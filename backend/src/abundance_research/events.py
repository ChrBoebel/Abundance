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
    """Framework-independent event emitted by the Abundance API."""

    type: str
    stage: ResearchStage | None = None
    message: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


_NODE_STAGES: dict[str, tuple[ResearchStage, str, str]] = {
    "scope_inquiry": (ResearchStage.INQUIRY, "inquiry.scoping", "Prüfe den Rechercheauftrag"),
    "design_research_plan": (ResearchStage.PLANNING, "plan.created", "Entwickle den Rechercheplan"),
    "coordinate_research": (ResearchStage.EVIDENCE, "evidence.collection.started", "Plane die Evidenzsuche"),
    "coordinator": (ResearchStage.EVIDENCE, "evidence.collection.started", "Koordiniere Recherchepfade"),
    "investigator": (ResearchStage.EVIDENCE, "evidence.collection.started", "Sammle relevante Evidenz"),
    "run_evidence_tools": (ResearchStage.EVIDENCE, "evidence.collection.started", "Prüfe Suchergebnisse"),
    "review_evidence": (ResearchStage.REVIEW, "evidence.review.started", "Ordne Evidenz und Gegenbelege"),
    "synthesize_report": (ResearchStage.SYNTHESIS, "synthesis.started", "Erstelle die Synthese"),
}


class ResearchEventMapper:
    """Translate LangGraph runtime events into the public Abundance contract."""

    def __init__(self) -> None:
        """Initialize event mapping state for one research run."""
        self._report_emitted = False

    def map(self, event: dict[str, Any]) -> list[ResearchEvent]:
        """Map one serialized runtime event to public domain events."""
        event_name = event.get("event")
        data = event.get("data") or {}
        metadata = event.get("metadata") or data.get("metadata") or {}
        node_name = metadata.get("langgraph_node")
        mapped: list[ResearchEvent] = []

        if event_name == "on_chain_start" and node_name in _NODE_STAGES:
            stage, event_type, message = _NODE_STAGES[node_name]
            mapped.append(
                ResearchEvent(
                    type=event_type,
                    stage=stage,
                    message=message,
                )
            )

        elif event_name == "on_tool_start":
            mapped.append(
                ResearchEvent(
                    type="evidence.search.started",
                    stage=ResearchStage.EVIDENCE,
                    message="Durchsuche Quellen",
                    data={
                        "tool": event.get("name") or data.get("name"),
                        "query": data.get("input"),
                    },
                )
            )

        elif event_name == "on_tool_end":
            mapped.append(
                ResearchEvent(
                    type="evidence.discovered",
                    stage=ResearchStage.EVIDENCE,
                    message="Neue Evidenz gefunden",
                    data={
                        "tool": event.get("name") or data.get("name"),
                        "result": data.get("output"),
                    },
                )
            )

        elif event_name == "on_chat_model_stream" and node_name == "synthesize_report":
            chunk = data.get("chunk")
            if chunk:
                mapped.append(
                    ResearchEvent(
                        type="report.delta",
                        stage=ResearchStage.SYNTHESIS,
                        data={"chunk": chunk},
                    )
                )

        elif event_name == "on_chain_end":
            output = data.get("output") or {}
            final_report = output.get("final_report") if isinstance(output, dict) else None
            if final_report and not self._report_emitted:
                self._report_emitted = True
                mapped.append(
                    ResearchEvent(
                        type="report.completed",
                        stage=ResearchStage.SYNTHESIS,
                        message="Recherchebericht abgeschlossen",
                        data={"content": final_report},
                    )
                )

        return mapped
