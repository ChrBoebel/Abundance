"""Persistence ports and PostgreSQL adapters for durable research runs."""

from __future__ import annotations

import asyncio
import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, Field

from abundance_research.application.contracts import ResearchCommand


class StoredResearchRun(BaseModel):
    """Stable stored representation returned by run and share APIs."""

    id: str
    inquiry: dict[str, Any]
    model: str
    mode: str
    status: str
    report: dict[str, Any] | None = None
    evaluation: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None


class RunFeedback(BaseModel):
    """One explicit user judgment attached to a report or claim."""

    run_id: str
    claim_id: str | None = Field(default=None, max_length=100)
    rating: int = Field(ge=-1, le=1)
    note: str | None = Field(default=None, max_length=2000)


class ResearchRunRepository(Protocol):
    """Persistence boundary used by the HTTP streaming application."""

    async def create(self, command: ResearchCommand) -> None: ...

    async def complete(
        self,
        run_id: str,
        report: dict[str, Any],
        evaluation: dict[str, Any],
    ) -> None: ...

    async def record_metrics(self, run_id: str, metrics: dict[str, Any]) -> None: ...

    async def fail(self, run_id: str, error: dict[str, Any]) -> None: ...

    async def cancel(self, run_id: str) -> None: ...

    async def get(self, run_id: str) -> StoredResearchRun | None: ...

    async def list(self, *, limit: int = 50) -> list[StoredResearchRun]: ...

    async def add_feedback(self, feedback: RunFeedback) -> str: ...

    async def create_share(self, run_id: str) -> str: ...

    async def get_shared(self, token: str) -> StoredResearchRun | None: ...

    async def ready(self) -> bool: ...


class InMemoryResearchRunRepository:
    """Concurrency-safe development and test repository."""

    def __init__(self) -> None:
        self._runs: dict[str, StoredResearchRun] = {}
        self._feedback: dict[tuple[str, str], tuple[str, RunFeedback]] = {}
        self._shares: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def create(self, command: ResearchCommand) -> None:
        async with self._lock:
            self._runs[command.run_id] = StoredResearchRun(
                id=command.run_id,
                inquiry=command.inquiry.model_dump(mode="json"),
                model=command.model,
                mode=command.mode.value,
                status="running",
            )

    async def complete(
        self,
        run_id: str,
        report: dict[str, Any],
        evaluation: dict[str, Any],
    ) -> None:
        async with self._lock:
            current = self._runs[run_id]
            self._runs[run_id] = current.model_copy(
                update={
                    "status": "completed",
                    "report": report,
                    "evaluation": evaluation,
                    "completed_at": datetime.now(timezone.utc),
                }
            )

    async def record_metrics(self, run_id: str, metrics: dict[str, Any]) -> None:
        async with self._lock:
            current = self._runs[run_id]
            self._runs[run_id] = current.model_copy(update={"metrics": metrics})

    async def fail(self, run_id: str, error: dict[str, Any]) -> None:
        async with self._lock:
            current = self._runs[run_id]
            self._runs[run_id] = current.model_copy(
                update={
                    "status": "failed",
                    "error": error,
                    "completed_at": datetime.now(timezone.utc),
                }
            )

    async def cancel(self, run_id: str) -> None:
        async with self._lock:
            current = self._runs.get(run_id)
            if current is not None and current.status == "running":
                self._runs[run_id] = current.model_copy(
                    update={"status": "cancelled", "completed_at": datetime.now(timezone.utc)}
                )

    async def get(self, run_id: str) -> StoredResearchRun | None:
        async with self._lock:
            return self._runs.get(run_id)

    async def list(self, *, limit: int = 50) -> list[StoredResearchRun]:
        async with self._lock:
            values = sorted(self._runs.values(), key=lambda item: item.created_at, reverse=True)
            return values[:limit]

    async def add_feedback(self, feedback: RunFeedback) -> str:
        async with self._lock:
            run = self._runs.get(feedback.run_id)
            if run is None or run.status != "completed" or run.report is None:
                raise KeyError(feedback.run_id)
            if feedback.claim_id and not _report_has_claim(run.report, feedback.claim_id):
                raise KeyError(feedback.claim_id)
            key = (feedback.run_id, feedback.claim_id or "")
            existing = self._feedback.get(key)
            feedback_id = existing[0] if existing else f"feedback-{uuid4().hex}"
            self._feedback[key] = (feedback_id, feedback)
        return feedback_id

    async def create_share(self, run_id: str) -> str:
        async with self._lock:
            run = self._runs.get(run_id)
            if run is None or run.status != "completed":
                raise KeyError(run_id)
            token = secrets.token_urlsafe(32)
            self._shares[_token_digest(token)] = run_id
            return token

    async def get_shared(self, token: str) -> StoredResearchRun | None:
        async with self._lock:
            run_id = self._shares.get(_token_digest(token))
            return self._runs.get(run_id) if run_id is not None else None

    async def ready(self) -> bool:
        return True


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _report_has_claim(report: dict[str, Any], claim_id: str) -> bool:
    claims = report.get("claims")
    return isinstance(claims, list) and any(
        isinstance(claim, dict) and claim.get("id") == claim_id for claim in claims
    )


class PostgresResearchRunRepository:
    """Parameterized PostgreSQL implementation of the research-run boundary."""

    def __init__(self, pool: AsyncConnectionPool[Any]) -> None:
        self._pool = pool

    async def create(self, command: ResearchCommand) -> None:
        async with self._pool.connection() as connection:
            await connection.execute(
                """
                INSERT INTO abundance_research_runs (id, inquiry, model, mode, status)
                VALUES (%s, %s, %s, %s, 'running')
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    command.run_id,
                    Jsonb(command.inquiry.model_dump(mode="json")),
                    command.model,
                    command.mode.value,
                ),
            )

    async def complete(
        self,
        run_id: str,
        report: dict[str, Any],
        evaluation: dict[str, Any],
    ) -> None:
        async with self._pool.connection() as connection:
            await connection.execute(
                """
                UPDATE abundance_research_runs
                SET status = 'completed', report = %s, evaluation = %s,
                    completed_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (Jsonb(report), Jsonb(evaluation), run_id),
            )

    async def record_metrics(self, run_id: str, metrics: dict[str, Any]) -> None:
        async with self._pool.connection() as connection:
            await connection.execute(
                "UPDATE abundance_research_runs SET metrics = %s WHERE id = %s",
                (Jsonb(metrics), run_id),
            )

    async def fail(self, run_id: str, error: dict[str, Any]) -> None:
        await self._finish_with_status(run_id, "failed", error)

    async def cancel(self, run_id: str) -> None:
        await self._finish_with_status(run_id, "cancelled", None)

    async def _finish_with_status(
        self,
        run_id: str,
        status: str,
        error: dict[str, Any] | None,
    ) -> None:
        async with self._pool.connection() as connection:
            await connection.execute(
                """
                UPDATE abundance_research_runs
                SET status = %s, error = %s, completed_at = CURRENT_TIMESTAMP
                WHERE id = %s AND status = 'running'
                """,
                (status, Jsonb(error) if error is not None else None, run_id),
            )

    async def get(self, run_id: str) -> StoredResearchRun | None:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                "SELECT * FROM abundance_research_runs WHERE id = %s",
                (run_id,),
            )
            row = await cursor.fetchone()
        return StoredResearchRun.model_validate(row) if row else None

    async def list(self, *, limit: int = 50) -> list[StoredResearchRun]:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                "SELECT * FROM abundance_research_runs ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            rows = await cursor.fetchall()
        return [StoredResearchRun.model_validate(row) for row in rows]

    async def add_feedback(self, feedback: RunFeedback) -> str:
        feedback_id = f"feedback-{uuid4().hex}"
        async with self._pool.connection() as connection:
            lookup = await connection.execute(
                "SELECT status, report FROM abundance_research_runs WHERE id = %s",
                (feedback.run_id,),
            )
            run = await lookup.fetchone()
            if run is None or run["status"] != "completed" or run["report"] is None:
                raise KeyError(feedback.run_id)
            if feedback.claim_id and not _report_has_claim(run["report"], feedback.claim_id):
                raise KeyError(feedback.claim_id)
            cursor = await connection.execute(
                """
                INSERT INTO abundance_research_feedback
                    (id, run_id, claim_id, rating, note)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (run_id, claim_id) DO UPDATE
                SET rating = EXCLUDED.rating, note = EXCLUDED.note,
                    created_at = CURRENT_TIMESTAMP
                RETURNING id
                """,
                (
                    feedback_id,
                    feedback.run_id,
                    feedback.claim_id or "",
                    feedback.rating,
                    feedback.note,
                ),
            )
            row = await cursor.fetchone()
        if row is None:
            raise KeyError(feedback.run_id)
        return str(row["id"])

    async def create_share(self, run_id: str) -> str:
        token = secrets.token_urlsafe(32)
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                """
                INSERT INTO abundance_research_shares (token_digest, run_id)
                SELECT %s, id FROM abundance_research_runs
                WHERE id = %s AND status = 'completed'
                RETURNING run_id
                """,
                (_token_digest(token), run_id),
            )
            row = await cursor.fetchone()
        if row is None:
            raise KeyError(run_id)
        return token

    async def get_shared(self, token: str) -> StoredResearchRun | None:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                """
                SELECT run.* FROM abundance_research_runs AS run
                JOIN abundance_research_shares AS share ON share.run_id = run.id
                WHERE share.token_digest = %s AND share.revoked_at IS NULL
                """,
                (_token_digest(token),),
            )
            row = await cursor.fetchone()
        return StoredResearchRun.model_validate(row) if row else None

    async def ready(self) -> bool:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                "SELECT to_regclass('public.abundance_research_runs') AS relation"
            )
            row = await cursor.fetchone()
        return bool(row and row["relation"])
