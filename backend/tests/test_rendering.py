from abundance_research.application.rendering import finalize_report
from abundance_research.domain import (
    Claim,
    Confidence,
    CounterEvidence,
    EvidenceRecord,
    OpenQuestion,
    ResearchReport,
)


def test_report_renderer_uses_only_known_evidence_references() -> None:
    evidence = EvidenceRecord(
        id="ev-known",
        title="Official [record]",
        url="https://example.org/source",
        excerpt="A material observation",
    )
    report = ResearchReport(
        inquiry_id="inq-1",
        title="Evidence review",
        summary="The supported answer remains conditional.",
        confidence=Confidence.MEDIUM,
        evidence=[evidence],
        claims=[
            Claim(
                statement="The central claim is supported",
                evidence_ids=["ev-known", "ev-invented"],
                counter_evidence=[
                    CounterEvidence(
                        summary="A limitation remains",
                        evidence_ids=["ev-invented"],
                    )
                ],
            )
        ],
        open_questions=[
            OpenQuestion(
                question="Will the result generalize?",
                why_it_matters="The sample is narrow.",
            )
        ],
    )

    rendered = finalize_report(report)

    assert "supported [1]" in rendered.markdown
    assert "ev-invented" not in rendered.markdown
    assert "[1] Official \\[record\\]: https://example.org/source" in rendered.markdown


def test_report_renderer_never_uses_model_supplied_markdown() -> None:
    report = ResearchReport(
        inquiry_id="inq-1",
        title="Safe report",
        summary="Summary",
        markdown="<script>alert('unsafe')</script>",
    )

    rendered = finalize_report(report)

    assert "<script>" not in rendered.markdown
    assert rendered.markdown.startswith("# Safe report")
