"""Supervisor workflow for coordinating research delegation.

This module implements the coordinator subgraph that plans research strategy
and delegates bounded evidence questions to parallel investigators.
"""

import asyncio
import logging
from typing import Literal

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from abundance_research.investigation import investigation_subgraph
from abundance_research.settings import AbundanceSettings
from abundance_research.state import (
    CoordinationState,
    EvidenceReviewComplete,
    InvestigateQuestion,
)
from abundance_research.utils import (
    build_reasoning_config,
    get_api_key_for_model,
    get_notes_from_tool_calls,
    init_chat_model_wrapper,
    is_token_limit_exceeded,
    prepare_model_config,
    think_tool,
)

logger = logging.getLogger(__name__)

# Initialize a configurable model for coordinator workflow
configurable_model = init_chat_model_wrapper(
    configurable_fields=("model", "max_tokens", "api_key"),
)


async def coordinator(state: CoordinationState, config: RunnableConfig) -> Command[Literal["coordinate_tasks"]]:
    """Lead research coordinator that plans research strategy and delegates to researchers.

    The coordinator analyzes the research brief and decides how to break down the research
    into manageable tasks. It can use think_tool for strategic planning, InvestigateQuestion
    to delegate tasks to sub-researchers, or EvidenceReviewComplete when satisfied with findings.

    Args:
        state: Current coordinator state with messages and research context
        config: Runtime configuration with model settings

    Returns:
        Command to proceed to coordinate_tasks for tool execution
    """
    # Step 1: Configure the coordinator model with available tools
    configurable = AbundanceSettings.from_runnable_config(config)

    # Build reasoning configuration for coordinator (strategic thinking)
    reasoning_config = build_reasoning_config(
        model_name=configurable.research_model,
        enable_reasoning=configurable.enable_reasoning,
        reasoning_effort=configurable.reasoning_effort,
        reasoning_max_tokens=configurable.reasoning_max_tokens,
        exclude_reasoning=configurable.exclude_reasoning_from_output
    )

    research_model_config = {
        "model": configurable.research_model,
        "max_tokens": configurable.research_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.research_model, config),
        "tags": ["langsmith:nostream"]
    }

    # Available tools: research delegation, completion signaling, and strategic thinking
    coordination_tools = [InvestigateQuestion, EvidenceReviewComplete, think_tool]

    # Configure model with tools, retry logic, and model settings
    research_model = (
        configurable_model
        .bind_tools(coordination_tools)
        .with_retry(stop_after_attempt=configurable.max_structured_output_retries)
        .with_config(prepare_model_config(research_model_config, reasoning_config))
    )

    # Step 2: Generate coordinator response based on current context
    coordination_messages = state.get("coordination_messages", [])
    response = await research_model.ainvoke(coordination_messages)

    # Step 3: Update state and proceed to tool execution
    return Command(
        goto="coordinate_tasks",
        update={
            "coordination_messages": [response],
            "coordination_iterations": state.get("coordination_iterations", 0) + 1
        }
    )


async def coordinate_tasks(state: CoordinationState, config: RunnableConfig) -> Command[Literal["coordinator", "__end__"]]:
    """Execute tools called by the coordinator, including research delegation and strategic thinking.

    This function handles three types of coordinator tool calls:
    1. think_tool - Strategic reflection that continues the conversation
    2. InvestigateQuestion - Delegates research tasks to sub-researchers
    3. EvidenceReviewComplete - Signals completion of research phase

    Args:
        state: Current coordinator state with messages and iteration count
        config: Runtime configuration with research limits and model settings

    Returns:
        Command to either continue supervision loop or end research phase
    """
    # Step 1: Extract current state and check exit conditions
    configurable = AbundanceSettings.from_runnable_config(config)
    coordination_messages = state.get("coordination_messages", [])
    coordination_iterations = state.get("coordination_iterations", 0)
    most_recent_message = coordination_messages[-1]

    # Define exit criteria for research phase
    exceeded_allowed_iterations = coordination_iterations >= configurable.max_coordination_iterations
    no_tool_calls = not most_recent_message.tool_calls
    evidence_review_complete = any(
        tool_call["name"] == "EvidenceReviewComplete"
        for tool_call in most_recent_message.tool_calls
    )

    # Exit if any termination condition is met
    if exceeded_allowed_iterations or no_tool_calls or evidence_review_complete:
        return Command(
            goto=END,
            update={
                "notes": get_notes_from_tool_calls(coordination_messages),
                "research_brief": state.get("research_brief", "")
            }
        )

    # Step 2: Process all tool calls together (both think_tool and InvestigateQuestion)
    all_tool_messages = []
    update_payload = {"coordination_messages": []}

    # Handle think_tool calls (strategic reflection)
    think_tool_calls = [
        tool_call for tool_call in most_recent_message.tool_calls
        if tool_call["name"] == "think_tool"
    ]

    for tool_call in think_tool_calls:
        reflection_content = tool_call["args"]["reflection"]
        all_tool_messages.append(ToolMessage(
            content=f"Reflection recorded: {reflection_content}",
            name="think_tool",
            tool_call_id=tool_call["id"]
        ))

    # Handle InvestigateQuestion calls (research delegation)
    investigation_calls = [
        tool_call for tool_call in most_recent_message.tool_calls
        if tool_call["name"] == "InvestigateQuestion"
    ]

    if investigation_calls:
        try:
            # Limit concurrent research units to prevent resource exhaustion
            allowed_investigation_calls = investigation_calls[:configurable.max_concurrent_research_units]
            overflow_investigation_calls = investigation_calls[configurable.max_concurrent_research_units:]

            # Execute research tasks in parallel
            research_tasks = [
                investigation_subgraph.ainvoke({
                    "investigation_messages": [
                        HumanMessage(content=tool_call["args"]["evidence_question"])
                    ],
                    "evidence_question": tool_call["args"]["evidence_question"]
                }, config)
                for tool_call in allowed_investigation_calls
            ]

            tool_results = await asyncio.gather(*research_tasks)

            # Create tool messages with research results
            for observation, tool_call in zip(tool_results, allowed_investigation_calls):
                all_tool_messages.append(ToolMessage(
                    content=observation.get("evidence_dossier", "Error synthesizing research report: Maximum retries exceeded"),
                    name=tool_call["name"],
                    tool_call_id=tool_call["id"]
                ))

            # Handle overflow research calls with error messages
            for overflow_call in overflow_investigation_calls:
                all_tool_messages.append(ToolMessage(
                    content=f"Error: Did not run this research as you have already exceeded the maximum number of concurrent research units. Please try again with {configurable.max_concurrent_research_units} or fewer research units.",
                    name="InvestigateQuestion",
                    tool_call_id=overflow_call["id"]
                ))

            # Aggregate raw notes from all research results
            raw_evidence_concat = "\n".join([
                "\n".join(observation.get("raw_evidence", []))
                for observation in tool_results
            ])

            if raw_evidence_concat:
                update_payload["raw_evidence"] = [raw_evidence_concat]

        except Exception as e:
            # Handle research execution errors
            if is_token_limit_exceeded(e, configurable.research_model):
                # Token limit exceeded - end research phase
                logger.warning(
                    f"Token limit exceeded during research delegation, ending research phase early. "
                    f"Collected {len(get_notes_from_tool_calls(coordination_messages))} notes so far."
                )
                return Command(
                    goto=END,
                    update={
                        "notes": get_notes_from_tool_calls(coordination_messages),
                        "research_brief": state.get("research_brief", "")
                    }
                )
            # Re-raise other exceptions to allow retry logic to handle them
            logger.error(f"Research delegation failed: {e}", exc_info=True)
            raise

    # Step 3: Return command with all tool results
    update_payload["coordination_messages"] = all_tool_messages
    return Command(
        goto="coordinator",
        update=update_payload
    )


# Supervisor Subgraph Construction
# Creates the coordinator workflow that manages research delegation and coordination
coordination_builder = StateGraph(CoordinationState, config_schema=AbundanceSettings)

# Add coordinator nodes for research management
coordination_builder.add_node("coordinator", coordinator)           # Main coordinator logic
coordination_builder.add_node("coordinate_tasks", coordinate_tasks)  # Tool execution handler

# Define coordinator workflow edges
coordination_builder.add_edge(START, "coordinator")  # Entry point to coordinator

# Compile coordinator subgraph for use in main workflow
coordination_subgraph = coordination_builder.compile()
