"""Deterministic quality metrics for structured Abundance reports."""

from __future__ import annotations

from enum import Enum
from urllib.parse import urlsplit

from pydantic import BaseModel, Field

from abundance_research.domain import (
    ClaimVerificationSummary,
    Confidence,
    EvidenceAssessmentSummary,
    ResearchReport,
)

EVALUATION_SCHEMA_VERSION = "1.0"


class MetricComparator(str, Enum):
    """Supported deterministic quality-gate comparisons."""

    AT_LEAST = "at_least"
    AT_MOST = "at_most"
    EXACTLY = "exactly"


class EvaluationCheck(BaseModel):
    """Explain one metric decision without reducing evaluation to a score."""

    metric: str = Field(min_length=1, max_length=120)
    comparator: MetricComparator
    actual: float | int | None
    threshold: float | int
    passed: bool
    failure_code: str = Field(min_length=1, max_length=120)


class ReportEvaluation(BaseModel):
    """Explainable coverage metrics for one research report."""

    schema_version: str = EVALUATION_SCHEMA_VERSION
    total_claims: int = 0
    total_sources: int = 0
    claim_evidence_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    citation_integrity: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_utilization: float = Field(default=0.0, ge=0.0, le=1.0)
    challenged_claim_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    primary_source_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    source_domain_diversity: float = Field(default=0.0, ge=0.0, le=1.0)
    broken_evidence_links: int = 0
    unsupported_high_confidence_claims: int = 0
    open_question_count: int = 0
    evidence_assessment: EvidenceAssessmentSummary | None = None
    claim_verification: ClaimVerificationSummary | None = None


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def evaluate_threshold(
    metric: str,
    actual: float | int | None,
    comparator: MetricComparator,
    threshold: float | int,
    failure_code: str,
) -> EvaluationCheck:
    """Evaluate one numeric threshold and retain the complete decision context."""
    numeric_actual: float | int | None = (
        actual if isinstance(actual, int | float) and not isinstance(actual, bool) else None
    )
    passed = False
    if numeric_actual is not None and comparator is MetricComparator.AT_LEAST:
        passed = numeric_actual >= threshold
    elif numeric_actual is not None and comparator is MetricComparator.AT_MOST:
        passed = numeric_actual <= threshold
    elif numeric_actual is not None and comparator is MetricComparator.EXACTLY:
        passed = numeric_actual == threshold
    return EvaluationCheck(
        metric=metric,
        comparator=comparator,
        actual=actual,
        threshold=threshold,
        passed=passed,
        failure_code=failure_code,
    )


def evaluate_report(report: ResearchReport) -> ReportEvaluation:
    """Evaluate report structure without using another language model."""
    evidence_ids = {record.id for record in report.evidence}
    referenced_evidence_ids: set[str] = set()
    covered_claims = 0
    challenged_claims = 0
    broken_links = 0
    total_links = 0
    valid_links_count = 0
    unsupported_high_confidence_claims = 0

    for claim in report.claims:
        valid_links = [evidence_id for evidence_id in claim.evidence_ids if evidence_id in evidence_ids]
        total_links += len(claim.evidence_ids)
        valid_links_count += len(valid_links)
        referenced_evidence_ids.update(valid_links)
        if valid_links:
            covered_claims += 1
        elif claim.confidence is Confidence.HIGH:
            unsupported_high_confidence_claims += 1
        broken_links += len(claim.evidence_ids) - len(valid_links)
        if claim.counter_evidence:
            challenged_claims += 1
        for counter_evidence in claim.counter_evidence:
            valid_counter_links = [
                evidence_id
                for evidence_id in counter_evidence.evidence_ids
                if evidence_id in evidence_ids
            ]
            total_links += len(counter_evidence.evidence_ids)
            valid_links_count += len(valid_counter_links)
            referenced_evidence_ids.update(valid_counter_links)
            broken_links += len(counter_evidence.evidence_ids) - len(valid_counter_links)

    primary_sources = sum(record.assessment.is_primary for record in report.evidence)
    source_domains = {
        hostname
        for record in report.evidence
        if (hostname := urlsplit(record.url).hostname)
    }
    return ReportEvaluation(
        total_claims=len(report.claims),
        total_sources=len(report.evidence),
        claim_evidence_coverage=_ratio(covered_claims, len(report.claims)),
        citation_integrity=_ratio(valid_links_count, total_links),
        evidence_utilization=_ratio(len(referenced_evidence_ids), len(report.evidence)),
        challenged_claim_ratio=_ratio(challenged_claims, len(report.claims)),
        primary_source_ratio=_ratio(primary_sources, len(report.evidence)),
        source_domain_diversity=_ratio(len(source_domains), len(report.evidence)),
        broken_evidence_links=broken_links,
        unsupported_high_confidence_claims=unsupported_high_confidence_claims,
        open_question_count=len(report.open_questions),
    )
