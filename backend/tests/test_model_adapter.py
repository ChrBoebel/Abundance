import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from abundance_research.adapters.models import (
    ClaimDraft,
    EvidenceAssessmentBatchDraft,
    ModelCatalog,
    OpenRouterResearchModel,
    SynthesisDraft,
)
from abundance_research.application.errors import ResearchFailure
from abundance_research.domain import (
    AssessedEvidenceRelation,
    Confidence,
    EvidenceRecord,
    Inquiry,
)


@pytest.mark.asyncio
async def test_model_adapter_requests_schema_output_without_tools() -> None:
    captured: dict[str, object] = {}

    class FakeStructuredModel:
        async def ainvoke(self, messages):
            captured["messages"] = messages
            return {
                "objective": "Test the central proposition",
                "research_questions": ["What evidence supports it?"],
                "falsification_questions": ["What evidence contradicts it?"],
            }

    class FakeChatModel:
        def with_structured_output(self, schema, **kwargs):
            captured["schema"] = schema
            captured["structured_output_options"] = kwargs
            return FakeStructuredModel()

    def build_chat_model(model_id: str, max_tokens: int):
        captured["model"] = model_id
        captured["max_tokens"] = max_tokens
        return FakeChatModel()

    model = OpenRouterResearchModel("test-key", chat_model_factory=build_chat_model)
    inquiry = Inquiry(question="Does the proposition hold?")

    plan = await model.create_plan(inquiry, model="mercury")

    assert plan.inquiry_id == inquiry.id
    assert captured["schema"].__name__ == "PlanDraft"
    assert captured["structured_output_options"] == {
        "method": "json_schema",
        "strict": True,
        "include_raw": True,
    }
    assert captured["model"] == "inception/mercury-2"
    assert captured["max_tokens"] == 3000
    assert isinstance(captured["messages"][0], SystemMessage)
    assert isinstance(captured["messages"][1], HumanMessage)


def test_model_catalog_rejects_arbitrary_provider_identifiers() -> None:
    with pytest.raises(ResearchFailure) as caught:
        ModelCatalog.resolve("attacker/provider-model")

    assert caught.value.code.value == "invalid_input"


def test_model_adapter_describes_versioned_observability_artifacts() -> None:
    model = OpenRouterResearchModel("test-key")

    artifacts = model.observability_artifacts("mercury")

    assert {(artifact.kind.value, artifact.name, artifact.version) for artifact in artifacts} == {
        ("model", "mercury", "inception/mercury-2"),
        ("prompt", "planning", "planning-v1"),
        ("prompt", "evidence-assessment", "evidence-assessment-v1"),
        ("prompt", "synthesis", "synthesis-v1"),
    }


@pytest.mark.asyncio
async def test_evidence_assessment_binds_ids_quotes_and_irrelevant_relevance() -> None:
    captured: dict[str, object] = {}

    class FakeStructuredModel:
        async def ainvoke(self, messages):
            captured["messages"] = messages
            return {
                "assessments": [
                    {
                        "evidence_id": "ev-known",
                        "relation": "irrelevant",
                        "relevance": "high",
                        "source_kind": "other",
                        "is_primary": False,
                        "quote": "A paraphrase that is not in the record.",
                        "limitations": ["No benchmark evidence."],
                        "confidence": "high",
                    },
                    {
                        "evidence_id": "ev-invented",
                        "relation": "supports",
                        "relevance": "high",
                        "source_kind": "primary",
                        "is_primary": True,
                        "quote": None,
                    },
                ]
            }

    class FakeChatModel:
        def with_structured_output(self, schema, **kwargs):
            captured["schema"] = schema
            return FakeStructuredModel()

    model = OpenRouterResearchModel(
        "test-key",
        chat_model_factory=lambda model_id, max_tokens: FakeChatModel(),
    )
    inquiry = Inquiry(question="Was the benchmark independently reproduced?")
    evidence = [
        EvidenceRecord(
            id="ev-known",
            title="Commercial offer",
            url="https://vendor.example/product",
            excerpt="Order today to receive a discount.",
        )
    ]

    assessments = list(await model.assess_evidence(inquiry, evidence, model="mercury"))

    assert captured["schema"] is EvidenceAssessmentBatchDraft
    assert len(assessments) == 1
    assert assessments[0].evidence_id == "ev-known"
    assert assessments[0].relation is AssessedEvidenceRelation.IRRELEVANT
    assert assessments[0].relevance is Confidence.LOW
    assert assessments[0].quote is None
    assert any("not found verbatim" in item for item in assessments[0].limitations)
    assert assessments[0].content_sha256
    assert "ev-invented" not in {assessment.evidence_id for assessment in assessments}


@pytest.mark.asyncio
async def test_model_adapter_aggregates_usage_without_message_content() -> None:
    class FakeStructuredModel:
        async def ainvoke(self, messages):
            return {
                "parsed": {
                    "objective": "Measure the proposition",
                    "research_questions": ["What supports it?"],
                    "falsification_questions": ["What contradicts it?"],
                },
                "raw": AIMessage(
                    content="private completion",
                    usage_metadata={
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "total_tokens": 15,
                    },
                    response_metadata={"token_usage": {"cost": 0.001}},
                ),
            }

    class FakeChatModel:
        def with_structured_output(self, schema, **kwargs):
            return FakeStructuredModel()

    model = OpenRouterResearchModel(
        "test-key",
        chat_model_factory=lambda model_id, max_tokens: FakeChatModel(),
    )
    inquiry = Inquiry(question="How costly is this research?")

    await model.create_plan(inquiry, model="mercury")
    usage = model.drain_usage(inquiry.id)

    assert usage.total_tokens == 15
    assert usage.cost_usd == pytest.approx(0.001)
    assert "private completion" not in usage.model_dump_json()


@pytest.mark.asyncio
async def test_model_adapter_classifies_structured_output_parse_failure() -> None:
    class FakeStructuredModel:
        async def ainvoke(self, messages):
            return {
                "raw": AIMessage(content="private malformed response"),
                "parsed": None,
                "parsing_error": RuntimeError("private parser details"),
            }

    class FakeChatModel:
        def with_structured_output(self, schema, **kwargs):
            return FakeStructuredModel()

    model = OpenRouterResearchModel(
        "test-key",
        chat_model_factory=lambda model_id, max_tokens: FakeChatModel(),
    )

    with pytest.raises(ResearchFailure) as caught:
        await model.create_plan(Inquiry(question="Test structured output"), model="mercury")

    assert caught.value.code.value == "model_output_invalid"
    assert not caught.value.retryable
    assert "private" not in caught.value.public_message


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
