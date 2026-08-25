"""Utilities shared by the Abundance research workflow.

This module re-exports all utilities from the submodules for backward compatibility.
"""

# Model Utils
from abundance_research.utils.model_utils import (
    strip_openrouter_prefix,
    prepare_model_config,
    build_reasoning_config,
    init_chat_model_wrapper,
    get_api_key_for_model,
    get_tavily_api_key,
    MODEL_TOKEN_LIMITS,
    get_model_token_limit,
    remove_up_to_last_ai_message,
    get_today_str,
    create_cached_message,
    get_config_value,
)

# Search Tools
from abundance_research.utils.search_tools import (
    TAVILY_SEARCH_DESCRIPTION,
    tavily_search,
    ARXIV_SEARCH_DESCRIPTION,
    arxiv_search,
    PUBMED_SEARCH_DESCRIPTION,
    pubmed_search,
    tavily_search_async,
    summarize_webpage,
)

# Error Handling
from abundance_research.utils.error_handling import (
    is_token_limit_exceeded,
    is_retryable_api_error,
    calculate_backoff_delay,
)

# MCP Tools
from abundance_research.utils.mcp_tools import (
    get_mcp_access_token,
    get_tokens,
    set_tokens,
    fetch_tokens,
    wrap_mcp_authenticate_tool,
    load_mcp_tools,
)

# Tool Management
from abundance_research.utils.tool_management import (
    think_tool,
    get_search_tool,
    get_all_tools,
    get_notes_from_tool_calls,
    anthropic_websearch_called,
    openai_websearch_called,
)

__all__ = [
    # Model Utils
    "strip_openrouter_prefix",
    "prepare_model_config",
    "build_reasoning_config",
    "init_chat_model_wrapper",
    "get_api_key_for_model",
    "get_tavily_api_key",
    "MODEL_TOKEN_LIMITS",
    "get_model_token_limit",
    "remove_up_to_last_ai_message",
    "get_today_str",
    "create_cached_message",
    "get_config_value",
    # Search Tools
    "TAVILY_SEARCH_DESCRIPTION",
    "tavily_search",
    "ARXIV_SEARCH_DESCRIPTION",
    "arxiv_search",
    "PUBMED_SEARCH_DESCRIPTION",
    "pubmed_search",
    "tavily_search_async",
    "summarize_webpage",
    # Error Handling
    "is_token_limit_exceeded",
    "is_retryable_api_error",
    "calculate_backoff_delay",
    # MCP Tools
    "get_mcp_access_token",
    "get_tokens",
    "set_tokens",
    "fetch_tokens",
    "wrap_mcp_authenticate_tool",
    "load_mcp_tools",
    # Tool Management
    "think_tool",
    "get_search_tool",
    "get_all_tools",
    "get_notes_from_tool_calls",
    "anthropic_websearch_called",
    "openai_websearch_called",
]
