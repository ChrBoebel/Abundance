"""Deterministic quality metrics for structured Abundance reports."""

from __future__ import annotations

from pydantic import BaseModel, Field

from abundance_research.domain import ResearchReport


class ReportEvaluation(BaseModel):
    """Explainable coverage metrics for one research report."""

    total_claims: int = 0
    total_sources: int = 0
    claim_evidence_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    challenged_claim_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    primary_source_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    broken_evidence_links: int = 0
    open_question_count: int = 0


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def evaluate_report(report: ResearchReport) -> ReportEvaluation:
    """Evaluate report structure without using another language model."""
    evidence_ids = {record.id for record in report.evidence}
    covered_claims = 0
    challenged_claims = 0
    broken_links = 0

    for claim in report.claims:
        valid_links = [evidence_id for evidence_id in claim.evidence_ids if evidence_id in evidence_ids]
        if valid_links:
            covered_claims += 1
        broken_links += len(claim.evidence_ids) - len(valid_links)
        if claim.counter_evidence:
            challenged_claims += 1
        for counter_evidence in claim.counter_evidence:
            broken_links += sum(
                evidence_id not in evidence_ids
                for evidence_id in counter_evidence.evidence_ids
            )

    primary_sources = sum(record.assessment.is_primary for record in report.evidence)
    return ReportEvaluation(
        total_claims=len(report.claims),
        total_sources=len(report.evidence),
        claim_evidence_coverage=_ratio(covered_claims, len(report.claims)),
        challenged_claim_ratio=_ratio(challenged_claims, len(report.claims)),
        primary_source_ratio=_ratio(primary_sources, len(report.evidence)),
        broken_evidence_links=broken_links,
        open_question_count=len(report.open_questions),
    )
