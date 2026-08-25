"""Typed runtime settings for the Abundance research workflow."""

from __future__ import annotations

import os
from enum import Enum
from typing import Any

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field


class SearchProvider(str, Enum):
    """Search capabilities supported by the workflow."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    TAVILY = "tavily"
    NONE = "none"


class MCPServerSettings(BaseModel):
    """Optional Model Context Protocol server configuration."""

    url: str | None = None
    tools: list[str] | None = None
    auth_required: bool = False


class AbundanceSettings(BaseModel):
    """Validated settings shared by planning, investigation, and synthesis."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    max_structured_output_retries: int = Field(default=3, ge=1, le=10)
    api_retry_attempts: int = Field(default=3, ge=1, le=10)
    api_retry_initial_delay: float = Field(default=1.0, ge=0.1, le=10.0)
    api_retry_max_delay: float = Field(default=60.0, ge=1.0, le=300.0)
    api_retry_exponential_base: float = Field(default=2.0, ge=1.5, le=3.0)

    allow_clarification: bool = True
    max_concurrent_research_units: int = Field(default=3, ge=1, le=20)
    max_coordination_iterations: int = Field(default=3, ge=1, le=10)
    max_search_iterations: int = Field(default=4, ge=1, le=30)
    max_search_results: int = Field(default=4, ge=1, le=20)
    search_provider: SearchProvider = SearchProvider.TAVILY

    summarization_model: str = "openrouter:inception/mercury-2"
    summarization_model_max_tokens: int = Field(default=8192, ge=256)
    research_model: str = "openrouter:inception/mercury-2"
    research_model_max_tokens: int = Field(default=10000, ge=256)
    evidence_review_model: str = "openrouter:inception/mercury-2"
    evidence_review_model_max_tokens: int = Field(default=8192, ge=256)
    final_report_model: str = "openrouter:inception/mercury-2"
    final_report_model_max_tokens: int = Field(default=30000, ge=256)
    max_content_length: int = Field(default=50000, ge=1000, le=200000)

    enable_reasoning: bool = True
    reasoning_effort: str = "high"
    reasoning_max_tokens: int = Field(default=8000, ge=1024, le=32000)
    exclude_reasoning_from_output: bool = False
    enable_prompt_caching: bool = True

    mcp_config: MCPServerSettings | None = None
    mcp_prompt: str | None = None

    @classmethod
    def from_runnable_config(
        cls,
        config: RunnableConfig | None = None,
    ) -> AbundanceSettings:
        """Merge graph configuration with optional environment overrides."""
        configurable = config.get("configurable", {}) if config else {}
        values: dict[str, Any] = {}
        for field_name in cls.model_fields:
            abundance_env = os.environ.get(f"ABUNDANCE_{field_name.upper()}")
            legacy_env = os.environ.get(field_name.upper())
            value = abundance_env or legacy_env or configurable.get(field_name)
            if value is not None:
                values[field_name] = value
        return cls(**values)
