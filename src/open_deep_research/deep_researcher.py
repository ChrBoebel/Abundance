"""Main LangGraph implementation for the Deep Research agent.

This module orchestrates the complete deep research workflow, integrating
clarification, research supervision, and final report generation phases.
"""

import asyncio
import logging
import re

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, get_buffer_string
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from open_deep_research.clarification import clarify_with_user, write_research_brief
from open_deep_research.configuration import Configuration
from open_deep_research.prompts import final_report_generation_prompt
from open_deep_research.state import AgentInputState, AgentState
from open_deep_research.supervisor import supervisor_subgraph
from open_deep_research.utils import (
    calculate_backoff_delay,
    get_api_key_for_model,
    get_model_token_limit,
    get_today_str,
    is_retryable_api_error,
    is_token_limit_exceeded,
)

logger = logging.getLogger(__name__)

# Initialize a configurable model that we will use throughout the agent
configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens", "api_key"),
)


async def final_report_generation(state: AgentState, config: RunnableConfig):
    """Generate the final comprehensive research report with retry logic for token limits.

    This function takes all collected research findings and synthesizes them into a
    well-structured, comprehensive final report using the configured report generation model.

    Args:
        state: Agent state containing research findings and context
        config: Runtime configuration with model settings and API keys

    Returns:
        Dictionary containing the final report and cleared state
    """
    # Step 1: Extract research findings and prepare state cleanup
    notes = state.get("notes", [])
    cleared_state = {"notes": {"type": "override", "value": []}}
    findings = "\n".join(notes)

    # Step 2: Configure the final report generation model
    configurable = Configuration.from_runnable_config(config)
    writer_model_config = {
        "model": configurable.final_report_model,
        "max_tokens": configurable.final_report_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.final_report_model, config),
        "tags": ["langsmith:nostream"]
    }

    # Step 3: Attempt report generation with API retry and token limit retry logic
    max_retries = 3
    current_retry = 0
    findings_token_limit = None

    # Outer retry loop for API errors (rate limiting, server errors, timeouts)
    for api_retry_attempt in range(configurable.api_retry_attempts):
        try:
            # Inner retry loop for token limit errors
            while current_retry <= max_retries:
                try:
                    # Create comprehensive prompt with all research context
                    final_report_prompt = final_report_generation_prompt.format(
                        research_brief=state.get("research_brief", ""),
                        messages=get_buffer_string(state.get("messages", [])),
                        findings=findings,
                        date=get_today_str()
                    )

                    # Generate the final report
                    final_report = await configurable_model.with_config(writer_model_config).ainvoke([
                        HumanMessage(content=final_report_prompt)
                    ])

                    # Return successful report generation
                    return {
                        "final_report": final_report.content,
                        "messages": [final_report],
                        **cleared_state
                    }

                except Exception as e:
                    # Handle token limit exceeded errors with progressive truncation
                    if is_token_limit_exceeded(e, configurable.final_report_model):
                        current_retry += 1
                        logger.warning(
                            f"Token limit exceeded during final report generation "
                            f"(attempt {current_retry}/{max_retries}), truncating findings"
                        )

                        if current_retry == 1:
                            # First retry: determine initial truncation limit
                            model_token_limit = get_model_token_limit(configurable.final_report_model)
                            if not model_token_limit:
                                error_msg = (
                                    f"Token limit exceeded but could not determine model's maximum context length. "
                                    f"Please update the model map in utils.py with this information."
                                )
                                logger.error(f"{error_msg} Error: {e}")
                                return {
                                    "final_report": f"Error generating final report: {error_msg}",
                                    "messages": [AIMessage(content="Report generation failed due to token limits")],
                                    **cleared_state
                                }
                            # Use 4x token limit as character approximation for truncation
                            findings_token_limit = model_token_limit * 4
                            logger.info(f"Truncating findings to ~{findings_token_limit} characters")
                        else:
                            # Subsequent retries: reduce by 10% each time
                            findings_token_limit = int(findings_token_limit * 0.9)
                            logger.info(f"Further reducing findings to ~{findings_token_limit} characters")

                        # Smart truncation: preserve sources section
                        sources_match = re.search(r'### Sources\n(.+)', findings, re.DOTALL)
                        if sources_match:
                            # Extract sources section and main content
                            sources_section = sources_match.group(0)
                            main_content = findings[:sources_match.start()]

                            # Truncate main content only, preserve sources
                            max_main_content_length = findings_token_limit - len(sources_section) - 10
                            if max_main_content_length > 0:
                                truncated_main = main_content[:max_main_content_length]
                                findings = truncated_main + "\n\n" + sources_section
                            else:
                                # If sources are too large, keep them anyway
                                findings = sources_section
                        else:
                            # No sources section found, use blind truncation
                            findings = findings[:findings_token_limit]
                        continue
                    else:
                        # Not a token limit error, re-raise for outer retry logic
                        raise

            # If we exhausted token limit retries, break to try API retry
            break

        except Exception as e:
            # Check if this is a retryable API error
            if is_retryable_api_error(e):
                # If not the last retry attempt, wait with exponential backoff
                if api_retry_attempt < configurable.api_retry_attempts - 1:
                    delay = calculate_backoff_delay(api_retry_attempt, configurable)
                    logger.info(
                        f"Retryable API error during final report generation "
                        f"(attempt {api_retry_attempt + 1}/{configurable.api_retry_attempts}), "
                        f"retrying after {delay}s backoff"
                    )
                    await asyncio.sleep(delay)
                    # Reset token retry counter for next API retry
                    current_retry = 0
                    continue
                # Last attempt, fall through to return error
                logger.error(f"Final report generation failed after {configurable.api_retry_attempts} API retries: {e}")

            # Non-retryable error or exhausted retries: return error
            logger.error(f"Final report generation failed with non-retryable error: {e}", exc_info=True)
            return {
                "final_report": f"Error generating final report: {e}",
                "messages": [AIMessage(content="Report generation failed due to an error")],
                **cleared_state
            }

    # Step 4: Return failure result if all retries exhausted
    logger.error("Final report generation failed: Maximum retries exceeded")
    return {
        "final_report": "Error generating final report: Maximum retries exceeded",
        "messages": [AIMessage(content="Report generation failed after maximum retries")],
        **cleared_state
    }


# Main Deep Researcher Graph Construction
# Creates the complete deep research workflow from user input to final report
deep_researcher_builder = StateGraph(
    AgentState,
    input=AgentInputState,
    config_schema=Configuration
)

# Add main workflow nodes for the complete research process
deep_researcher_builder.add_node("clarify_with_user", clarify_with_user)           # User clarification phase
deep_researcher_builder.add_node("write_research_brief", write_research_brief)     # Research planning phase
deep_researcher_builder.add_node("research_supervisor", supervisor_subgraph)       # Research execution phase
deep_researcher_builder.add_node("final_report_generation", final_report_generation)  # Report generation phase

# Define main workflow edges for sequential execution
deep_researcher_builder.add_edge(START, "clarify_with_user")                       # Entry point
deep_researcher_builder.add_edge("research_supervisor", "final_report_generation") # Research to report
deep_researcher_builder.add_edge("final_report_generation", END)                   # Final exit point

# Compile the complete deep researcher workflow
deep_researcher = deep_researcher_builder.compile()
