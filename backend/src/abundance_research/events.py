"""Stable Abundance event contract for streaming research progress."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ResearchStage(str, Enum):
    """Product-level stages shown to clients."""

    INQUIRY = "inquiry"
    PLANNING = "planning"
    EVIDENCE = "evidence"
    REVIEW = "review"
    SYNTHESIS = "synthesis"


class ResearchEvent(BaseModel):
    """Version-independent event emitted by the Abundance application."""

    type: str
    stage: ResearchStage | None = None
    message: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
