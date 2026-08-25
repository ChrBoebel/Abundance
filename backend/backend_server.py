#!/usr/bin/env python3
"""FastAPI and SSE entrypoint for Abundance research runs."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import re
import sys
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
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
from abundance_research.bootstrap import get_research_engine
from abundance_research.domain import Inquiry, ResearchMode
from abundance_research.events import ResearchEvent
from abundance_research.settings import AbundanceSettings

EngineFactory = Callable[[], AbundanceResearchEngine]
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")


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
            sequence += 1
            yield encode_sse(event, sequence)
            await asyncio.sleep(0)
    finally:
        if pending_event is not None and not pending_event.done():
            pending_event.cancel()
            await asyncio.gather(pending_event, return_exceptions=True)
        await event_stream.aclose()


def create_app(
    engine_factory: EngineFactory = get_research_engine,
    *,
    settings: AbundanceSettings | None = None,
) -> FastAPI:
    """Create an API instance with an injectable application composition root."""
    runtime = settings or AbundanceSettings.from_environment()
    application = FastAPI(
        title="Abundance Research API",
        description="Evidence-oriented research orchestration for Abundance.",
        version=__version__,
    )
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
        supplied = request.headers.get("x-request-id", "")
        request_id = supplied if _REQUEST_ID.fullmatch(supplied) else f"req-{uuid4().hex}"
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @application.post("/api/v1/research-runs/stream")
    async def research_run_stream(payload: ResearchRunRequest, request: Request):
        expected_token = runtime.internal_api_token
        if expected_token is not None:
            authorization = request.headers.get("authorization", "")
            supplied = authorization.removeprefix("Bearer ")
            expected_digest = hashlib.sha256(
                expected_token.get_secret_value().encode()
            ).digest()
            supplied_digest = hashlib.sha256(supplied.encode()).digest()
            if not authorization.startswith("Bearer ") or not hmac.compare_digest(
                supplied_digest,
                expected_digest,
            ):
                raise HTTPException(status_code=401, detail="Unauthorized")
        run_id = f"run-{uuid4().hex}"
        inquiry = Inquiry(question=payload.inquiry, mode=payload.mode)
        command = ResearchCommand(
            run_id=run_id,
            inquiry=inquiry,
            model=payload.model,
            mode=payload.mode,
        )
        try:
            engine = engine_factory()
        except ResearchFailure as exc:
            status = 503 if exc.code is FailureCode.CONFIGURATION else 500
            raise HTTPException(
                status_code=status,
                detail={"code": exc.code.value, "message": exc.public_message},
            ) from exc

        return StreamingResponse(
            stream_research_run(engine, command, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-Run-ID": run_id,
            },
        )

    @application.get("/health")
    async def health():
        return {"status": "healthy", "version": __version__}

    @application.get("/ready")
    async def readiness():
        try:
            engine_factory()
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
