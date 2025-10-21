"""Comprehensive tests for utils.py before refactoring into modules."""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, SystemMessage

from open_deep_research.configuration import Configuration, SearchAPI
from open_deep_research.utils import (
    # Model Utils
    strip_openrouter_prefix,
    prepare_model_config,
    build_reasoning_config,
    get_api_key_for_model,
    get_model_token_limit,
    get_config_value,
    get_today_str,
    create_cached_message,
    remove_up_to_last_ai_message,
    # Error Handling
    is_token_limit_exceeded,
    is_retryable_api_error,
    calculate_backoff_delay,
    # Tool Management
    think_tool,
    get_search_tool,
    anthropic_websearch_called,
    openai_websearch_called,
    get_notes_from_tool_calls,
    # Search Tools
    tavily_search_async,
    summarize_webpage,
)


##########################
# Model Utils Tests
##########################

class TestModelUtils:
    """Test model initialization and configuration utilities."""

    def test_strip_openrouter_prefix(self):
        """Test removal of openrouter: prefix from model names."""
        assert strip_openrouter_prefix("openrouter:deepseek/deepseek-v3.2-exp") == "deepseek/deepseek-v3.2-exp"
        assert strip_openrouter_prefix("deepseek/deepseek-v3.2-exp") == "deepseek/deepseek-v3.2-exp"
        assert strip_openrouter_prefix("openrouter:openrouter:double") == "openrouter:double"
        assert strip_openrouter_prefix("") == ""
        assert strip_openrouter_prefix(None) is None

    def test_prepare_model_config_basic(self):
        """Test basic model config preparation."""
        config = {"model": "openrouter:deepseek/v3", "temperature": 0.7}
        result = prepare_model_config(config)

        assert result["model"] == "deepseek/v3"
        assert result["temperature"] == 0.7
        assert "reasoning_config" not in result

    def test_prepare_model_config_with_reasoning(self):
        """Test model config preparation with reasoning config."""
        config = {"model": "openrouter:deepseek/v3"}
        reasoning = {"enabled": True, "effort": "high"}
        result = prepare_model_config(config, reasoning_config=reasoning)

        assert result["model"] == "deepseek/v3"
        assert result["reasoning_config"] == reasoning

    def test_build_reasoning_config_disabled(self):
        """Test reasoning config when disabled."""
        config = build_reasoning_config("openrouter:deepseek/v3", False, "high", 8000, False)
        assert config == {}

    def test_build_reasoning_config_openai_style(self):
        """Test reasoning config for OpenAI-style models."""
        # Test with various OpenAI-compatible models
        models = ["openrouter:openai/gpt-4", "openrouter:o1-preview", "openrouter:grok-2"]

        for model in models:
            config = build_reasoning_config(model, True, "medium", 8000, True)
            assert config["enabled"] is True
            assert config["exclude"] is True
            assert config["effort"] == "medium"
            assert "max_tokens" not in config

    def test_build_reasoning_config_anthropic_style(self):
        """Test reasoning config for Anthropic models."""
        config = build_reasoning_config("openrouter:anthropic/claude-3-5-sonnet", True, "high", 4000, False)

        assert config["enabled"] is True
        assert config["exclude"] is False
        assert config["max_tokens"] == 4000
        assert "effort" not in config

    def test_build_reasoning_config_gemini_style(self):
        """Test reasoning config for Gemini models."""
        config = build_reasoning_config("openrouter:google/gemini-2.0-flash", True, "high", 8192, True)

        assert config["enabled"] is True
        assert config["exclude"] is True
        assert config["max_tokens"] == 8192
        assert "effort" not in config

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-openai-key", "ANTHROPIC_API_KEY": "test-anthropic-key"})
    def test_get_api_key_for_model_from_env(self):
        """Test API key retrieval from environment variables."""
        config = {}

        assert get_api_key_for_model("openai:gpt-4", config) == "test-openai-key"
        assert get_api_key_for_model("anthropic:claude-3", config) == "test-anthropic-key"

    @patch.dict(os.environ, {"GET_API_KEYS_FROM_CONFIG": "true"})
    def test_get_api_key_for_model_from_config(self):
        """Test API key retrieval from config."""
        config = {
            "configurable": {
                "apiKeys": {
                    "OPENAI_API_KEY": "config-openai-key",
                    "OPENROUTER_API_KEY": "config-openrouter-key"
                }
            }
        }

        assert get_api_key_for_model("openai:gpt-4", config) == "config-openai-key"
        assert get_api_key_for_model("openrouter:deepseek/v3", config) == "config-openrouter-key"

    def test_get_model_token_limit(self):
        """Test token limit lookup for various models."""
        assert get_model_token_limit("openai:gpt-4o") == 128000
        assert get_model_token_limit("anthropic:claude-opus-4") == 200000
        assert get_model_token_limit("google:gemini-1.5-pro") == 2097152
        assert get_model_token_limit("unknown:model") is None

    def test_get_config_value(self):
        """Test config value extraction."""
        assert get_config_value("simple_string") == "simple_string"
        assert get_config_value({"key": "value"}) == {"key": "value"}
        assert get_config_value(None) is None

        # Test with enum-like object
        mock_enum = Mock()
        mock_enum.value = "enum_value"
        assert get_config_value(mock_enum) == "enum_value"

    def test_get_today_str(self):
        """Test date string generation."""
        result = get_today_str()
        # Should match format like "Mon Jan 15, 2024"
        assert len(result.split()) == 4
        assert "," in result

    def test_create_cached_message_enabled(self):
        """Test message creation with caching enabled."""
        msg = create_cached_message(HumanMessage, "Test content", enable_caching=True)

        assert isinstance(msg, HumanMessage)
        assert msg.content == "Test content"
        assert "cache_control" in msg.additional_kwargs
        assert msg.additional_kwargs["cache_control"]["type"] == "ephemeral"

    def test_create_cached_message_disabled(self):
        """Test message creation with caching disabled."""
        msg = create_cached_message(SystemMessage, "Test content", enable_caching=False)

        assert isinstance(msg, SystemMessage)
        assert msg.content == "Test content"
        assert "cache_control" not in msg.additional_kwargs

    def test_remove_up_to_last_ai_message(self):
        """Test message truncation up to last AI message."""
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there"),
            HumanMessage(content="How are you?"),
            AIMessage(content="I'm good"),
            HumanMessage(content="Great"),
        ]

        result = remove_up_to_last_ai_message(messages)

        # Should remove up to the last AI message (index 3)
        assert len(result) == 3
        assert result[-1].content == "How are you?"

    def test_remove_up_to_last_ai_message_no_ai(self):
        """Test message truncation when no AI messages exist."""
        messages = [
            HumanMessage(content="Hello"),
            HumanMessage(content="World"),
        ]

        result = remove_up_to_last_ai_message(messages)
        assert result == messages


##########################
# Error Handling Tests
##########################

class TestErrorHandling:
    """Test error detection and retry logic."""

    def test_is_token_limit_exceeded_openai(self):
        """Test OpenAI token limit error detection."""
        # Create a custom exception class that mimics OpenAI errors
        class BadRequestError(Exception):
            def __init__(self, message):
                super().__init__(message)
                self.code = "context_length_exceeded"
                self.type = "invalid_request_error"

        BadRequestError.__module__ = "openai.error"
        error = BadRequestError("Error code: context_length_exceeded - This model's maximum context length is 128000 tokens")

        assert is_token_limit_exceeded(error, "openai:gpt-4o") is True

    def test_is_token_limit_exceeded_anthropic(self):
        """Test Anthropic token limit error detection."""
        # Create a custom exception class that mimics Anthropic errors
        class BadRequestError(Exception):
            pass

        BadRequestError.__module__ = "anthropic.error"
        error = BadRequestError("prompt is too long: maximum context length exceeded")

        assert is_token_limit_exceeded(error, "anthropic:claude-3") is True

    def test_is_token_limit_exceeded_gemini(self):
        """Test Gemini token limit error detection."""
        # Create a custom exception class that mimics Google errors
        class ResourceExhausted(Exception):
            pass

        ResourceExhausted.__module__ = "google.api_core.exceptions"
        error = ResourceExhausted("Resource exhausted: quota exceeded")

        assert is_token_limit_exceeded(error, "google:gemini-1.5-pro") is True

    def test_is_token_limit_exceeded_not_exceeded(self):
        """Test that non-token errors are not detected as token limits."""
        error = Exception("Some other error")
        assert is_token_limit_exceeded(error) is False

    def test_is_retryable_api_error_rate_limit(self):
        """Test rate limit error detection."""
        errors = [
            Exception("Rate limit exceeded"),
            Exception("429 Too Many Requests"),
            Exception("quota exceeded"),
        ]

        for error in errors:
            assert is_retryable_api_error(error) is True

    def test_is_retryable_api_error_server_error(self):
        """Test server error detection."""
        errors = [
            Exception("500 Internal Server Error"),
            Exception("503 Service Unavailable"),
            Exception("backend error occurred"),
        ]

        for error in errors:
            assert is_retryable_api_error(error) is True

    def test_is_retryable_api_error_timeout(self):
        """Test timeout error detection."""
        errors = [
            Exception("Request timed out"),
            Exception("deadline exceeded"),
        ]

        for error in errors:
            assert is_retryable_api_error(error) is True

    def test_is_retryable_api_error_not_retryable(self):
        """Test that non-retryable errors are not detected."""
        error = Exception("Invalid API key")
        assert is_retryable_api_error(error) is False

    def test_calculate_backoff_delay(self):
        """Test exponential backoff calculation."""
        # Create a mock config
        config = Mock()
        config.api_retry_initial_delay = 1.0
        config.api_retry_exponential_base = 2.0
        config.api_retry_max_delay = 60.0

        # Test exponential growth
        assert calculate_backoff_delay(0, config) == 1.0  # 1 * 2^0
        assert calculate_backoff_delay(1, config) == 2.0  # 1 * 2^1
        assert calculate_backoff_delay(2, config) == 4.0  # 1 * 2^2
        assert calculate_backoff_delay(3, config) == 8.0  # 1 * 2^3

        # Test max delay cap
        assert calculate_backoff_delay(10, config) == 60.0  # capped at max


##########################
# Tool Management Tests
##########################

class TestToolManagement:
    """Test tool management and orchestration."""

    def test_think_tool(self):
        """Test reflection tool functionality."""
        result = think_tool.invoke({"reflection": "Analyzing search results..."})

        assert "Reflection recorded" in result
        assert "Analyzing search results" in result

    @pytest.mark.asyncio
    async def test_get_search_tool_tavily(self):
        """Test Tavily search tool configuration."""
        tools = await get_search_tool(SearchAPI.TAVILY)

        assert len(tools) == 3  # tavily, arxiv, pubmed
        assert any(hasattr(t, "metadata") and t.metadata.get("name") == "web_search" for t in tools)

    @pytest.mark.asyncio
    async def test_get_search_tool_anthropic(self):
        """Test Anthropic native search configuration."""
        tools = await get_search_tool(SearchAPI.ANTHROPIC)

        assert len(tools) == 1
        assert tools[0]["type"] == "web_search_20250305"
        assert tools[0]["max_uses"] == 5

    @pytest.mark.asyncio
    async def test_get_search_tool_openai(self):
        """Test OpenAI search configuration."""
        tools = await get_search_tool(SearchAPI.OPENAI)

        assert len(tools) == 1
        assert tools[0]["type"] == "web_search_preview"

    @pytest.mark.asyncio
    async def test_get_search_tool_none(self):
        """Test no search configuration."""
        tools = await get_search_tool(SearchAPI.NONE)
        assert tools == []

    def test_anthropic_websearch_called_true(self):
        """Test Anthropic web search detection when called."""
        response = Mock()
        response.response_metadata = {
            "usage": {
                "server_tool_use": {
                    "web_search_requests": 2
                }
            }
        }

        assert anthropic_websearch_called(response) is True

    def test_anthropic_websearch_called_false(self):
        """Test Anthropic web search detection when not called."""
        response = Mock()
        response.response_metadata = {
            "usage": {
                "server_tool_use": {
                    "web_search_requests": 0
                }
            }
        }

        assert anthropic_websearch_called(response) is False

    def test_anthropic_websearch_called_missing_data(self):
        """Test Anthropic web search detection with missing metadata."""
        response = Mock()
        response.response_metadata = {}

        assert anthropic_websearch_called(response) is False

    def test_openai_websearch_called_true(self):
        """Test OpenAI web search detection when called."""
        response = Mock()
        response.additional_kwargs = {
            "tool_outputs": [
                {"type": "web_search_call", "data": "..."}
            ]
        }

        assert openai_websearch_called(response) is True

    def test_openai_websearch_called_false(self):
        """Test OpenAI web search detection when not called."""
        response = Mock()
        response.additional_kwargs = {
            "tool_outputs": []
        }

        assert openai_websearch_called(response) is False

    def test_get_notes_from_tool_calls(self):
        """Test extracting notes from tool messages."""
        messages = [
            HumanMessage(content="Query"),
            ToolMessage(content="Result 1", tool_call_id="1"),
            AIMessage(content="Thinking"),
            ToolMessage(content="Result 2", tool_call_id="2"),
        ]

        notes = get_notes_from_tool_calls(messages)

        assert len(notes) == 2
        assert "Result 1" in notes
        assert "Result 2" in notes


##########################
# Search Tools Tests
##########################

class TestSearchTools:
    """Test search functionality."""

    @pytest.mark.asyncio
    async def test_tavily_search_async(self):
        """Test async Tavily search execution."""
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(return_value={
            "query": "test query",
            "results": [
                {
                    "title": "Test Result",
                    "url": "https://example.com",
                    "content": "Test content",
                    "raw_content": "Raw test content"
                }
            ]
        })

        with patch("open_deep_research.utils.search_tools.AsyncTavilyClient", return_value=mock_client):
            with patch("open_deep_research.utils.search_tools.get_tavily_api_key", return_value="test-key"):
                results = await tavily_search_async(
                    ["test query"],
                    max_results=5,
                    topic="general",
                    config={}
                )

                assert len(results) == 1
                assert results[0]["query"] == "test query"
                assert len(results[0]["results"]) == 1

    @pytest.mark.asyncio
    async def test_summarize_webpage_success(self):
        """Test successful webpage summarization."""
        mock_model = AsyncMock()
        mock_summary = Mock()
        mock_summary.summary = "This is a summary"
        mock_summary.key_excerpts = "Key excerpt 1\nKey excerpt 2"
        mock_model.ainvoke = AsyncMock(return_value=mock_summary)

        result = await summarize_webpage(mock_model, "Long webpage content here...", enable_caching=True)

        assert "<summary>" in result
        assert "This is a summary" in result
        assert "<key_excerpts>" in result
        assert "Key excerpt 1" in result

    @pytest.mark.asyncio
    async def test_summarize_webpage_timeout(self):
        """Test webpage summarization timeout handling."""
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(side_effect=asyncio.TimeoutError())

        content = "Original content"
        result = await summarize_webpage(mock_model, content, enable_caching=False)

        # Should return original content on timeout
        assert result == content

    @pytest.mark.asyncio
    async def test_summarize_webpage_error(self):
        """Test webpage summarization error handling."""
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(side_effect=Exception("API Error"))

        content = "Original content"
        result = await summarize_webpage(mock_model, content, enable_caching=False)

        # Should return original content on error
        assert result == content


##########################
# Integration Tests
##########################

class TestIntegration:
    """Integration tests for combined functionality."""

    def test_model_config_pipeline(self):
        """Test complete model configuration pipeline."""
        # Step 1: Build reasoning config
        reasoning = build_reasoning_config(
            "openrouter:deepseek/deepseek-v3.2-exp",
            enable_reasoning=True,
            reasoning_effort="high",
            reasoning_max_tokens=8000,
            exclude_reasoning=False
        )

        # Step 2: Prepare model config
        base_config = {
            "model": "openrouter:deepseek/deepseek-v3.2-exp",
            "temperature": 0.7,
            "max_tokens": 4096
        }

        final_config = prepare_model_config(base_config, reasoning_config=reasoning)

        # Verify pipeline results
        assert final_config["model"] == "deepseek/deepseek-v3.2-exp"
        assert final_config["temperature"] == 0.7
        assert final_config["reasoning_config"]["enabled"] is True

    def test_error_detection_pipeline(self):
        """Test error detection and retry decision pipeline."""
        # Retryable error
        retry_error = Exception("429 Rate limit exceeded")
        assert is_retryable_api_error(retry_error) is True
        assert is_token_limit_exceeded(retry_error) is False

        # Token limit error
        class BadRequestError(Exception):
            def __init__(self, message):
                super().__init__(message)
                self.code = "context_length_exceeded"
                self.type = "invalid_request_error"

        BadRequestError.__module__ = "openai.error"
        token_error = BadRequestError("context_length_exceeded")
        assert is_token_limit_exceeded(token_error, "openai:gpt-4") is True

        # Non-retryable error
        auth_error = Exception("Invalid API key")
        assert is_retryable_api_error(auth_error) is False
        assert is_token_limit_exceeded(auth_error) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
