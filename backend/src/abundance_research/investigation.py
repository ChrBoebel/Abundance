"""Individual investigator workflow for conducting focused research.

This module implements the investigator subgraph that conducts focused research
on specific topics using available search tools and MCP integrations.
"""

import asyncio
import logging
from typing import Literal

from abundance_research.utils import init_chat_model_wrapper, prepare_model_config
from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
    ToolMessage,
    filter_messages,
)
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from abundance_research.settings import AbundanceSettings
from abundance_research.prompts import (
    evidence_review_request,
    evidence_review_prompt,
    investigation_prompt,
)
from abundance_research.state import (
    InvestigationOutput,
    InvestigationState,
)
from abundance_research.utils import (
    anthropic_websearch_called,
    build_reasoning_config,
    create_cached_message,
    get_all_tools,
    get_api_key_for_model,
    get_today_str,
    is_token_limit_exceeded,
    openai_websearch_called,
    remove_up_to_last_ai_message,
)

logger = logging.getLogger(__name__)

# Initialize a configurable model for investigator workflow
configurable_model = init_chat_model_wrapper(
    configurable_fields=("model", "max_tokens", "api_key"),
)


async def execute_tool_safely(tool, args, config):
    """Safely execute a tool with error handling.

    Args:
        tool: The tool to execute
        args: Arguments to pass to the tool
        config: Runtime configuration

    Returns:
        Tool execution result or error message
    """
    try:
        return await tool.ainvoke(args, config)
    except Exception as e:
        tool_name = tool.name if hasattr(tool, "name") else str(tool)
        logger.error(f"Tool execution error [{tool_name}]: {e}", exc_info=True)
        return f"Error executing tool: {str(e)}"


async def investigator(state: InvestigationState, config: RunnableConfig) -> Command[Literal["run_evidence_tools"]]:
    """Individual investigator that conducts focused research on specific topics.

    This investigator is given a specific research topic by the coordinator and uses
    available tools (search, think_tool, MCP tools) to gather comprehensive information.
    It can use think_tool for strategic planning between searches.

    Args:
        state: Current investigator state with messages and topic context
        config: Runtime configuration with model settings and tool availability

    Returns:
        Command to proceed to run_evidence_tools for tool execution
    """
    # Step 1: Load configuration and validate tool availability
    configurable = AbundanceSettings.from_runnable_config(config)
    investigation_messages = state.get("investigation_messages", [])

    # Get all available research tools (search, MCP, think_tool)
    tools = await get_all_tools(config)
    if len(tools) == 0:
        raise ValueError(
            "No tools found to conduct research: Please configure either your "
            "search API or add MCP tools to your configuration."
        )

    # Step 2: Configure the investigator model with tools
    # Build reasoning configuration for investigator (analytical thinking)
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

    # Prepare system prompt with MCP context if available
    investigator_prompt = investigation_prompt.format(
        mcp_prompt=configurable.mcp_prompt or "",
        date=get_today_str()
    )

    # Configure model with tools, retry logic, and settings
    research_model = (
        configurable_model
        .bind_tools(tools)
        .with_retry(stop_after_attempt=configurable.max_structured_output_retries)
        .with_config(prepare_model_config(research_model_config, reasoning_config))
    )

    # Step 3: Generate investigator response with system context
    # Use cached system message for cost savings (system prompt is consistent)
    cached_system_message = create_cached_message(
        SystemMessage,
        investigator_prompt,
        enable_caching=configurable.enable_prompt_caching
    )
    messages = [cached_system_message] + investigation_messages
    response = await research_model.ainvoke(messages)

    # Step 4: Update state and proceed to tool execution
    return Command(
        goto="run_evidence_tools",
        update={
            "investigation_messages": [response],
            "tool_call_iterations": state.get("tool_call_iterations", 0) + 1
        }
    )


async def run_evidence_tools(state: InvestigationState, config: RunnableConfig) -> Command[Literal["investigator", "review_evidence"]]:
    """Execute tools called by the investigator, including search tools and strategic thinking.

    This function handles various types of investigator tool calls:
    1. think_tool - Strategic reflection that continues the research conversation
    2. Search tools (tavily_search, web_search) - Information gathering
    3. MCP tools - External tool integrations
    4. EvidenceReviewComplete - Signals completion of individual research task

    Args:
        state: Current investigator state with messages and iteration count
        config: Runtime configuration with research limits and tool settings

    Returns:
        Command to either continue research loop or proceed to compression
    """
    # Step 1: Extract current state and check early exit conditions
    configurable = AbundanceSettings.from_runnable_config(config)
    investigation_messages = state.get("investigation_messages", [])
    most_recent_message = investigation_messages[-1]

    # Early exit if no tool calls were made (including native web search)
    has_tool_calls = bool(most_recent_message.tool_calls)
    has_native_search = (
        openai_websearch_called(most_recent_message) or
        anthropic_websearch_called(most_recent_message)
    )

    if not has_tool_calls and not has_native_search:
        return Command(goto="review_evidence")

    # Step 2: Handle other tool calls (search, MCP tools, etc.)
    tools = await get_all_tools(config)
    tools_by_name = {
        tool.name if hasattr(tool, "name") else tool.get("name", "web_search"): tool
        for tool in tools
    }

    # Execute all tool calls in parallel
    tool_calls = most_recent_message.tool_calls
    tool_execution_tasks = [
        execute_tool_safely(tools_by_name[tool_call["name"]], tool_call["args"], config)
        for tool_call in tool_calls
    ]
    observations = await asyncio.gather(*tool_execution_tasks)

    # Create tool messages from execution results
    tool_outputs = [
        ToolMessage(
            content=observation,
            name=tool_call["name"],
            tool_call_id=tool_call["id"]
        )
        for observation, tool_call in zip(observations, tool_calls)
    ]

    # Step 3: Check late exit conditions (after processing tools)
    exceeded_iterations = state.get("tool_call_iterations", 0) >= configurable.max_search_iterations
    evidence_review_complete = any(
        tool_call["name"] == "EvidenceReviewComplete"
        for tool_call in most_recent_message.tool_calls
    )

    if exceeded_iterations or evidence_review_complete:
        # End research and proceed to compression
        return Command(
            goto="review_evidence",
            update={"investigation_messages": tool_outputs}
        )

    # Continue research loop with tool results
    return Command(
        goto="investigator",
        update={"investigation_messages": tool_outputs}
    )


async def review_evidence(state: InvestigationState, config: RunnableConfig):
    """Compress and synthesize research findings into a concise, structured summary.

    This function takes all the research findings, tool outputs, and AI messages from
    a investigator's work and distills them into a clean, comprehensive summary while
    preserving all important information and findings.

    Args:
        state: Current investigator state with accumulated research messages
        config: Runtime configuration with compression model settings

    Returns:
        Dictionary containing compressed research summary and raw notes
    """
    # Step 1: Configure the compression model
    configurable = AbundanceSettings.from_runnable_config(config)

    # Build reasoning configuration for compression (synthesis thinking)
    reasoning_config = build_reasoning_config(
        model_name=configurable.evidence_review_model,
        enable_reasoning=configurable.enable_reasoning,
        reasoning_effort=configurable.reasoning_effort,
        reasoning_max_tokens=configurable.reasoning_max_tokens,
        exclude_reasoning=configurable.exclude_reasoning_from_output
    )

    synthesizer_model = configurable_model.with_config(prepare_model_config({
        "model": configurable.evidence_review_model,
        "max_tokens": configurable.evidence_review_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.evidence_review_model, config),
        "tags": ["langsmith:nostream"]
    }, reasoning_config))

    # Step 2: Prepare messages for compression
    investigation_messages = state.get("investigation_messages", [])

    # Add instruction to switch from research mode to compression mode
    investigation_messages.append(HumanMessage(content=evidence_review_request))

    # Step 3: Attempt compression with retry logic for token limit issues
    synthesis_attempts = 0
    max_attempts = 3

    while synthesis_attempts < max_attempts:
        try:
            # Create system prompt focused on compression task
            compression_prompt = evidence_review_prompt.format(date=get_today_str())
            # Use cached system message for compression (consistent across all compressions)
            cached_compression_message = create_cached_message(
                SystemMessage,
                compression_prompt,
                enable_caching=configurable.enable_prompt_caching
            )
            messages = [cached_compression_message] + investigation_messages

            # Execute compression
            response = await synthesizer_model.ainvoke(messages)

            # Extract raw notes from all tool and AI messages
            raw_evidence_content = "\n".join([
                str(message.content)
                for message in filter_messages(investigation_messages, include_types=["tool", "ai"])
            ])

            # Return successful compression result
            return {
                "evidence_dossier": str(response.content),
                "raw_evidence": [raw_evidence_content]
            }

        except Exception as e:
            synthesis_attempts += 1
            logger.warning(
                f"Compression attempt {synthesis_attempts}/{max_attempts} failed: {type(e).__name__}: {str(e)}"
            )

            # Handle token limit exceeded by removing older messages
            if is_token_limit_exceeded(e, configurable.research_model):
                logger.info("Token limit exceeded during compression, removing older messages")
                investigation_messages = remove_up_to_last_ai_message(investigation_messages)
                continue

            # For other errors, continue retrying
            continue

    # Step 4: Return error result if all attempts failed
    logger.error(f"Research compression failed after {max_attempts} attempts, returning raw notes")
    raw_evidence_content = "\n".join([
        str(message.content)
        for message in filter_messages(investigation_messages, include_types=["tool", "ai"])
    ])

    return {
        "evidence_dossier": "Error synthesizing research report: Maximum retries exceeded",
        "raw_evidence": [raw_evidence_content]
    }


# Researcher Subgraph Construction
# Creates individual investigator workflow for conducting focused research on specific topics
investigation_builder = StateGraph(
    InvestigationState,
    output=InvestigationOutput,
    config_schema=AbundanceSettings
)

# Add investigator nodes for research execution and compression
investigation_builder.add_node("investigator", investigator)                 # Main investigator logic
investigation_builder.add_node("run_evidence_tools", run_evidence_tools)     # Tool execution handler
investigation_builder.add_node("review_evidence", review_evidence)   # Research compression

# Define investigator workflow edges
investigation_builder.add_edge(START, "investigator")           # Entry point to investigator
investigation_builder.add_edge("review_evidence", END)      # Exit point after compression

# Compile investigator subgraph for parallel execution by coordinator
investigation_subgraph = investigation_builder.compile()
