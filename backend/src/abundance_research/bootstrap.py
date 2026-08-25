"""Composition root for the Abundance research application."""

from __future__ import annotations

import os
from collections.abc import Mapping
from functools import lru_cache
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver

from abundance_research.adapters import OpenRouterResearchModel, TavilyEvidenceSource
from abundance_research.application.engine import AbundanceResearchEngine
from abundance_research.settings import AbundanceSettings


def build_research_engine(
    *,
    settings: AbundanceSettings | None = None,
    environment: Mapping[str, str] | None = None,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> AbundanceResearchEngine:
    """Bind application ports to explicitly configured provider adapters."""
    runtime = settings or AbundanceSettings.from_environment(environment)
    source = environment if environment is not None else os.environ
    model = OpenRouterResearchModel(
        source.get("OPENROUTER_API_KEY", ""),
        base_url=runtime.openrouter_base_url,
        planning_tokens=runtime.planning_model_max_tokens,
        synthesis_tokens=runtime.synthesis_model_max_tokens,
        timeout_seconds=runtime.provider_timeout_seconds,
        max_retries=runtime.provider_max_retries,
    )
    evidence = TavilyEvidenceSource(
        source.get("TAVILY_API_KEY"),
        timeout_seconds=runtime.search_timeout_seconds,
        max_excerpt_chars=runtime.max_evidence_excerpt_chars,
    )
    return AbundanceResearchEngine(model, [evidence], model, checkpointer=checkpointer)


@lru_cache(maxsize=1)
def get_research_engine() -> AbundanceResearchEngine:
    """Create one stateless adapter set per API process."""
    return build_research_engine()
