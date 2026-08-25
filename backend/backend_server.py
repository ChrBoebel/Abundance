#!/usr/bin/env python3
"""FastAPI and SSE entrypoint for Abundance research runs."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import re
import sys
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

backend_root = Path(__file__).parent
load_dotenv(backend_root / ".env")
sys.path.insert(0, str(backend_root / "src"))

from abundance_research import __version__
from abundance_research.adapters import ModelCatalog
from abundance_research.application.contracts import ResearchCommand
from abundance_research.application.engine import AbundanceResearchEngine
from abundance_research.application.errors import FailureCode, ResearchFailure
from abundance_research.domain import Inquiry, ResearchMode
from abundance_research.events import ResearchEvent
from abundance_research.observability import configure_logging
from abundance_research.persistence import (
    InMemoryResearchRunRepository,
    ResearchRunRepository,
    RunFeedback,
)
from abundance_research.runtime import open_runtime
from abundance_research.settings import AbundanceSettings

EngineFactory = Callable[[], Any]
logger = logging.getLogger(__name__)
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")
_SHARE_TOKEN = re.compile(r"^[A-Za-z0-9_-]{32,100}$")


class ResearchRunRequest(BaseModel):
    """Public request contract for a new Abundance research run."""

    inquiry: str = Field(min_length=3, max_length=8000)
    model: str = "mercury"
    mode: ResearchMode = ResearchMode.BALANCED

    @field_validator("inquiry")
    @classmethod
    def normalize_inquiry(cls, value: str) -> str:
        """Reject whitespace-only inquiries and normalize surrounding space."""
        normalized = value.strip()
        if len(normalized) < 3:
            raise ValueError("inquiry must contain at least three characters")
        return normalized

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        """Reject arbitrary provider model IDs at the HTTP boundary."""
        try:
            ModelCatalog.resolve(value)
        except ResearchFailure as exc:
            raise ValueError(exc.public_message) from exc
        return value


def encode_sse(event: ResearchEvent, sequence: int) -> bytes:
    """Encode one JSON event with a monotonic SSE identifier."""
    payload = event.model_dump_json(exclude_none=True)
    return f"id: {sequence}\ndata: {payload}\n\n".encode()


async def stream_research_run(
    engine: AbundanceResearchEngine,
    command: ResearchCommand,
    request: Request,
    repository: ResearchRunRepository,
) -> AsyncIterator[bytes]:
    """Bridge application events to cancellable HTTP streaming with heartbeats."""
    accepted = ResearchEvent(
        type="run.accepted",
        message="Recherche angenommen",
        data={"run_id": command.run_id},
    )
    sequence = 1
    yield encode_sse(accepted, sequence)
    await asyncio.sleep(0)

    event_stream = engine.stream(command)
    pending_event: asyncio.Future[ResearchEvent] | None = None
    settled = False
    try:
        while True:
            if pending_event is None:
                pending_event = asyncio.ensure_future(anext(event_stream))
            done, _ = await asyncio.wait({pending_event}, timeout=15)
            if await request.is_disconnected():
                return
            if not done:
                yield b": heartbeat\n\n"
                await asyncio.sleep(0)
                continue
            try:
                event = pending_event.result()
            except StopAsyncIteration:
                return
            pending_event = None
            if event.type == "report.completed":
                report = event.data.get("report")
                evaluation = event.data.get("evaluation")
                if isinstance(report, dict) and isinstance(evaluation, dict):
                    await repository.complete(command.run_id, report, evaluation)
            elif event.type == "run.metrics":
                metrics = event.data.get("metrics")
                if isinstance(metrics, dict):
                    await repository.record_metrics(command.run_id, metrics)
            elif event.type == "run.failed":
                settled = True
                await repository.fail(
                    command.run_id,
                    {
                        "code": event.data.get("code", "internal_error"),
                        "message": event.message,
                    },
                )
            elif event.type == "run.completed":
                settled = True
            sequence += 1
            yield encode_sse(event, sequence)
            await asyncio.sleep(0)
    finally:
        if pending_event is not None and not pending_event.done():
            pending_event.cancel()
            await asyncio.gather(pending_event, return_exceptions=True)
        await event_stream.aclose()
        if not settled:
            await repository.cancel(command.run_id)


def require_internal_auth(request: Request, settings: AbundanceSettings) -> None:
    """Authenticate one internal endpoint without retaining the bearer token."""
    expected_token = settings.internal_api_token
    if expected_token is None:
        return
    authorization = request.headers.get("authorization", "")
    supplied = authorization.removeprefix("Bearer ")
    expected_digest = hashlib.sha256(expected_token.get_secret_value().encode()).digest()
    supplied_digest = hashlib.sha256(supplied.encode()).digest()
    if not authorization.startswith("Bearer ") or not hmac.compare_digest(
        supplied_digest,
        expected_digest,
    ):
        raise HTTPException(status_code=401, detail="Unauthorized")


def create_app(
    engine_factory: EngineFactory | None = None,
    *,
    settings: AbundanceSettings | None = None,
    repository: ResearchRunRepository | None = None,
) -> FastAPI:
    """Create an API instance with an injectable application composition root."""
    runtime = settings or AbundanceSettings.from_environment()
    configure_logging(runtime.log_level)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if engine_factory is not None:
            yield
            return
        async with open_runtime(runtime) as resources:
            application.state.engine = resources.engine
            application.state.repository = resources.repository
            yield

    application = FastAPI(
        title="Abundance Research API",
        description="Evidence-oriented research orchestration for Abundance.",
        version=__version__,
        lifespan=lifespan,
    )
    application.state.engine = None
    application.state.repository = repository or InMemoryResearchRunRepository()
    application.add_middleware(
        CORSMiddleware,
        allow_origins=runtime.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Last-Event-ID"],
        expose_headers=["X-Request-ID", "X-Run-ID"],
    )

    @application.middleware("http")
    async def correlation_header(request: Request, call_next):
        started = time.perf_counter()
        supplied = request.headers.get("x-request-id", "")
        request_id = supplied if _REQUEST_ID.fullmatch(supplied) else f"req-{uuid4().hex}"
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "HTTP request failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                    "status_code": 500,
                },
            )
            raise
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "HTTP request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "status_code": response.status_code,
            },
        )
        return response

    @application.post("/api/v1/research-runs/stream")
    async def research_run_stream(payload: ResearchRunRequest, request: Request):
        require_internal_auth(request, runtime)
        run_id = f"run-{uuid4().hex}"
        inquiry = Inquiry(question=payload.inquiry, mode=payload.mode)
        command = ResearchCommand(
            run_id=run_id,
            inquiry=inquiry,
            model=payload.model,
            mode=payload.mode,
        )
        try:
            engine = engine_factory() if engine_factory is not None else request.app.state.engine
            if engine is None:
                raise ResearchFailure(
                    FailureCode.CONFIGURATION,
                    "Der Recherchedienst ist noch nicht bereit.",
                )
        except ResearchFailure as exc:
            status = 503 if exc.code is FailureCode.CONFIGURATION else 500
            raise HTTPException(
                status_code=status,
                detail={"code": exc.code.value, "message": exc.public_message},
            ) from exc

        run_repository: ResearchRunRepository = request.app.state.repository
        await run_repository.create(command)
        return StreamingResponse(
            stream_research_run(engine, command, request, run_repository),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-Run-ID": run_id,
            },
        )

    @application.get("/api/v1/research-runs")
    async def list_research_runs(request: Request, limit: int = 50):
        require_internal_auth(request, runtime)
        bounded_limit = max(1, min(limit, 100))
        items = await request.app.state.repository.list(limit=bounded_limit)
        return {"items": [item.model_dump(mode="json") for item in items]}

    @application.get("/api/v1/research-runs/{run_id}")
    async def get_research_run(run_id: str, request: Request):
        require_internal_auth(request, runtime)
        item = await request.app.state.repository.get(run_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Research run not found")
        return item.model_dump(mode="json")

    @application.post("/api/v1/research-runs/{run_id}/feedback")
    async def add_research_feedback(run_id: str, feedback: RunFeedback, request: Request):
        require_internal_auth(request, runtime)
        if feedback.run_id != run_id:
            raise HTTPException(status_code=422, detail="Run identifier mismatch")
        try:
            feedback_id = await request.app.state.repository.add_feedback(feedback)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Research run not found") from exc
        return {"id": feedback_id}

    @application.post("/api/v1/research-runs/{run_id}/shares")
    async def share_research_run(run_id: str, request: Request):
        require_internal_auth(request, runtime)
        try:
            token = await request.app.state.repository.create_share(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Completed research run not found") from exc
        return {"token": token, "url": f"{runtime.share_base_url}/{token}"}

    @application.get("/api/v1/shared/{token}")
    async def get_shared_research(token: str, request: Request, response: Response):
        if not _SHARE_TOKEN.fullmatch(token):
            raise HTTPException(status_code=404, detail="Shared research not found")
        item = await request.app.state.repository.get_shared(token)
        if item is None:
            raise HTTPException(status_code=404, detail="Shared research not found")
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        # A capability link exposes the completed public report, not the
        # original inquiry, internal metrics/cost, provider errors, or IDs.
        return {
            "report": item.report,
            "evaluation": item.evaluation,
            "created_at": item.created_at.isoformat(),
        }

    @application.get("/health")
    async def health():
        return {"status": "healthy", "version": __version__}

    @application.get("/ready")
    async def readiness(request: Request):
        try:
            engine = engine_factory() if engine_factory is not None else request.app.state.engine
            if engine is None or not await request.app.state.repository.ready():
                raise ResearchFailure(
                    FailureCode.CONFIGURATION,
                    "Persistence or provider setup is incomplete",
                )
        except ResearchFailure as exc:
            raise HTTPException(
                status_code=503,
                detail={"code": exc.code.value, "message": exc.public_message},
            ) from exc
        return {"status": "ready", "version": __version__}

    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
