"""Structured, privacy-conscious logging and run metrics."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


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

    duration_ms: int = Field(ge=0)
    stage_duration_ms: dict[str, int] = Field(default_factory=dict)
    event_count: int = Field(default=0, ge=0)
    evidence_count: int = Field(default=0, ge=0)
    claim_count: int = Field(default=0, ge=0)
    model: str
    mode: str
    usage: ModelUsage = Field(default_factory=ModelUsage)


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
