import os

import pytest
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from abundance_research.application.contracts import ResearchCommand
from abundance_research.domain import Inquiry, ResearchMode
from abundance_research.migrations import migrate
from abundance_research.persistence import PostgresResearchRunRepository


@pytest.mark.integration
async def test_postgres_migration_and_repository_round_trip() -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    first = await migrate(database_url)
    second = await migrate(database_url)
    assert first == ["0001_research_platform.up.sql"]
    assert second == []

    pool = AsyncConnectionPool(
        database_url,
        min_size=1,
        max_size=2,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )
    await pool.open(wait=True)
    try:
        repository = PostgresResearchRunRepository(pool)
        inquiry = Inquiry(question="Does PostgreSQL retain this report?")
        command = ResearchCommand(
            run_id="run-postgres-integration",
            inquiry=inquiry,
            model="mercury",
            mode=ResearchMode.BALANCED,
        )
        await repository.create(command)
        await repository.complete(
            command.run_id,
            {"title": "Persisted report", "claims": []},
            {"claim_evidence_coverage": 1.0},
        )
        token = await repository.create_share(command.run_id)

        stored = await repository.get(command.run_id)
        shared = await repository.get_shared(token)
        assert await repository.ready()
        assert stored is not None
        assert stored.report is not None
        assert stored.report["title"] == "Persisted report"
        assert shared == stored
    finally:
        await pool.close()
