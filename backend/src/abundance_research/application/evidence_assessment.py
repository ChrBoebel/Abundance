"""Deterministic boundaries for semantic evidence assessment."""

from __future__ import annotations

from hashlib import sha256

from abundance_research.domain import (
    AssessedEvidenceRelation,
    AssessmentStatus,
    EvidenceAssessment,
    EvidenceAssessmentSummary,
    EvidenceRecord,
)


def evidence_content_sha256(record: EvidenceRecord) -> str:
    """Hash normalized evidence content for private duplicate detection."""
    normalized = " ".join(record.excerpt.split()).casefold()
    return sha256(normalized.encode("utf-8")).hexdigest()


def bind_exact_quote(record: EvidenceRecord, quote: str | None) -> str | None:
    """Keep a proposed quote only when it occurs verbatim in admitted evidence."""
    candidate = quote.strip() if quote is not None else ""
    return candidate if candidate and candidate in record.excerpt else None


def unavailable_assessment_summary(
    evidence_count: int,
    *,
    status: AssessmentStatus,
    failure_code: str | None = None,
) -> EvidenceAssessmentSummary:
    """Create a validated summary when shadow assessment cannot execute."""
    return EvidenceAssessmentSummary(
        status=status,
        evidence_count=evidence_count,
        failure_code=failure_code,
    )


def summarize_evidence_assessments(
    evidence: list[EvidenceRecord],
    assessments: list[EvidenceAssessment],
) -> EvidenceAssessmentSummary:
    """Aggregate shadow results without exposing evidence or model reasoning."""
    records_by_id = {record.id: record for record in evidence}
    unique_assessments: dict[str, EvidenceAssessment] = {}
    for assessment in assessments:
        if assessment.evidence_id in records_by_id:
            unique_assessments.setdefault(assessment.evidence_id, assessment)

    assessed = list(unique_assessments.values())
    evidence_count = len(evidence)
    assessed_count = len(assessed)
    relation_disagreements = 0
    primary_disagreements = 0
    exact_quotes = 0
    irrelevant = 0
    for assessment in assessed:
        record = records_by_id[assessment.evidence_id]
        expected_relation = AssessedEvidenceRelation(record.relation.value)
        relation_disagreements += assessment.relation is not expected_relation
        primary_disagreements += assessment.is_primary != record.assessment.is_primary
        exact_quotes += assessment.quote is not None
        irrelevant += assessment.relation is AssessedEvidenceRelation.IRRELEVANT

    fingerprints = [evidence_content_sha256(record) for record in evidence]
    status = (
        AssessmentStatus.COMPLETE
        if evidence_count > 0 and assessed_count == evidence_count
        else AssessmentStatus.PARTIAL
    )
    return EvidenceAssessmentSummary(
        status=status,
        evidence_count=evidence_count,
        assessed_count=assessed_count,
        coverage_ratio=assessed_count / evidence_count if evidence_count else 0.0,
        relation_disagreement_count=relation_disagreements,
        irrelevant_count=irrelevant,
        duplicate_content_count=len(fingerprints) - len(set(fingerprints)),
        primary_status_disagreement_count=primary_disagreements,
        exact_quote_ratio=exact_quotes / assessed_count if assessed_count else 0.0,
    )
