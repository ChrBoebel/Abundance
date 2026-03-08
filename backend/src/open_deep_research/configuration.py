"""Configuration management for the Open Deep Research system."""

import os
from enum import Enum
from typing import Any, List, Optional

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field


class SearchAPI(Enum):
    """Enumeration of available search API providers."""
    
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    TAVILY = "tavily"
    NONE = "none"

class MCPConfig(BaseModel):
    """Configuration for Model Context Protocol (MCP) servers."""
    
    url: Optional[str] = Field(
        default=None,
        optional=True,
    )
    """The URL of the MCP server"""
    tools: Optional[List[str]] = Field(
        default=None,
        optional=True,
    )
    """The tools to make available to the LLM"""
    auth_required: Optional[bool] = Field(
        default=False,
        optional=True,
    )
    """Whether the MCP server requires authentication"""

class Configuration(BaseModel):
    """Main configuration class for the Deep Research agent."""
    
    # General Configuration
    max_structured_output_retries: int = Field(
        default=3,
        metadata={
            "x_oap_ui_config": {
                "type": "number",
                "default": 3,
                "min": 1,
                "max": 10,
                "description": "Maximum number of retries for structured output calls from models"
            }
        }
    )
    api_retry_attempts: int = Field(
        default=3,
        metadata={
            "x_oap_ui_config": {
                "type": "number",
                "default": 3,
                "min": 1,
                "max": 10,
                "description": "Maximum number of retry attempts for API rate limiting and server errors"
            }
        }
    )
    api_retry_initial_delay: float = Field(
        default=1.0,
        metadata={
            "x_oap_ui_config": {
                "type": "number",
                "default": 1.0,
                "min": 0.1,
                "max": 10.0,
                "description": "Initial delay in seconds before first retry (exponential backoff base)"
            }
        }
    )
    api_retry_max_delay: float = Field(
        default=60.0,
        metadata={
            "x_oap_ui_config": {
                "type": "number",
                "default": 60.0,
                "min": 1.0,
                "max": 300.0,
                "description": "Maximum delay in seconds between retries (exponential backoff cap)"
            }
        }
    )
    api_retry_exponential_base: float = Field(
        default=2.0,
        metadata={
            "x_oap_ui_config": {
                "type": "number",
                "default": 2.0,
                "min": 1.5,
                "max": 3.0,
                "description": "Exponential base for backoff calculation (delay = initial * base^attempt)"
            }
        }
    )
    allow_clarification: bool = Field(
        default=True,
        metadata={
            "x_oap_ui_config": {
                "type": "boolean",
                "default": True,
                "description": "Whether to allow the researcher to ask the user clarifying questions before starting research"
            }
        }
    )
    max_concurrent_research_units: int = Field(
        default=10,
        metadata={
            "x_oap_ui_config": {
                "type": "slider",
                "default": 10,
                "min": 1,
                "max": 20,
                "step": 1,
                "description": "Maximum number of research units to run concurrently. This will allow the researcher to use multiple sub-agents to conduct research. Note: with more concurrency, you may run into rate limits."
            }
        }
    )
    # Research Configuration
    search_api: SearchAPI = Field(
        default=SearchAPI.TAVILY,
        metadata={
            "x_oap_ui_config": {
                "type": "select",
                "default": "tavily",
                "description": "Search API to use for research. NOTE: Make sure your Researcher Model supports the selected search API.",
                "options": [
                    {"label": "Tavily", "value": SearchAPI.TAVILY.value},
                    {"label": "OpenAI Native Web Search", "value": SearchAPI.OPENAI.value},
                    {"label": "Anthropic Native Web Search", "value": SearchAPI.ANTHROPIC.value},
                    {"label": "None", "value": SearchAPI.NONE.value}
                ]
            }
        }
    )
    max_researcher_iterations: int = Field(
        default=3,
        metadata={
            "x_oap_ui_config": {
                "type": "slider",
                "default": 4,
                "min": 1,
                "max": 10,
                "step": 1,
                "description": "Maximum number of research iterations for the Research Supervisor. This is the number of times the Research Supervisor will reflect on the research and ask follow-up questions."
            }
        }
    )
    max_react_tool_calls: int = Field(
        default=4,
        metadata={
            "x_oap_ui_config": {
                "type": "slider",
                "default": 8,
                "min": 1,
                "max": 30,
                "step": 1,
                "description": "Maximum number of tool calling iterations to make in a single researcher step."
            }
        }
    )
    max_search_results: int = Field(
        default=4,
        metadata={
            "x_oap_ui_config": {
                "type": "slider",
                "default": 7,
                "min": 3,
                "max": 20,
                "step": 1,
                "description": "Maximum number of search results to return per query from Tavily. Higher values provide more sources but increase token costs and processing time."
            }
        }
    )
    # Model Configuration
    summarization_model: str = Field(
        default="openrouter:inception/mercury-2",
        metadata={
            "x_oap_ui_config": {
                "type": "text",
                "default": "openrouter:inception/mercury-2",
                "description": "Model for summarizing research results from Tavily search results"
            }
        }
    )
    summarization_model_max_tokens: int = Field(
        default=8192,
        metadata={
            "x_oap_ui_config": {
                "type": "number",
                "default": 8192,
                "description": "Maximum output tokens for summarization model"
            }
        }
    )
    max_content_length: int = Field(
        default=50000,
        metadata={
            "x_oap_ui_config": {
                "type": "number",
                "default": 50000,
                "min": 1000,
                "max": 200000,
                "description": "Maximum character length for webpage content before summarization"
            }
        }
    )
    research_model: str = Field(
        default="openrouter:inception/mercury-2",
        metadata={
            "x_oap_ui_config": {
                "type": "text",
                "default": "openrouter:inception/mercury-2",
                "description": "Model for conducting research. NOTE: Make sure your Researcher Model supports the selected search API."
            }
        }
    )
    research_model_max_tokens: int = Field(
        default=10000,
        metadata={
            "x_oap_ui_config": {
                "type": "number",
                "default": 10000,
                "description": "Maximum output tokens for research model"
            }
        }
    )
    compression_model: str = Field(
        default="openrouter:inception/mercury-2",
        metadata={
            "x_oap_ui_config": {
                "type": "text",
                "default": "openrouter:inception/mercury-2",
                "description": "Model for compressing research findings from sub-agents. NOTE: Make sure your Compression Model supports the selected search API."
            }
        }
    )
    compression_model_max_tokens: int = Field(
        default=8192,
        metadata={
            "x_oap_ui_config": {
                "type": "number",
                "default": 8192,
                "description": "Maximum output tokens for compression model"
            }
        }
    )
    final_report_model: str = Field(
        default="openrouter:inception/mercury-2",
        metadata={
            "x_oap_ui_config": {
                "type": "text",
                "default": "openrouter:inception/mercury-2",
                "description": "Model for writing the final report from all research findings"
            }
        }
    )
    final_report_model_max_tokens: int = Field(
        default=30000,
        metadata={
            "x_oap_ui_config": {
                "type": "number",
                "default": 30000,
                "description": "Maximum output tokens for final report model"
            }
        }
    )
    # Reasoning Configuration (OpenRouter Extended Thinking)
    enable_reasoning: bool = Field(
        default=True,
        metadata={
            "x_oap_ui_config": {
                "type": "boolean",
                "default": True,
                "description": "Enable OpenRouter reasoning/extended thinking for improved research quality"
            }
        }
    )
    reasoning_effort: str = Field(
        default="high",
        metadata={
            "x_oap_ui_config": {
                "type": "select",
                "default": "high",
                "description": "Reasoning effort level for OpenAI-compatible models (o-series, GPT-5, Grok)",
                "options": [
                    {"label": "High", "value": "high"},
                    {"label": "Medium", "value": "medium"},
                    {"label": "Low", "value": "low"}
                ]
            }
        }
    )
    reasoning_max_tokens: int = Field(
        default=8000,
        metadata={
            "x_oap_ui_config": {
                "type": "number",
                "default": 8000,
                "min": 1024,
                "max": 32000,
                "description": "Maximum reasoning tokens for Anthropic/Gemini models (Claude, Gemini). Must leave room for final response."
            }
        }
    )
    exclude_reasoning_from_output: bool = Field(
        default=False,
        metadata={
            "x_oap_ui_config": {
                "type": "boolean",
                "default": False,
                "description": "Hide reasoning tokens from output (keep reasoning internal). Set to True to reduce output verbosity."
            }
        }
    )
    # Prompt Caching Configuration
    enable_prompt_caching: bool = Field(
        default=True,
        metadata={
            "x_oap_ui_config": {
                "type": "boolean",
                "default": True,
                "description": "Enable OpenRouter prompt caching for cost reduction (50-90% savings on repeated prompts)"
            }
        }
    )
    # MCP server configuration
    mcp_config: Optional[MCPConfig] = Field(
        default=None,
        optional=True,
        metadata={
            "x_oap_ui_config": {
                "type": "mcp",
                "description": "MCP server configuration"
            }
        }
    )
    mcp_prompt: Optional[str] = Field(
        default=None,
        optional=True,
        metadata={
            "x_oap_ui_config": {
                "type": "text",
                "description": "Any additional instructions to pass along to the Agent regarding the MCP tools that are available to it."
            }
        }
    )


    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "Configuration":
        """Create a Configuration instance from a RunnableConfig."""
        configurable = config.get("configurable", {}) if config else {}
        field_names = list(cls.model_fields.keys())
        values: dict[str, Any] = {
            field_name: os.environ.get(field_name.upper(), configurable.get(field_name))
            for field_name in field_names
        }
        return cls(**{k: v for k, v in values.items() if v is not None})

    class Config:
        """Pydantic configuration."""
        
        arbitrary_types_allowed = True