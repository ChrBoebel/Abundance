"""Canonical, privacy-conscious observability contracts for research runs."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from abundance_research import __version__
from abundance_research.events import ResearchEvent

OBSERVABILITY_SCHEMA_VERSION = "1.0"
OPERATION_SIGNAL_TYPE = "observability.operation"


class RunOutcome(str, Enum):
    """Terminal outcomes recorded independently of transport events."""

    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ArtifactKind(str, Enum):
    """Versioned runtime inputs that can change AI behavior."""

    GRAPH = "graph"
    PROMPT = "prompt"
    MODEL = "model"
    DATASET = "dataset"


class ArtifactRevision(BaseModel):
    """Identify one behavior-affecting artifact without retaining its content."""

    kind: ArtifactKind
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=200)


class OperationKind(str, Enum):
    """External operation categories measured by the research graph."""

    MODEL = "model"
    SEARCH = "search"


class OperationOutcome(str, Enum):
    """Outcome of one logical provider invocation."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"


class OperationSpan(BaseModel):
    """Privacy-safe measurement for one model or search invocation."""

    schema_version: str = OBSERVABILITY_SCHEMA_VERSION
    span_id: str = Field(default_factory=lambda: f"span-{uuid4().hex}")
    kind: OperationKind
    operation: str = Field(min_length=1, max_length=120)
    stage: str = Field(min_length=1, max_length=80)
    component: str = Field(min_length=1, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    started_at: datetime
    duration_ms: int = Field(ge=0)
    outcome: OperationOutcome
    result_count: int | None = Field(default=None, ge=0)
    failure_code: str | None = Field(default=None, max_length=120)
    retryable: bool | None = None


class OperationSignal(BaseModel):
    """Internal LangGraph custom-stream envelope never forwarded to clients."""

    type: Literal["observability.operation"] = "observability.operation"
    span: OperationSpan


class RunManifest(BaseModel):
    """Reproducibility metadata safe to persist with operational metrics."""

    schema_version: str = OBSERVABILITY_SCHEMA_VERSION
    application: str = "abundance-research"
    application_version: str = __version__
    graph_version: str = Field(min_length=1, max_length=80)
    run_id: str = Field(min_length=1, max_length=200)
    inquiry_id: str = Field(min_length=1, max_length=200)
    requested_model: str = Field(min_length=1, max_length=120)
    mode: str = Field(min_length=1, max_length=40)
    artifacts: list[ArtifactRevision] = Field(default_factory=list)
    started_at: datetime
    completed_at: datetime
    outcome: RunOutcome
    failure_code: str | None = Field(default=None, max_length=120)


class ModelUsage(BaseModel):
    """Provider usage aggregated without retaining prompts or completions."""

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    cost_usd: float | None = Field(default=None, ge=0)

    def add(self, other: ModelUsage) -> ModelUsage:
        """Return a combined usage value."""
        costs = [value for value in (self.cost_usd, other.cost_usd) if value is not None]
        return ModelUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            cost_usd=sum(costs) if costs else None,
        )


class RunMetrics(BaseModel):
    """Operational metrics emitted once per completed or failed run."""

    schema_version: str = OBSERVABILITY_SCHEMA_VERSION
    duration_ms: int = Field(ge=0)
    stage_duration_ms: dict[str, int] = Field(default_factory=dict)
    event_count: int = Field(default=0, ge=0)
    evidence_count: int = Field(default=0, ge=0)
    claim_count: int = Field(default=0, ge=0)
    model: str
    mode: str
    usage: ModelUsage = Field(default_factory=ModelUsage)
    operation_count: int = Field(default=0, ge=0)
    failed_operation_count: int = Field(default=0, ge=0)
    operations: list[OperationSpan] = Field(default_factory=list, max_length=200)
    manifest: RunManifest | None = None


class RunTelemetry:
    """Collect one run's canonical metrics without retaining research content."""

    def __init__(
        self,
        *,
        run_id: str,
        inquiry_id: str,
        requested_model: str,
        mode: str,
        graph_version: str,
        artifacts: Sequence[ArtifactRevision] = (),
        monotonic: Callable[[], float] = time.perf_counter,
        utcnow: Callable[[], datetime] | None = None,
    ) -> None:
        """Start a run-local collector with injectable clocks for testing."""
        self._run_id = run_id
        self._inquiry_id = inquiry_id
        self._requested_model = requested_model
        self._mode = mode
        self._graph_version = graph_version
        self._artifacts = list(artifacts)
        self._monotonic = monotonic
        self._utcnow = utcnow or (lambda: datetime.now(timezone.utc))
        self._started = monotonic()
        self._started_at = self._utcnow()
        self._stage_started = self._started
        self._current_stage: str | None = None
        self._stage_durations: dict[str, int] = {}
        self._event_count = 0
        self._evidence_count = 0
        self._claim_count = 0
        self._operations: list[OperationSpan] = []
        self._finished = False

    @property
    def finished(self) -> bool:
        """Return whether terminal metrics have already been produced."""
        return self._finished

    def record_event(self, event: ResearchEvent) -> None:
        """Observe only stable event metadata and public aggregate counts."""
        if self._finished:
            raise RuntimeError("Cannot record events after run telemetry is finished")
        self._event_count += 1
        next_stage = event.stage.value if event.stage is not None else self._current_stage
        now = self._monotonic()
        if next_stage != self._current_stage:
            self._close_current_stage(now)
            self._current_stage = next_stage
            self._stage_started = now
        if event.type == "run.completed":
            self._evidence_count = _public_count(event.data, "evidence_count")
            self._claim_count = _public_count(event.data, "claim_count")

    def record_operation(self, span: OperationSpan) -> None:
        """Retain one bounded privacy-safe operation measurement."""
        if self._finished:
            raise RuntimeError("Cannot record operations after run telemetry is finished")
        if len(self._operations) >= 200:
            raise RuntimeError("Run telemetry operation limit exceeded")
        self._operations.append(span)

    def finish(
        self,
        outcome: RunOutcome,
        *,
        usage: ModelUsage | None = None,
        failure_code: str | None = None,
    ) -> RunMetrics:
        """Close stage timing and return an immutable validated run summary."""
        if self._finished:
            raise RuntimeError("Run telemetry can only be finished once")
        now = self._monotonic()
        self._close_current_stage(now)
        self._current_stage = None
        completed_at = self._utcnow()
        self._finished = True
        manifest = RunManifest(
            graph_version=self._graph_version,
            run_id=self._run_id,
            inquiry_id=self._inquiry_id,
            requested_model=self._requested_model,
            mode=self._mode,
            artifacts=self._artifacts,
            started_at=self._started_at,
            completed_at=completed_at,
            outcome=outcome,
            failure_code=failure_code,
        )
        return RunMetrics(
            duration_ms=max(0, int((now - self._started) * 1000)),
            stage_duration_ms=dict(self._stage_durations),
            event_count=self._event_count,
            evidence_count=self._evidence_count,
            claim_count=self._claim_count,
            model=self._requested_model,
            mode=self._mode,
            usage=usage or ModelUsage(),
            operation_count=len(self._operations),
            failed_operation_count=sum(
                span.outcome is OperationOutcome.FAILED for span in self._operations
            ),
            operations=list(self._operations),
            manifest=manifest,
        )

    def _close_current_stage(self, now: float) -> None:
        if self._current_stage is None:
            return
        elapsed_ms = max(0, int((now - self._stage_started) * 1000))
        self._stage_durations[self._current_stage] = (
            self._stage_durations.get(self._current_stage, 0) + elapsed_ms
        )


def _public_count(data: dict[str, Any], field: str) -> int:
    value = data.get(field, 0)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def operation_signal_payload(span: OperationSpan) -> dict[str, Any]:
    """Serialize an internal operation span for LangGraph's custom stream."""
    return OperationSignal(span=span).model_dump(mode="json")


def parse_operation_signal(payload: Any) -> OperationSpan | None:
    """Return a validated internal span or ``None`` for a product event."""
    if not isinstance(payload, dict) or payload.get("type") != OPERATION_SIGNAL_TYPE:
        return None
    return OperationSignal.model_validate(payload).span


class JsonLogFormatter(logging.Formatter):
    """Serialize operational logs while excluding arbitrary object payloads."""

    _extra_fields = (
        "request_id",
        "run_id",
        "failure_code",
        "event_type",
        "duration_ms",
        "status_code",
        "method",
        "path",
    )

    def format(self, record: logging.LogRecord) -> str:
        """Return one JSON object per log record."""
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in self._extra_fields:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str) -> None:
    """Configure one JSON stream handler for the application process."""
    root = logging.getLogger()
    root.setLevel(level)
    if any(getattr(handler, "_abundance_json", False) for handler in root.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    handler._abundance_json = True  # type: ignore[attr-defined]
    root.handlers.clear()
    root.addHandler(handler)
