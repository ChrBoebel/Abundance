"""Research clarification and brief generation workflow.

This module handles the initial phase of an Abundance research run, including
user clarification and research brief generation.
"""

from typing import Literal

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    get_buffer_string,
)
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.types import Command

from abundance_research.prompts import (
    coordination_prompt,
    inquiry_scoping_prompt,
    research_brief_prompt,
)
from abundance_research.settings import AbundanceSettings
from abundance_research.state import (
    ClarificationDecision,
    ResearchBrief,
    ResearchRunState,
)
from abundance_research.utils import (
    create_cached_message,
    get_api_key_for_model,
    get_today_str,
    init_chat_model_wrapper,
    prepare_model_config,
)

# Initialize a configurable model for clarification workflow
configurable_model = init_chat_model_wrapper(
    configurable_fields=("model", "max_tokens", "api_key"),
)


async def scope_inquiry(state: ResearchRunState, config: RunnableConfig) -> Command[Literal["design_research_plan", "__end__"]]:
    """Analyze user messages and ask clarifying questions if the research scope is unclear.

    This function determines whether the user's request needs clarification before proceeding
    with research. If clarification is disabled or not needed, it proceeds directly to research.

    Args:
        state: Current agent state containing user messages
        config: Runtime configuration with model settings and preferences

    Returns:
        Command to either end with a clarifying question or proceed to research brief
    """
    # Step 1: Check if clarification is enabled in configuration
    configurable = AbundanceSettings.from_runnable_config(config)
    if not configurable.allow_clarification:
        # Skip clarification step and proceed directly to research
        return Command(goto="design_research_plan")

    # Step 2: Prepare the model for structured clarification analysis
    messages = state["messages"]
    model_config = {
        "model": configurable.research_model,
        "max_tokens": configurable.research_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.research_model, config),
        "tags": ["langsmith:nostream"]
    }

    # Configure model with structured output and retry logic
    clarification_model = (
        configurable_model
        .with_structured_output(ClarificationDecision)
        .with_retry(stop_after_attempt=configurable.max_structured_output_retries)
        .with_config(prepare_model_config(model_config))
    )

    # Step 3: Analyze whether clarification is needed
    prompt_content = inquiry_scoping_prompt.format(
        messages=get_buffer_string(messages),
        date=get_today_str()
    )
    response = await clarification_model.ainvoke([HumanMessage(content=prompt_content)])

    # Step 4: Route based on clarification analysis
    if response.need_clarification:
        # End with clarifying question for user
        return Command(
            goto=END,
            update={"messages": [AIMessage(content=response.question)]}
        )
    else:
        # Proceed to research with verification message
        return Command(
            goto="design_research_plan",
            update={"messages": [AIMessage(content=response.verification)]}
        )


async def design_research_plan(state: ResearchRunState, config: RunnableConfig) -> Command[Literal["coordinate_research"]]:
    """Transform user messages into a structured research brief and initialize coordinator.

    This function analyzes the user's messages and generates a focused research brief
    that will guide the research coordinator. It also sets up the initial coordinator
    context with appropriate prompts and instructions.

    Args:
        state: Current agent state containing user messages
        config: Runtime configuration with model settings

    Returns:
        Command to proceed to research coordinator with initialized context
    """
    # Step 1: Set up the research model for structured output
    configurable = AbundanceSettings.from_runnable_config(config)
    research_model_config = {
        "model": configurable.research_model,
        "max_tokens": configurable.research_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.research_model, config),
        "tags": ["langsmith:nostream"]
    }

    # Configure model for structured research question generation
    research_model = (
        configurable_model
        .with_structured_output(ResearchBrief)
        .with_retry(stop_after_attempt=configurable.max_structured_output_retries)
        .with_config(prepare_model_config(research_model_config))
    )

    # Step 2: Generate structured research brief from user messages
    prompt_content = research_brief_prompt.format(
        messages=get_buffer_string(state.get("messages", [])),
        date=get_today_str()
    )
    response = await research_model.ainvoke([HumanMessage(content=prompt_content)])

    # Step 3: Initialize coordinator with research brief and instructions
    supervisor_system_prompt = coordination_prompt.format(
        date=get_today_str(),
        max_concurrent_research_units=configurable.max_concurrent_research_units,
        max_coordination_iterations=configurable.max_coordination_iterations
    )

    # Use cached messages for cost savings (coordinator prompt is consistent)
    # The research brief is especially valuable to cache as it's sent to all parallel researchers
    cached_supervisor_system = create_cached_message(
        SystemMessage,
        supervisor_system_prompt,
        enable_caching=configurable.enable_prompt_caching
    )
    cached_research_brief = create_cached_message(
        HumanMessage,
        response.research_brief,
        enable_caching=configurable.enable_prompt_caching
    )

    return Command(
        goto="coordinate_research",
        update={
            "research_brief": response.research_brief,
            "coordination_messages": {
                "type": "override",
                "value": [
                    cached_supervisor_system,
                    cached_research_brief
                ]
            }
        }
    )
