"""LangGraph workflow for the Abundance research application."""

from __future__ import annotations

import asyncio
import operator
from collections.abc import Sequence
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send, StreamWriter

from abundance_research.application.contracts import (
    EvidenceSource,
    PlanningModel,
    ResearchCommand,
    SynthesisModel,
)
from abundance_research.application.errors import FailureCode, ResearchFailure
from abundance_research.application.policy import ResearchCapabilityPolicy
from abundance_research.application.rendering import (
    enforce_report_contract,
    finalize_report,
    public_report_payload,
)
from abundance_research.domain import EvidenceRecord, ResearchPlan, ResearchUnit
from abundance_research.evaluation import evaluate_report
from abundance_research.events import ResearchEvent, ResearchStage

RESEARCH_GRAPH_VERSION = "research-graph-v1"


class ResearchGraphState(TypedDict, total=False):
    """JSON-serializable state persisted between workflow supersteps."""

    command: dict[str, Any]
    plan: dict[str, Any]
    units: list[dict[str, Any]]
    unit: dict[str, Any]
    max_results: int
    unit_results: Annotated[list[dict[str, Any]], operator.add]
    evidence: list[dict[str, Any]]
    report: dict[str, Any]
    evaluation: dict[str, Any]


def _emit(writer: StreamWriter, event: ResearchEvent) -> None:
    """Write one framework-independent product event to the custom stream."""
    writer(event.model_dump(mode="json", exclude_none=True))


class AbundanceResearchGraph:
    """Compile deterministic research stages around explicit application ports."""

    def __init__(
        self,
        planner: PlanningModel,
        evidence_sources: Sequence[EvidenceSource],
        synthesizer: SynthesisModel,
        *,
        checkpointer: BaseCheckpointSaver[Any] | None = None,
    ) -> None:
        """Bind model and read-only evidence adapters to graph nodes."""
        if not evidence_sources:
            raise ValueError("At least one evidence source is required")
        self._planner = planner
        self._evidence_sources = tuple(evidence_sources)
        self._synthesizer = synthesizer
        self._run_semaphores: dict[str, asyncio.Semaphore] = {}
        self.compiled = self._compile(checkpointer)

    def begin_run(self, run_id: str, max_concurrency: int) -> None:
        """Allocate a run-local concurrency gate outside serializable state."""
        if run_id in self._run_semaphores:
            raise ValueError(f"Research run {run_id!r} is already active")
        self._run_semaphores[run_id] = asyncio.Semaphore(max_concurrency)

    def finish_run(self, run_id: str) -> None:
        """Release ephemeral run resources after success, failure, or cancellation."""
        self._run_semaphores.pop(run_id, None)

    def _compile(
        self,
        checkpointer: BaseCheckpointSaver[Any] | None,
    ) -> CompiledStateGraph:
        builder = StateGraph(ResearchGraphState)
        builder.add_node("scope_inquiry", self._scope_inquiry)
        builder.add_node("create_plan", self._create_plan)
        builder.add_node("collect_evidence", self._collect_evidence)
        builder.add_node("review_evidence", self._review_evidence)
        builder.add_node("synthesize_report", self._synthesize_report)
        builder.add_edge(START, "scope_inquiry")
        builder.add_edge("scope_inquiry", "create_plan")
        builder.add_conditional_edges(
            "create_plan",
            self._dispatch_evidence_units,
            ["collect_evidence"],
        )
        builder.add_edge("collect_evidence", "review_evidence")
        builder.add_edge("review_evidence", "synthesize_report")
        builder.add_edge("synthesize_report", END)
        return builder.compile(checkpointer=checkpointer, name="abundance-research")

    async def _scope_inquiry(
        self,
        state: ResearchGraphState,
        writer: StreamWriter,
    ) -> dict[str, Any]:
        command = ResearchCommand.from_payload(state["command"])
        _emit(
            writer,
            ResearchEvent(
                type="inquiry.scoping",
                stage=ResearchStage.INQUIRY,
                message="Prüfe den Rechercheauftrag",
                data={"run_id": command.run_id},
            ),
        )
        return {}

    async def _create_plan(
        self,
        state: ResearchGraphState,
        writer: StreamWriter,
    ) -> dict[str, Any]:
        command = ResearchCommand.from_payload(state["command"])
        policy = ResearchCapabilityPolicy(command.mode)
        plan = await self._planner.create_plan(command.inquiry, model=command.model)
        units = policy.authorize_plan(plan)
        run_data = {"run_id": command.run_id}
        _emit(
            writer,
            ResearchEvent(
                type="plan.created",
                stage=ResearchStage.PLANNING,
                message="Rechercheplan erstellt",
                data={**run_data, "plan": plan.model_dump(mode="json")},
            ),
        )
        _emit(
            writer,
            ResearchEvent(
                type="evidence.collection.started",
                stage=ResearchStage.EVIDENCE,
                message="Beginne die kontrollierte Evidenzsuche",
                data={**run_data, "unit_count": len(units)},
            ),
        )
        return {
            "plan": plan.model_dump(mode="json"),
            "units": [unit.model_dump(mode="json") for unit in units],
        }

    def _dispatch_evidence_units(self, state: ResearchGraphState) -> list[Send]:
        command = ResearchCommand.from_payload(state["command"])
        max_results = ResearchCapabilityPolicy(command.mode).limits.max_results_per_unit
        return [
            Send(
                "collect_evidence",
                {
                    "command": state["command"],
                    "unit": unit,
                    "max_results": max_results,
                },
            )
            for unit in state["units"]
        ]

    async def _collect_evidence(
        self,
        state: ResearchGraphState,
        writer: StreamWriter,
    ) -> dict[str, Any]:
        command = ResearchCommand.from_payload(state["command"])
        unit = ResearchUnit.model_validate(state["unit"])
        max_results = int(state["max_results"])
        semaphore = self._run_semaphores.get(command.run_id)
        if semaphore is None:
            raise RuntimeError("Research run concurrency gate is not initialized")

        async with semaphore:
            _emit(
                writer,
                ResearchEvent(
                    type="evidence.search.started",
                    stage=ResearchStage.EVIDENCE,
                    message="Durchsuche Quellen",
                    data={
                        "run_id": command.run_id,
                        "unit_id": unit.id,
                        "query": unit.question,
                        "relation": unit.relation.value,
                    },
                ),
            )

            records: list[EvidenceRecord] = []
            for source in self._evidence_sources:
                try:
                    records.extend(await source.search(unit, max_results=max_results))
                except ResearchFailure as exc:
                    _emit(
                        writer,
                        ResearchEvent(
                            type="evidence.search.failed",
                            stage=ResearchStage.EVIDENCE,
                            message=exc.public_message,
                            data={
                                "run_id": command.run_id,
                                "unit_id": unit.id,
                                **exc.public_data(command.run_id),
                            },
                        ),
                    )
                except Exception as exc:
                    failure = ResearchFailure(
                        FailureCode.PROVIDER_UNAVAILABLE,
                        f"Die Evidenzquelle {source.name} ist nicht verfügbar.",
                        retryable=True,
                        cause=exc,
                    )
                    _emit(
                        writer,
                        ResearchEvent(
                            type="evidence.search.failed",
                            stage=ResearchStage.EVIDENCE,
                            message=failure.public_message,
                            data={
                                "run_id": command.run_id,
                                "unit_id": unit.id,
                                **failure.public_data(command.run_id),
                            },
                        ),
                    )
        return {"unit_results": [record.model_dump(mode="json") for record in records]}

    async def _review_evidence(
        self,
        state: ResearchGraphState,
        writer: StreamWriter,
    ) -> dict[str, Any]:
        command = ResearchCommand.from_payload(state["command"])
        policy = ResearchCapabilityPolicy(command.mode)
        collected = [EvidenceRecord.model_validate(item) for item in state["unit_results"]]
        evidence = policy.admit_evidence(collected)
        if not evidence:
            raise ResearchFailure(
                FailureCode.PROVIDER_UNAVAILABLE,
                "Es konnte keine belastbare Evidenz aufgenommen werden.",
                retryable=True,
            )

        for record in evidence:
            _emit(
                writer,
                ResearchEvent(
                    type="evidence.discovered",
                    stage=ResearchStage.EVIDENCE,
                    message="Evidenz aufgenommen",
                    data={
                        "run_id": command.run_id,
                        "evidence": {
                            "id": record.id,
                            "title": record.title,
                            "url": record.url,
                            "relation": record.relation.value,
                            "source_kind": record.assessment.source_kind.value,
                            "is_primary": record.assessment.is_primary,
                            "published_at": (
                                record.published_at.isoformat() if record.published_at else None
                            ),
                        },
                    },
                ),
            )
        _emit(
            writer,
            ResearchEvent(
                type="evidence.review.started",
                stage=ResearchStage.REVIEW,
                message="Prüfe Evidenz und Gegenbelege",
                data={"run_id": command.run_id, "evidence_count": len(evidence)},
            ),
        )
        return {"evidence": [record.model_dump(mode="json") for record in evidence]}

    async def _synthesize_report(
        self,
        state: ResearchGraphState,
        writer: StreamWriter,
    ) -> dict[str, Any]:
        command = ResearchCommand.from_payload(state["command"])
        plan = ResearchPlan.model_validate(state["plan"])
        evidence = [EvidenceRecord.model_validate(item) for item in state["evidence"]]
        _emit(
            writer,
            ResearchEvent(
                type="synthesis.started",
                stage=ResearchStage.SYNTHESIS,
                message="Erstelle die evidenzgebundene Synthese",
                data={"run_id": command.run_id},
            ),
        )
        draft = await self._synthesizer.synthesize(
            command.inquiry,
            plan,
            evidence,
            model=command.model,
        )
        report = finalize_report(
            enforce_report_contract(
                draft,
                inquiry_id=command.inquiry.id,
                evidence=evidence,
            )
        )
        evaluation = evaluate_report(report)
        _emit(
            writer,
            ResearchEvent(
                type="report.completed",
                stage=ResearchStage.SYNTHESIS,
                message="Recherchebericht abgeschlossen",
                data={
                    "run_id": command.run_id,
                    "content": report.markdown,
                    "report": public_report_payload(report),
                    "evaluation": evaluation.model_dump(mode="json"),
                },
            ),
        )
        _emit(
            writer,
            ResearchEvent(
                type="run.completed",
                message="Recherche abgeschlossen",
                data={
                    "run_id": command.run_id,
                    "evidence_count": len(evidence),
                    "claim_count": len(report.claims),
                },
            ),
        )
        return {
            "report": report.model_dump(mode="json"),
            "evaluation": evaluation.model_dump(mode="json"),
        }
