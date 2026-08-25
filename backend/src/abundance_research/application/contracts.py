"""Ports used by the Abundance research application."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from abundance_research.domain import (
    EvidenceAssessment,
    EvidenceRecord,
    Inquiry,
    ResearchMode,
    ResearchPlan,
    ResearchReport,
    ResearchUnit,
)


@dataclass(frozen=True, slots=True)
class ResearchCommand:
    """Validated input for one independent research run."""

    run_id: str
    inquiry: Inquiry
    model: str
    mode: ResearchMode

    def to_payload(self) -> dict[str, Any]:
        """Serialize the command for LangGraph state and checkpointing."""
        return {
            "run_id": self.run_id,
            "inquiry": self.inquiry.model_dump(mode="json"),
            "model": self.model,
            "mode": self.mode.value,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ResearchCommand:
        """Reconstruct a command at an application-node boundary."""
        inquiry = Inquiry.model_validate(payload["inquiry"])
        return cls(
            run_id=str(payload["run_id"]),
            inquiry=inquiry,
            model=str(payload["model"]),
            mode=ResearchMode(payload["mode"]),
        )


class PlanningModel(Protocol):
    """Create an inspectable research plan without executing tools."""

    async def create_plan(self, inquiry: Inquiry, *, model: str) -> ResearchPlan:
        """Return a plan tied to the supplied inquiry."""


class EvidenceSource(Protocol):
    """Read-only source of normalized evidence records."""

    @property
    def name(self) -> str:
        """Return the stable source adapter name."""

    async def search(
        self,
        unit: ResearchUnit,
        *,
        max_results: int,
    ) -> Sequence[EvidenceRecord]:
        """Collect evidence for one policy-approved research unit."""


class EvidenceAssessmentModel(Protocol):
    """Assess admitted evidence without changing the admitted source set."""

    async def assess_evidence(
        self,
        inquiry: Inquiry,
        evidence: Sequence[EvidenceRecord],
        *,
        model: str,
    ) -> Sequence[EvidenceAssessment]:
        """Return bound semantic assessments for known evidence IDs only."""


class SynthesisModel(Protocol):
    """Turn an allowed evidence set into a structured report."""

    async def synthesize(
        self,
        inquiry: Inquiry,
        plan: ResearchPlan,
        evidence: Sequence[EvidenceRecord],
        *,
        model: str,
    ) -> ResearchReport:
        """Return a structured report; final Markdown is rendered in application code."""
