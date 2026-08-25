"""LangGraph workflow for the Abundance research application."""

from __future__ import annotations

import asyncio
import operator
import time
from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime, timezone
from typing import Annotated, Any, TypedDict, TypeVar

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send, StreamWriter

from abundance_research.application.claim_verification import (
    summarize_claim_verifications,
    unavailable_verification_summary,
)
from abundance_research.application.contracts import (
    ClaimVerificationModel,
    EvidenceAssessmentModel,
    EvidenceSource,
    PlanningModel,
    ResearchCommand,
    SynthesisModel,
)
from abundance_research.application.errors import FailureCode, ResearchFailure
from abundance_research.application.evidence_assessment import (
    summarize_evidence_assessments,
    unavailable_assessment_summary,
)
from abundance_research.application.policy import ResearchCapabilityPolicy
from abundance_research.application.rendering import (
    enforce_report_contract,
    finalize_report,
    public_report_payload,
)
from abundance_research.domain import (
    AssessmentStatus,
    ClaimEvidenceVerification,
    ClaimVerificationSummary,
    EvidenceAssessment,
    EvidenceAssessmentSummary,
    EvidenceRecord,
    ResearchPlan,
    ResearchReport,
    ResearchUnit,
    VerificationStatus,
)
from abundance_research.evaluation import evaluate_report
from abundance_research.events import ResearchEvent, ResearchStage
from abundance_research.observability import (
    OperationKind,
    OperationOutcome,
    OperationSpan,
    operation_signal_payload,
)

RESEARCH_GRAPH_VERSION = "research-graph-v4"
OperationResult = TypeVar("OperationResult")


class ResearchGraphState(TypedDict, total=False):
    """JSON-serializable state persisted between workflow supersteps."""

    command: dict[str, Any]
    plan: dict[str, Any]
    units: list[dict[str, Any]]
    unit: dict[str, Any]
    max_results: int
    unit_results: Annotated[list[dict[str, Any]], operator.add]
    evidence: list[dict[str, Any]]
    evidence_assessments: list[dict[str, Any]]
    evidence_assessment_summary: dict[str, Any]
    claim_verifications: list[dict[str, Any]]
    claim_verification_summary: dict[str, Any]
    report: dict[str, Any]
    evaluation: dict[str, Any]


def _emit(writer: StreamWriter, event: ResearchEvent) -> None:
    """Write one framework-independent product event to the custom stream."""
    writer(event.model_dump(mode="json", exclude_none=True))


def _component_name(component: Any, fallback: str) -> str:
    """Return a stable adapter name without leaking its concrete class."""
    name = getattr(component, "name", None)
    return name if isinstance(name, str) and name else fallback


class AbundanceResearchGraph:
    """Compile deterministic research stages around explicit application ports."""

    def __init__(
        self,
        planner: PlanningModel,
        evidence_sources: Sequence[EvidenceSource],
        synthesizer: SynthesisModel,
        *,
        assessor: EvidenceAssessmentModel | None = None,
        verifier: ClaimVerificationModel | None = None,
        verification_model_alias: str | None = None,
        checkpointer: BaseCheckpointSaver[Any] | None = None,
    ) -> None:
        """Bind model and read-only evidence adapters to graph nodes."""
        if not evidence_sources:
            raise ValueError("At least one evidence source is required")
        self._planner = planner
        self._evidence_sources = tuple(evidence_sources)
        self._synthesizer = synthesizer
        self._assessor = assessor
        self._verifier = verifier
        self._verification_model_alias = verification_model_alias
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

    async def _observe_operation(
        self,
        writer: StreamWriter,
        *,
        kind: OperationKind,
        operation: str,
        stage: ResearchStage,
        component: str,
        invoke: Callable[[], Awaitable[OperationResult]],
        model: str | None = None,
        count_results: Callable[[OperationResult], int] | None = None,
    ) -> OperationResult:
        """Measure one logical external call and emit only privacy-safe metadata."""
        started_at = datetime.now(timezone.utc)
        started = time.perf_counter()
        try:
            result = await invoke()
        except ResearchFailure as exc:
            writer(
                operation_signal_payload(
                    OperationSpan(
                        kind=kind,
                        operation=operation,
                        stage=stage.value,
                        component=component,
                        model=model,
                        started_at=started_at,
                        duration_ms=max(0, int((time.perf_counter() - started) * 1000)),
                        outcome=OperationOutcome.FAILED,
                        failure_code=exc.code.value,
                        retryable=exc.retryable,
                    )
                )
            )
            raise
        except Exception:
            writer(
                operation_signal_payload(
                    OperationSpan(
                        kind=kind,
                        operation=operation,
                        stage=stage.value,
                        component=component,
                        model=model,
                        started_at=started_at,
                        duration_ms=max(0, int((time.perf_counter() - started) * 1000)),
                        outcome=OperationOutcome.FAILED,
                        failure_code=FailureCode.PROVIDER_UNAVAILABLE.value,
                        retryable=True,
                    )
                )
            )
            raise
        result_count = count_results(result) if count_results is not None else None
        writer(
            operation_signal_payload(
                OperationSpan(
                    kind=kind,
                    operation=operation,
                    stage=stage.value,
                    component=component,
                    model=model,
                    started_at=started_at,
                    duration_ms=max(0, int((time.perf_counter() - started) * 1000)),
                    outcome=OperationOutcome.SUCCEEDED,
                    result_count=result_count,
                )
            )
        )
        return result

    def _compile(
        self,
        checkpointer: BaseCheckpointSaver[Any] | None,
    ) -> CompiledStateGraph:
        builder = StateGraph(ResearchGraphState)
        builder.add_node("scope_inquiry", self._scope_inquiry)
        builder.add_node("create_plan", self._create_plan)
        builder.add_node("collect_evidence", self._collect_evidence)
        builder.add_node("review_evidence", self._review_evidence)
        builder.add_node("assess_evidence", self._assess_evidence)
        builder.add_node("synthesize_report", self._synthesize_report)
        builder.add_node("verify_claims", self._verify_claims)
        builder.add_node("publish_report", self._publish_report)
        builder.add_edge(START, "scope_inquiry")
        builder.add_edge("scope_inquiry", "create_plan")
        builder.add_conditional_edges(
            "create_plan",
            self._dispatch_evidence_units,
            ["collect_evidence"],
        )
        builder.add_edge("collect_evidence", "review_evidence")
        builder.add_edge("review_evidence", "assess_evidence")
        builder.add_edge("assess_evidence", "synthesize_report")
        builder.add_edge("synthesize_report", "verify_claims")
        builder.add_edge("verify_claims", "publish_report")
        builder.add_edge("publish_report", END)
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
        plan = await self._observe_operation(
            writer,
            kind=OperationKind.MODEL,
            operation="plan.create",
            stage=ResearchStage.PLANNING,
            component=_component_name(self._planner, "planning-model"),
            model=command.model,
            invoke=lambda: self._planner.create_plan(command.inquiry, model=command.model),
            count_results=lambda result: (
                len(result.research_questions) + len(result.falsification_questions)
            ),
        )
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
                    async def search_source() -> Sequence[EvidenceRecord]:
                        return await source.search(unit, max_results=max_results)

                    source_records = await self._observe_operation(
                        writer,
                        kind=OperationKind.SEARCH,
                        operation="evidence.search",
                        stage=ResearchStage.EVIDENCE,
                        component=source.name,
                        invoke=search_source,
                        count_results=len,
                    )
                    records.extend(source_records)
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

    async def _assess_evidence(
        self,
        state: ResearchGraphState,
        writer: StreamWriter,
    ) -> dict[str, Any]:
        """Measure semantic evidence quality without changing admitted evidence."""
        command = ResearchCommand.from_payload(state["command"])
        evidence = [EvidenceRecord.model_validate(item) for item in state["evidence"]]
        assessor = self._assessor
        if assessor is None:
            summary = unavailable_assessment_summary(
                len(evidence),
                status=AssessmentStatus.DISABLED,
            )
            return {"evidence_assessment_summary": summary.model_dump(mode="json")}

        _emit(
            writer,
            ResearchEvent(
                type="evidence.assessment.started",
                stage=ResearchStage.REVIEW,
                message="Prüfe Evidenz im Shadow-Modus",
                data={"run_id": command.run_id, "evidence_count": len(evidence)},
            ),
        )
        try:
            async def assess_records() -> Sequence[EvidenceAssessment]:
                return await assessor.assess_evidence(
                    command.inquiry,
                    evidence,
                    model=command.model,
                )

            assessment_result = await self._observe_operation(
                writer,
                kind=OperationKind.MODEL,
                operation="evidence.assess",
                stage=ResearchStage.REVIEW,
                component=_component_name(assessor, "assessment-model"),
                model=command.model,
                invoke=assess_records,
                count_results=lambda result: len(result),
            )
            assessments = list(assessment_result)
        except ResearchFailure as exc:
            summary = unavailable_assessment_summary(
                len(evidence),
                status=AssessmentStatus.UNAVAILABLE,
                failure_code=exc.code.value,
            )
            assessments = []
        except Exception:
            summary = unavailable_assessment_summary(
                len(evidence),
                status=AssessmentStatus.UNAVAILABLE,
                failure_code=FailureCode.PROVIDER_UNAVAILABLE.value,
            )
            assessments = []
        else:
            summary = summarize_evidence_assessments(evidence, assessments)

        _emit(
            writer,
            ResearchEvent(
                type="evidence.assessment.completed",
                stage=ResearchStage.REVIEW,
                message="Shadow-Evidenzprüfung abgeschlossen",
                data={
                    "run_id": command.run_id,
                    "summary": summary.model_dump(mode="json"),
                },
            ),
        )
        return {
            "evidence_assessments": [
                assessment.model_dump(mode="json") for assessment in assessments
            ],
            "evidence_assessment_summary": summary.model_dump(mode="json"),
        }

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
        draft = await self._observe_operation(
            writer,
            kind=OperationKind.MODEL,
            operation="report.synthesize",
            stage=ResearchStage.SYNTHESIS,
            component=_component_name(self._synthesizer, "synthesis-model"),
            model=command.model,
            invoke=lambda: self._synthesizer.synthesize(
                command.inquiry,
                plan,
                evidence,
                model=command.model,
            ),
            count_results=lambda result: len(result.claims),
        )
        report = finalize_report(
            enforce_report_contract(
                draft,
                inquiry_id=command.inquiry.id,
                evidence=evidence,
            )
        )
        return {"report": report.model_dump(mode="json")}

    async def _verify_claims(
        self,
        state: ResearchGraphState,
        writer: StreamWriter,
    ) -> dict[str, Any]:
        """Measure semantic claim support without rewriting the report."""
        command = ResearchCommand.from_payload(state["command"])
        report = ResearchReport.model_validate(state["report"])
        verifier = self._verifier
        if verifier is None:
            summary = unavailable_verification_summary(
                report,
                status=VerificationStatus.DISABLED,
            )
            return {"claim_verification_summary": summary.model_dump(mode="json")}
        verification_model = self._verification_model_alias or command.model

        _emit(
            writer,
            ResearchEvent(
                type="claim.verification.started",
                stage=ResearchStage.SYNTHESIS,
                message="Prüfe die Evidenzbindung der Claims im Shadow-Modus",
                data={
                    "run_id": command.run_id,
                    "claim_count": len(report.claims),
                },
            ),
        )
        try:

            async def verify_report() -> Sequence[ClaimEvidenceVerification]:
                return await verifier.verify_claims(
                    command.inquiry,
                    report,
                    model=verification_model,
                )

            verification_result = await self._observe_operation(
                writer,
                kind=OperationKind.MODEL,
                operation="claim.verify",
                stage=ResearchStage.SYNTHESIS,
                component=_component_name(verifier, "claim-verification-model"),
                model=verification_model,
                invoke=verify_report,
                count_results=lambda result: len(result),
            )
            verifications = list(verification_result)
        except ResearchFailure as exc:
            summary = unavailable_verification_summary(
                report,
                status=VerificationStatus.UNAVAILABLE,
                failure_code=exc.code.value,
            )
            verifications = []
        except Exception:
            summary = unavailable_verification_summary(
                report,
                status=VerificationStatus.UNAVAILABLE,
                failure_code=FailureCode.PROVIDER_UNAVAILABLE.value,
            )
            verifications = []
        else:
            summary = summarize_claim_verifications(report, verifications)

        _emit(
            writer,
            ResearchEvent(
                type="claim.verification.completed",
                stage=ResearchStage.SYNTHESIS,
                message="Shadow-Claim-Verifikation abgeschlossen",
                data={
                    "run_id": command.run_id,
                    "summary": summary.model_dump(mode="json"),
                },
            ),
        )
        return {
            "claim_verifications": [
                verification.model_dump(mode="json") for verification in verifications
            ],
            "claim_verification_summary": summary.model_dump(mode="json"),
        }

    async def _publish_report(
        self,
        state: ResearchGraphState,
        writer: StreamWriter,
    ) -> dict[str, Any]:
        """Publish the unchanged report together with privacy-safe quality metrics."""
        command = ResearchCommand.from_payload(state["command"])
        report = ResearchReport.model_validate(state["report"])
        assessment_summary = EvidenceAssessmentSummary.model_validate(
            state["evidence_assessment_summary"]
        )
        verification_summary = ClaimVerificationSummary.model_validate(
            state["claim_verification_summary"]
        )
        evaluation = evaluate_report(report).model_copy(
            update={
                "evidence_assessment": assessment_summary,
                "claim_verification": verification_summary,
            }
        )
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
                    "evidence_count": len(report.evidence),
                    "claim_count": len(report.claims),
                },
            ),
        )
        return {"evaluation": evaluation.model_dump(mode="json")}
