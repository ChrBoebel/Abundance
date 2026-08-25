from abundance_research.domain import (
    Claim,
    Confidence,
    CounterEvidence,
    EvidenceRecord,
    Inquiry,
    ResearchMode,
    ResearchReport,
    SourceAssessment,
    SourceKind,
)
from abundance_research.evaluation import evaluate_report


def test_inquiry_defaults_to_balanced_research() -> None:
    inquiry = Inquiry(question="Welche Evidenz trägt die zentrale These?")

    assert inquiry.id.startswith("inq-")
    assert inquiry.mode is ResearchMode.BALANCED


def test_report_evaluation_tracks_support_and_counterevidence() -> None:
    primary = EvidenceRecord(
        id="ev-primary",
        title="Official dataset",
        url="https://example.com/data",
        excerpt="The dataset reports a measurable change.",
        assessment=SourceAssessment(
            source_kind=SourceKind.PRIMARY,
            credibility=Confidence.HIGH,
            relevance=Confidence.HIGH,
            is_primary=True,
        ),
    )
    secondary = EvidenceRecord(
        id="ev-secondary",
        title="Independent analysis",
        url="https://example.com/analysis",
        excerpt="The analysis identifies an alternative explanation.",
    )
    report = ResearchReport(
        inquiry_id="inq-test",
        title="Evidence review",
        summary="The claim is plausible but qualified.",
        evidence=[primary, secondary],
        claims=[
            Claim(
                statement="The intervention contributed to the measured change.",
                evidence_ids=[primary.id],
                counter_evidence=[
                    CounterEvidence(
                        summary="A contemporaneous policy may explain part of the change.",
                        evidence_ids=[secondary.id],
                    )
                ],
                confidence=Confidence.MEDIUM,
            )
        ],
    )

    evaluation = evaluate_report(report)

    assert evaluation.claim_evidence_coverage == 1.0
    assert evaluation.challenged_claim_ratio == 1.0
    assert evaluation.primary_source_ratio == 0.5
    assert evaluation.broken_evidence_links == 0


def test_report_evaluation_detects_broken_evidence_links() -> None:
    report = ResearchReport(
        inquiry_id="inq-test",
        title="Incomplete report",
        summary="Evidence is missing.",
        claims=[Claim(statement="An unsupported claim", evidence_ids=["ev-missing"])],
    )

    evaluation = evaluate_report(report)

    assert evaluation.claim_evidence_coverage == 0.0
    assert evaluation.broken_evidence_links == 1
