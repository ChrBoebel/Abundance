"""Domain models that define Abundance independently of its graph runtime."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ResearchMode(str, Enum):
    """User-facing research depth profiles."""

    QUICK = "quick"
    BALANCED = "balanced"
    THOROUGH = "thorough"


class Confidence(str, Enum):
    """Calibrated confidence attached to a claim or report."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SourceKind(str, Enum):
    """Broad source categories used during evidence assessment."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    ACADEMIC = "academic"
    NEWS = "news"
    OTHER = "other"


class EvidenceRelation(str, Enum):
    """How an evidence record relates to the question being investigated."""

    SUPPORTS = "supports"
    CHALLENGES = "challenges"
    CONTEXT = "context"


class Inquiry(BaseModel):
    """A research question together with explicit scope constraints."""

    id: str = Field(default_factory=lambda: f"inq-{uuid4().hex}")
    question: str = Field(min_length=3, max_length=8000)
    language: str | None = None
    timeframe: str | None = None
    geography: str | None = None
    preferred_source_kinds: list[SourceKind] = Field(default_factory=list)
    mode: ResearchMode = ResearchMode.BALANCED


class ResearchPlan(BaseModel):
    """An inspectable plan for answering an inquiry."""

    inquiry_id: str
    objective: str
    research_questions: list[str] = Field(default_factory=list)
    falsification_questions: list[str] = Field(default_factory=list)
    source_strategy: list[str] = Field(default_factory=list)
    completion_criteria: list[str] = Field(default_factory=list)


class ResearchUnit(BaseModel):
    """A bounded, policy-approved evidence question."""

    id: str = Field(default_factory=lambda: f"unit-{uuid4().hex}")
    question: str = Field(min_length=3, max_length=500)
    purpose: str = Field(min_length=3, max_length=500)
    relation: EvidenceRelation = EvidenceRelation.CONTEXT
    priority: int = Field(default=0, ge=0, le=100)


class SourceAssessment(BaseModel):
    """Quality signals associated with a source."""

    source_kind: SourceKind = SourceKind.OTHER
    credibility: Confidence = Confidence.MEDIUM
    relevance: Confidence = Confidence.MEDIUM
    is_primary: bool = False
    limitations: list[str] = Field(default_factory=list)


class EvidenceRecord(BaseModel):
    """A normalized source excerpt that can support or challenge claims."""

    id: str = Field(default_factory=lambda: f"ev-{uuid4().hex}")
    title: str = Field(min_length=1, max_length=500)
    url: str = Field(min_length=8, max_length=4000)
    excerpt: str = Field(min_length=1, max_length=50000)
    relation: EvidenceRelation = EvidenceRelation.CONTEXT
    research_unit_id: str | None = None
    published_at: datetime | None = None
    assessment: SourceAssessment = Field(default_factory=SourceAssessment)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CounterEvidence(BaseModel):
    """Evidence or reasoning that challenges a claim."""

    summary: str
    evidence_ids: list[str] = Field(default_factory=list)
    impact: Confidence = Confidence.MEDIUM


class Claim(BaseModel):
    """A falsifiable statement connected to supporting and opposing evidence."""

    id: str = Field(default_factory=lambda: f"claim-{uuid4().hex}")
    statement: str
    evidence_ids: list[str] = Field(default_factory=list)
    counter_evidence: list[CounterEvidence] = Field(default_factory=list)
    confidence: Confidence = Confidence.MEDIUM
    uncertainty_notes: list[str] = Field(default_factory=list)


class OpenQuestion(BaseModel):
    """A material uncertainty that remains after the research run."""

    question: str
    why_it_matters: str
    suggested_next_step: str | None = None


class ResearchReport(BaseModel):
    """Structured result of an Abundance research run."""

    inquiry_id: str
    title: str
    summary: str
    claims: list[Claim] = Field(default_factory=list)
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    confidence: Confidence = Confidence.MEDIUM
    markdown: str = ""
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
