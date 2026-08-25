"""Lifecycle-managed production resources for Abundance."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from abundance_research.application.engine import AbundanceResearchEngine
from abundance_research.bootstrap import build_research_engine
from abundance_research.persistence import (
    InMemoryResearchRunRepository,
    PostgresResearchRunRepository,
    ResearchRunRepository,
)
from abundance_research.settings import AbundanceSettings


@dataclass(slots=True)
class RuntimeResources:
    """Resources with the same lifecycle as the FastAPI process."""

    engine: AbundanceResearchEngine
    repository: ResearchRunRepository
    pool: AsyncConnectionPool[Any] | None = None


@asynccontextmanager
async def open_runtime(
    settings: AbundanceSettings,
    *,
    environment: Mapping[str, str] | None = None,
) -> AsyncIterator[RuntimeResources]:
    """Open optional PostgreSQL persistence and compile the graph once."""
    if settings.database_url is None:
        yield RuntimeResources(
            engine=build_research_engine(settings=settings, environment=environment),
            repository=InMemoryResearchRunRepository(),
        )
        return

    pool: AsyncConnectionPool[Any] = AsyncConnectionPool(
        settings.database_url.get_secret_value(),
        min_size=settings.database_pool_min_size,
        max_size=settings.database_pool_max_size,
        open=False,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
    )
    await pool.open(wait=True)
    try:
        repository = PostgresResearchRunRepository(pool)
        if not await repository.ready():
            raise RuntimeError(
                "PostgreSQL schema is missing; run python -m abundance_research.migrations"
            )
        checkpointer = AsyncPostgresSaver(pool)
        yield RuntimeResources(
            engine=build_research_engine(
                settings=settings,
                environment=environment,
                checkpointer=checkpointer,
            ),
            repository=repository,
            pool=pool,
        )
    finally:
        await pool.close()
