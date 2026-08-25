"""Ports used by the Abundance research application."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from abundance_research.domain import (
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
