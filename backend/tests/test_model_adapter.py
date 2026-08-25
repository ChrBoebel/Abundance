import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from abundance_research.adapters.models import (
    ClaimDraft,
    ModelCatalog,
    OpenRouterResearchModel,
    SynthesisDraft,
)
from abundance_research.application.errors import ResearchFailure
from abundance_research.domain import Confidence, EvidenceRecord, Inquiry


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
        ("prompt", "synthesis", "synthesis-v1"),
    }


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
