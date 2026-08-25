"""Forward-only application and LangGraph checkpoint migrations."""

from __future__ import annotations

import importlib.resources

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection
from psycopg.rows import dict_row


async def migrate(database_url: str) -> list[str]:
    """Apply immutable SQL migrations and LangGraph checkpoint migrations."""
    applied: list[str] = []
    async with await AsyncConnection.connect(
        database_url,
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
    ) as connection:
        await connection.execute(
            "SELECT pg_advisory_lock(hashtext('abundance_schema_migrations'))"
        )
        try:
            await connection.execute(
                """
                CREATE TABLE IF NOT EXISTS abundance_schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor = await connection.execute("SELECT version FROM abundance_schema_migrations")
            existing = {str(row["version"]) for row in await cursor.fetchall()}
            package = importlib.resources.files(__package__)
            for resource in sorted(package.iterdir(), key=lambda item: item.name):
                if not resource.name.endswith(".up.sql") or resource.name in existing:
                    continue
                sql = resource.read_text(encoding="utf-8")
                async with connection.transaction():
                    await connection.execute(sql, prepare=False)
                    await connection.execute(
                        "INSERT INTO abundance_schema_migrations (version) VALUES (%s)",
                        (resource.name,),
                    )
                applied.append(resource.name)

            checkpointer = AsyncPostgresSaver(connection)
            await checkpointer.setup()
        finally:
            await connection.execute(
                "SELECT pg_advisory_unlock(hashtext('abundance_schema_migrations'))"
            )
    return applied
