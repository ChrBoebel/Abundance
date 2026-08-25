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


class AssessedEvidenceRelation(str, Enum):
    """Semantically assessed relationship independent of retrieval intent."""

    SUPPORTS = "supports"
    CHALLENGES = "challenges"
    CONTEXT = "context"
    IRRELEVANT = "irrelevant"


class AssessmentStatus(str, Enum):
    """Completeness state for one shadow evidence-assessment pass."""

    DISABLED = "disabled"
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class ClaimVerificationVerdict(str, Enum):
    """Whether one admitted evidence record establishes a report claim."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    INSUFFICIENT = "insufficient"
    UNVERIFIABLE = "unverifiable"


class VerificationStatus(str, Enum):
    """Completeness state for one shadow claim-verification pass."""

    DISABLED = "disabled"
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


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


class EvidenceAssessment(BaseModel):
    """Bound semantic assessment of one admitted evidence record."""

    evidence_id: str
    relation: AssessedEvidenceRelation
    relevance: Confidence
    source_kind: SourceKind
    is_primary: bool
    quote: str | None = Field(default=None, max_length=2000)
    limitations: list[str] = Field(default_factory=list, max_length=10)
    confidence: Confidence = Confidence.MEDIUM
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    assessor_version: str = Field(min_length=1, max_length=120)


class EvidenceAssessmentSummary(BaseModel):
    """Privacy-safe aggregate emitted by the shadow assessment stage."""

    status: AssessmentStatus
    evidence_count: int = Field(default=0, ge=0)
    assessed_count: int = Field(default=0, ge=0)
    coverage_ratio: float = Field(default=0.0, ge=0, le=1)
    relation_disagreement_count: int = Field(default=0, ge=0)
    irrelevant_count: int = Field(default=0, ge=0)
    duplicate_content_count: int = Field(default=0, ge=0)
    primary_status_disagreement_count: int = Field(default=0, ge=0)
    exact_quote_ratio: float = Field(default=0.0, ge=0, le=1)
    failure_code: str | None = Field(default=None, max_length=120)


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


class ClaimEvidenceVerification(BaseModel):
    """A verdict bound to one existing claim and one of its cited records."""

    claim_id: str
    evidence_id: str
    verdict: ClaimVerificationVerdict
    quote: str | None = Field(default=None, max_length=2000)
    limitations: list[str] = Field(default_factory=list, max_length=10)
    confidence: Confidence = Confidence.MEDIUM
    claim_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    verifier_version: str = Field(min_length=1, max_length=120)


class ClaimVerificationSummary(BaseModel):
    """Privacy-safe aggregate emitted by shadow claim verification."""

    status: VerificationStatus
    claim_count: int = Field(default=0, ge=0)
    cited_claim_count: int = Field(default=0, ge=0)
    verified_claim_count: int = Field(default=0, ge=0)
    pair_count: int = Field(default=0, ge=0)
    verified_pair_count: int = Field(default=0, ge=0)
    coverage_ratio: float = Field(default=0.0, ge=0, le=1)
    supported_claim_count: int = Field(default=0, ge=0)
    contradicted_claim_count: int = Field(default=0, ge=0)
    insufficient_claim_count: int = Field(default=0, ge=0)
    unverifiable_claim_count: int = Field(default=0, ge=0)
    high_confidence_unsubstantiated_count: int = Field(default=0, ge=0)
    exact_quote_ratio: float = Field(default=0.0, ge=0, le=1)
    failure_code: str | None = Field(default=None, max_length=120)


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
