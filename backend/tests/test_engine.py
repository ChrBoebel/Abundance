import asyncio
import json

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from abundance_research.application.contracts import ResearchCommand
from abundance_research.application.engine import AbundanceResearchEngine
from abundance_research.application.errors import FailureCode, ResearchFailure
from abundance_research.domain import (
    Claim,
    Confidence,
    EvidenceRecord,
    Inquiry,
    ResearchMode,
    ResearchPlan,
    ResearchReport,
    ResearchUnit,
)


class FakePlanner:
    async def create_plan(self, inquiry: Inquiry, *, model: str) -> ResearchPlan:
        return ResearchPlan(
            inquiry_id=inquiry.id,
            objective="Test the proposition",
            research_questions=["Question one", "Question two", "Question three"],
            falsification_questions=["What contradicts the proposition?"],
        )


class TrackingEvidenceSource:
    name = "tracking-source"

    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0

    async def search(self, unit: ResearchUnit, *, max_results: int) -> list[EvidenceRecord]:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.005)
        self.active -= 1
        return [
            EvidenceRecord(
                id=f"ev-{unit.id}",
                title=f"Source for {unit.question}",
                url=f"https://example.org/{unit.id}?utm_source=test",
                excerpt="Observed evidence",
                relation=unit.relation,
                research_unit_id=unit.id,
            )
        ][:max_results]


class InventingSynthesizer:
    async def synthesize(
        self,
        inquiry: Inquiry,
        plan: ResearchPlan,
        evidence: list[EvidenceRecord],
        *,
        model: str,
    ) -> ResearchReport:
        return ResearchReport(
            inquiry_id="wrong-inquiry",
            title="Bound report",
            summary="A conditional result.",
            confidence=Confidence.MEDIUM,
            evidence=[
                EvidenceRecord(
                    id="ev-invented",
                    title="Invented",
                    url="https://attacker.invalid/source",
                    excerpt="Not admitted",
                )
            ],
            claims=[
                Claim(
                    statement="Only admitted references survive",
                    evidence_ids=[evidence[0].id, "ev-invented"],
                )
            ],
            markdown="<script>unsafe()</script>",
        )


def command(mode: ResearchMode = ResearchMode.BALANCED) -> ResearchCommand:
    inquiry = Inquiry(question="Does the proposition hold?", mode=mode)
    return ResearchCommand(run_id="run-test", inquiry=inquiry, model="mercury", mode=mode)


def test_research_command_round_trips_through_json_graph_state() -> None:
    original = command(ResearchMode.THOROUGH)

    payload = json.loads(json.dumps(original.to_payload()))
    restored = ResearchCommand.from_payload(payload)

    assert restored == original


@pytest.mark.asyncio
async def test_engine_emits_domain_events_and_enforces_evidence_boundary() -> None:
    source = TrackingEvidenceSource()
    engine = AbundanceResearchEngine(FakePlanner(), [source], InventingSynthesizer())

    events = [event async for event in engine.stream(command())]

    event_types = [event.type for event in events]
    assert event_types[0] == "inquiry.scoping"
    assert event_types[-3:] == ["report.completed", "run.metrics", "run.completed"]
    assert event_types.count("evidence.discovered") == 4
    assert source.max_active <= 3

    completed = events[-3]
    report = completed.data["report"]
    assert report["inquiry_id"] != "wrong-inquiry"
    assert [item["id"] for item in report["evidence"]] != ["ev-invented"]
    assert all("excerpt" not in item for item in report["evidence"])
    assert report["claims"][0]["evidence_ids"] == [report["evidence"][0]["id"]]
    assert "<script>" not in completed.data["content"]
    assert completed.data["evaluation"]["broken_evidence_links"] == 0
    assert events[-2].data["metrics"]["duration_ms"] >= 0
    assert events[-2].data["metrics"]["evidence_count"] == 4
    manifest = events[-2].data["metrics"]["manifest"]
    assert manifest["schema_version"] == "1.0"
    assert manifest["graph_version"] == "research-graph-v1"
    assert manifest["outcome"] == "completed"
    assert manifest["requested_model"] == "mercury"

    graph_nodes = set(engine.workflow.compiled.get_graph().nodes)
    assert graph_nodes == {
        "__start__",
        "scope_inquiry",
        "create_plan",
        "collect_evidence",
        "review_evidence",
        "synthesize_report",
        "__end__",
    }
    assert "langgraph" not in "".join(event.model_dump_json() for event in events).casefold()


class FailingEvidenceSource:
    name = "failing-source"

    async def search(self, unit: ResearchUnit, *, max_results: int) -> list[EvidenceRecord]:
        raise ResearchFailure(
            FailureCode.PROVIDER_UNAVAILABLE,
            "Die Testquelle ist nicht verfügbar.",
            retryable=True,
            cause=RuntimeError("private provider details"),
        )


@pytest.mark.asyncio
async def test_engine_never_streams_private_provider_errors() -> None:
    engine = AbundanceResearchEngine(FakePlanner(), [FailingEvidenceSource()], InventingSynthesizer())

    events = [event async for event in engine.stream(command(ResearchMode.QUICK))]

    assert events[-1].type == "run.failed"
    assert events[-2].type == "run.metrics"
    assert events[-2].data["metrics"]["duration_ms"] >= 0
    assert events[-2].data["metrics"]["manifest"]["outcome"] == "failed"
    assert (
        events[-2].data["metrics"]["manifest"]["failure_code"]
        == "provider_unavailable"
    )
    payload = events[-1].model_dump_json()
    assert "private provider details" not in payload
    assert events[-1].data["code"] == "provider_unavailable"
    assert events[-1].data["correlation_id"] == "run-test"


class MixedSafetyEvidenceSource:
    name = "mixed-source"

    async def search(self, unit: ResearchUnit, *, max_results: int) -> list[EvidenceRecord]:
        return [
            EvidenceRecord(
                id=f"ev-safe-{unit.id}",
                title="Safe source",
                url=f"https://example.org/{unit.id}?utm_campaign=private",
                excerpt="Safe evidence",
                research_unit_id=unit.id,
            ),
            EvidenceRecord(
                id=f"ev-unsafe-{unit.id}",
                title="Unsafe source",
                url="javascript:alert(document.domain)",
                excerpt="Untrusted evidence",
                research_unit_id=unit.id,
            ),
        ][:max_results]


@pytest.mark.asyncio
async def test_engine_streams_only_policy_admitted_evidence() -> None:
    engine = AbundanceResearchEngine(
        FakePlanner(),
        [MixedSafetyEvidenceSource()],
        InventingSynthesizer(),
    )

    events = [event async for event in engine.stream(command(ResearchMode.QUICK))]
    discovered = [event for event in events if event.type == "evidence.discovered"]

    assert discovered
    assert all(event.data["evidence"]["url"].startswith("https://") for event in discovered)
    assert all("utm_campaign" not in event.data["evidence"]["url"] for event in discovered)
    assert "javascript:" not in "".join(event.model_dump_json() for event in events)


@pytest.mark.asyncio
async def test_graph_checkpoint_contains_serializable_abundance_state() -> None:
    checkpointer = InMemorySaver()
    engine = AbundanceResearchEngine(
        FakePlanner(),
        [TrackingEvidenceSource()],
        InventingSynthesizer(),
        checkpointer=checkpointer,
    )

    events = [event async for event in engine.stream(command(ResearchMode.QUICK))]
    snapshot = await engine.workflow.compiled.aget_state(
        {"configurable": {"thread_id": "run-test"}}
    )

    assert events[-1].type == "run.completed"
    assert snapshot.values["report"]["title"] == "Bound report"
    json.dumps(snapshot.values)


class BlockingEvidenceSource:
    name = "blocking-source"

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()

    async def search(self, unit: ResearchUnit, *, max_results: int) -> list[EvidenceRecord]:
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled.set()
            raise
        return []


@pytest.mark.asyncio
async def test_stream_cancellation_reaches_running_graph_node() -> None:
    source = BlockingEvidenceSource()
    engine = AbundanceResearchEngine(FakePlanner(), [source], InventingSynthesizer())

    async def consume() -> None:
        async for _ in engine.stream(command(ResearchMode.QUICK)):
            pass

    task = asyncio.create_task(consume())
    await asyncio.wait_for(source.started.wait(), timeout=1)
    await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.wait_for(source.cancelled.wait(), timeout=1)
