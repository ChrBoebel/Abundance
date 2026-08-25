from abundance_research.application.errors import ResearchFailure
from abundance_research.application.policy import ResearchCapabilityPolicy
from abundance_research.domain import (
    EvidenceRecord,
    EvidenceRelation,
    ResearchMode,
    ResearchPlan,
)


def test_policy_bounds_and_deduplicates_research_units() -> None:
    plan = ResearchPlan(
        inquiry_id="inq-1",
        objective="Assess a claim",
        research_questions=["What supports it?", " What supports it? ", "What is the baseline?"],
        falsification_questions=["What would disprove it?", "Which data conflicts?"],
    )

    units = ResearchCapabilityPolicy(ResearchMode.QUICK).authorize_plan(plan)

    assert len(units) == 3
    assert units[0].question == "What supports it?"
    assert units[-1].relation is EvidenceRelation.CHALLENGES


def test_policy_rejects_plan_without_executable_questions() -> None:
    plan = ResearchPlan(inquiry_id="inq-1", objective="Empty")

    try:
        ResearchCapabilityPolicy(ResearchMode.BALANCED).authorize_plan(plan)
    except ResearchFailure as exc:
        assert exc.code.value == "invalid_input"
    else:
        raise AssertionError("Expected an invalid plan to be rejected")


def test_policy_normalizes_and_deduplicates_evidence_urls() -> None:
    records = [
        EvidenceRecord(
            id="ev-1",
            title="Primary record",
            url="HTTPS://Example.COM/report?utm_source=test&id=7#section",
            excerpt="Result",
        ),
        EvidenceRecord(
            id="ev-2",
            title="Repeated record",
            url="https://example.com/report?id=7",
            excerpt="Same underlying source",
        ),
        EvidenceRecord(
            id="ev-3",
            title="Unsafe record",
            url="javascript:alert(1)",
            excerpt="Unsafe URL",
        ),
    ]

    admitted = ResearchCapabilityPolicy(ResearchMode.BALANCED).admit_evidence(records)

    assert [record.id for record in admitted] == ["ev-1"]
    assert admitted[0].url == "https://example.com/report?id=7"


def test_policy_rejects_credentialed_and_invalid_port_urls() -> None:
    normalize = ResearchCapabilityPolicy.normalize_source_url

    assert normalize("https://user:secret@example.org/report") is None
    assert normalize("https://example.org:invalid/report") is None
