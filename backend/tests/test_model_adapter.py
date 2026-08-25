import pytest

from abundance_research.adapters.models import (
    ClaimDraft,
    ModelCatalog,
    OpenRouterResearchModel,
    SynthesisDraft,
)
from abundance_research.application.errors import ResearchFailure
from abundance_research.domain import Confidence, EvidenceRecord, Inquiry


def test_model_catalog_rejects_arbitrary_provider_identifiers() -> None:
    with pytest.raises(ResearchFailure) as caught:
        ModelCatalog.resolve("attacker/provider-model")

    assert caught.value.code.value == "invalid_input"


def test_synthesis_binding_removes_invented_evidence_ids() -> None:
    inquiry = Inquiry(question="Does the evidence support the claim?")
    evidence = [
        EvidenceRecord(
            id="ev-allowed",
            title="Official evidence",
            url="https://example.org/evidence",
            excerpt="A measured result",
        )
    ]
    draft = SynthesisDraft(
        title="Assessment",
        summary="The result is conditional.",
        claims=[
            ClaimDraft(
                statement="An unsupported strong claim",
                evidence_ids=["ev-invented"],
                confidence=Confidence.HIGH,
            ),
            ClaimDraft(
                statement="A supported claim",
                evidence_ids=["ev-allowed", "ev-allowed"],
                confidence=Confidence.HIGH,
            ),
        ],
    )

    report = OpenRouterResearchModel.bind_evidence(inquiry, evidence, draft)

    assert report.claims[0].evidence_ids == []
    assert report.claims[0].confidence is Confidence.LOW
    assert report.claims[0].uncertainty_notes
    assert report.claims[1].evidence_ids == ["ev-allowed"]
