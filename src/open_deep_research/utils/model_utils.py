"""Model initialization and configuration utilities."""

import os
from datetime import datetime
from typing import Optional

from langchain.chat_models import init_chat_model
from langchain_core.messages import MessageLikeRepresentation, AIMessage
from langchain_openai import ChatOpenAI


##########################
# Model Initialization
##########################

def strip_openrouter_prefix(model_name: str) -> str:
    """Strip 'openrouter:' prefix from model name if present."""
    if isinstance(model_name, str) and model_name.startswith("openrouter:"):
        return model_name.replace("openrouter:", "", 1)
    return model_name


def prepare_model_config(config: dict, reasoning_config: Optional[dict] = None) -> dict:
    """Prepare model config by stripping openrouter: prefix and adding reasoning.

    Args:
        config: Base model configuration dictionary
        reasoning_config: Optional reasoning configuration to add

    Returns:
        Prepared configuration dictionary
    """
    config = dict(config)  # Make a copy
    if "model" in config:
        config["model"] = strip_openrouter_prefix(config["model"])

    # Add reasoning config if provided
    if reasoning_config:
        config["reasoning_config"] = reasoning_config

    return config


def build_reasoning_config(model_name: str, enable_reasoning: bool, reasoning_effort: str, reasoning_max_tokens: int, exclude_reasoning: bool) -> dict:
    """Build OpenRouter reasoning configuration based on model provider.

    Args:
        model_name: The model identifier (e.g., "openrouter:deepseek/...")
        enable_reasoning: Whether to enable reasoning tokens
        reasoning_effort: Effort level for OpenAI-compatible models ("high"/"medium"/"low")
        reasoning_max_tokens: Max reasoning tokens for Anthropic/Gemini models
        exclude_reasoning: Whether to hide reasoning from output

    Returns:
        Dictionary with reasoning configuration for OpenRouter API
    """
    if not enable_reasoning:
        return {}

    model_lower = model_name.lower()

    # Detect provider from model name
    is_openai_style = any(provider in model_lower for provider in ["openai", "gpt", "o1", "o3", "o4", "grok"])
    is_anthropic_style = "anthropic" in model_lower or "claude" in model_lower
    is_gemini_style = "gemini" in model_lower or "google" in model_lower

    reasoning_config = {
        "enabled": True,
        "exclude": exclude_reasoning
    }

    # Add provider-specific reasoning parameters
    if is_openai_style:
        reasoning_config["effort"] = reasoning_effort
    elif is_anthropic_style or is_gemini_style:
        reasoning_config["max_tokens"] = reasoning_max_tokens

    return reasoning_config


def init_chat_model_wrapper(configurable_fields=None, **kwargs):
    """Wrapper that creates ChatOpenAI with OpenRouter support including reasoning.

    Args:
        configurable_fields: Tuple of field names that can be configured at runtime
        **kwargs: Additional arguments passed to model initialization

    Returns:
        Configured ChatOpenAI model that routes to OpenRouter
    """
    if configurable_fields:
        # Get API key or use placeholder
        api_key = os.getenv("OPENROUTER_API_KEY") or "placeholder"

        # Create base model pointing to OpenRouter
        base_model = ChatOpenAI(
            model="deepseek/deepseek-v3.2-exp",
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            **kwargs
        ).configurable_fields(
            model_name=dict(id="model", name="Model", description="Model to use"),
            max_tokens=dict(id="max_tokens", name="Max Tokens"),
            openai_api_key=dict(id="api_key", name="API Key"),
        )

        return base_model
    else:
        # Direct initialization without configurable fields
        model_name = kwargs.get("model", "")
        if model_name.startswith("openrouter:"):
            actual_model = strip_openrouter_prefix(model_name)
            api_key = kwargs.get("api_key") or os.getenv("OPENROUTER_API_KEY")

            # Extract reasoning config if provided
            reasoning_config = kwargs.pop("reasoning_config", None)

            # Build model kwargs
            model_kwargs = {
                "model": actual_model,
                "base_url": "https://openrouter.ai/api/v1",
                "api_key": api_key,
                **{k: v for k, v in kwargs.items() if k not in ["model", "api_key"]}
            }

            # Add reasoning to model_kwargs if provided
            if reasoning_config:
                model_kwargs["model_kwargs"] = {"reasoning": reasoning_config}

            return ChatOpenAI(**model_kwargs)
        else:
            return init_chat_model(configurable_fields=configurable_fields, **kwargs)


##########################
# API Keys
##########################

def get_api_key_for_model(model_name: str, config):
    """Get API key for a specific model from environment or config."""
    should_get_from_config = os.getenv("GET_API_KEYS_FROM_CONFIG", "false")
    model_name = model_name.lower()
    if should_get_from_config.lower() == "true":
        api_keys = config.get("configurable", {}).get("apiKeys", {})
        if not api_keys:
            return None
        if model_name.startswith("openai:"):
            return api_keys.get("OPENAI_API_KEY")
        elif model_name.startswith("anthropic:"):
            return api_keys.get("ANTHROPIC_API_KEY")
        elif model_name.startswith("google"):
            return api_keys.get("GOOGLE_API_KEY")
        elif model_name.startswith("openrouter:"):
            return api_keys.get("OPENROUTER_API_KEY")
        return None
    else:
        if model_name.startswith("openai:"):
            return os.getenv("OPENAI_API_KEY")
        elif model_name.startswith("anthropic:"):
            return os.getenv("ANTHROPIC_API_KEY")
        elif model_name.startswith("google"):
            return os.getenv("GOOGLE_API_KEY")
        elif model_name.startswith("openrouter:"):
            return os.getenv("OPENROUTER_API_KEY")
        return None


def get_tavily_api_key(config):
    """Get Tavily API key from environment or config."""
    should_get_from_config = os.getenv("GET_API_KEYS_FROM_CONFIG", "false")
    if should_get_from_config.lower() == "true":
        api_keys = config.get("configurable", {}).get("apiKeys", {})
        if not api_keys:
            return None
        return api_keys.get("TAVILY_API_KEY")
    else:
        return os.getenv("TAVILY_API_KEY")


##########################
# Token Limits
##########################

# NOTE: This may be out of date or not applicable to your models. Please update this as needed.
MODEL_TOKEN_LIMITS = {
    "openai:gpt-4.1-mini": 1047576,
    "openai:gpt-4.1-nano": 1047576,
    "openai:gpt-4.1": 1047576,
    "openai:gpt-4o-mini": 128000,
    "openai:gpt-4o": 128000,
    "openai:o4-mini": 200000,
    "openai:o3-mini": 200000,
    "openai:o3": 200000,
    "openai:o3-pro": 200000,
    "openai:o1": 200000,
    "openai:o1-pro": 200000,
    "anthropic:claude-opus-4": 200000,
    "anthropic:claude-sonnet-4": 200000,
    "anthropic:claude-3-7-sonnet": 200000,
    "anthropic:claude-3-5-sonnet": 200000,
    "anthropic:claude-3-5-haiku": 200000,
    "google:gemini-1.5-pro": 2097152,
    "google:gemini-1.5-flash": 1048576,
    "google:gemini-pro": 32768,
    "cohere:command-r-plus": 128000,
    "cohere:command-r": 128000,
    "cohere:command-light": 4096,
    "cohere:command": 4096,
    "mistral:mistral-large": 32768,
    "mistral:mistral-medium": 32768,
    "mistral:mistral-small": 32768,
    "mistral:mistral-7b-instruct": 32768,
    "ollama:codellama": 16384,
    "ollama:llama2:70b": 4096,
    "ollama:llama2:13b": 4096,
    "ollama:llama2": 4096,
    "ollama:mistral": 32768,
    "bedrock:us.amazon.nova-premier-v1:0": 1000000,
    "bedrock:us.amazon.nova-pro-v1:0": 300000,
    "bedrock:us.amazon.nova-lite-v1:0": 300000,
    "bedrock:us.amazon.nova-micro-v1:0": 128000,
    "bedrock:us.anthropic.claude-3-7-sonnet-20250219-v1:0": 200000,
    "bedrock:us.anthropic.claude-sonnet-4-20250514-v1:0": 200000,
    "bedrock:us.anthropic.claude-opus-4-20250514-v1:0": 200000,
    "anthropic.claude-opus-4-1-20250805-v1:0": 200000,
}


def get_model_token_limit(model_string):
    """Look up the token limit for a specific model.

    Args:
        model_string: The model identifier string to look up

    Returns:
        Token limit as integer if found, None if model not in lookup table
    """
    # Search through known model token limits
    for model_key, token_limit in MODEL_TOKEN_LIMITS.items():
        if model_key in model_string:
            return token_limit

    # Model not found in lookup table
    return None


def remove_up_to_last_ai_message(messages: list[MessageLikeRepresentation]) -> list[MessageLikeRepresentation]:
    """Truncate message history by removing up to the last AI message.

    This is useful for handling token limit exceeded errors by removing recent context.

    Args:
        messages: List of message objects to truncate

    Returns:
        Truncated message list up to (but not including) the last AI message
    """
    # Search backwards through messages to find the last AI message
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], AIMessage):
            # Return everything up to (but not including) the last AI message
            return messages[:i]

    # No AI messages found, return original list
    return messages


##########################
# Misc Utils
##########################

def get_today_str() -> str:
    """Get current date formatted for display in prompts and outputs.

    Returns:
        Human-readable date string in format like 'Mon Jan 15, 2024'
    """
    now = datetime.now()
    return f"{now:%a} {now:%b} {now.day}, {now:%Y}"


def create_cached_message(message_class, content: str, enable_caching: bool = True):
    """Create a message with prompt caching enabled for OpenRouter.

    Args:
        message_class: Message class (SystemMessage or HumanMessage)
        content: Message content
        enable_caching: Whether to enable caching for this message

    Returns:
        Message instance with cache_control if caching is enabled
    """
    if not enable_caching:
        return message_class(content=content)

    # Add cache_control breakpoint for OpenRouter/Anthropic-style caching
    return message_class(
        content=content,
        additional_kwargs={"cache_control": {"type": "ephemeral"}}
    )


def get_config_value(value):
    """Extract value from configuration, handling enums and None values."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    elif isinstance(value, dict):
        return value
    else:
        return value.value
