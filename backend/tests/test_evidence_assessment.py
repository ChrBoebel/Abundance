from abundance_research.application.evidence_assessment import (
    bind_exact_quote,
    evidence_content_sha256,
    summarize_evidence_assessments,
)
from abundance_research.domain import (
    AssessedEvidenceRelation,
    AssessmentStatus,
    Confidence,
    EvidenceAssessment,
    EvidenceRecord,
    EvidenceRelation,
    SourceKind,
)


def test_exact_quote_binding_rejects_model_paraphrases() -> None:
    record = EvidenceRecord(
        id="ev-1",
        title="Measured result",
        url="https://example.org/result",
        excerpt="The measured value fell by 12 percent.",
    )

    assert bind_exact_quote(record, "value fell by 12 percent") == "value fell by 12 percent"
    assert bind_exact_quote(record, "the value decreased by twelve percent") is None


def test_shadow_summary_tracks_disagreement_duplicates_and_coverage() -> None:
    first = EvidenceRecord(
        id="ev-1",
        title="First copy",
        url="https://example.org/first",
        excerpt="The same measured result.",
        relation=EvidenceRelation.SUPPORTS,
    )
    duplicate = EvidenceRecord(
        id="ev-2",
        title="Second copy",
        url="https://mirror.example/second",
        excerpt="  The same measured result.  ",
        relation=EvidenceRelation.CONTEXT,
    )
    assessment = EvidenceAssessment(
        evidence_id=first.id,
        relation=AssessedEvidenceRelation.CHALLENGES,
        relevance=Confidence.HIGH,
        source_kind=SourceKind.SECONDARY,
        is_primary=True,
        quote="The same measured result.",
        confidence=Confidence.MEDIUM,
        content_sha256=evidence_content_sha256(first),
        assessor_version="evidence-assessment-v1",
    )

    summary = summarize_evidence_assessments([first, duplicate], [assessment])

    assert summary.status is AssessmentStatus.PARTIAL
    assert summary.coverage_ratio == 0.5
    assert summary.relation_disagreement_count == 1
    assert summary.duplicate_content_count == 1
    assert summary.primary_status_disagreement_count == 1
    assert summary.exact_quote_ratio == 1
