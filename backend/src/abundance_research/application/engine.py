"""Abundance-owned orchestration for evidence-led research runs."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass

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
from abundance_research.domain import EvidenceRecord, ResearchUnit
from abundance_research.evaluation import evaluate_report
from abundance_research.events import ResearchEvent, ResearchStage

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class UnitCollection:
    """Evidence and safe failures returned by one research unit."""

    unit: ResearchUnit
    evidence: list[EvidenceRecord]
    failures: list[ResearchFailure]


class AbundanceResearchEngine:
    """Coordinate planning, bounded evidence collection, and synthesis."""

    def __init__(
        self,
        planner: PlanningModel,
        evidence_sources: Sequence[EvidenceSource],
        synthesizer: SynthesisModel,
    ) -> None:
        """Inject explicit read-only capabilities into the application service."""
        if not evidence_sources:
            raise ValueError("At least one evidence source is required")
        self._planner = planner
        self._evidence_sources = tuple(evidence_sources)
        self._synthesizer = synthesizer

    async def stream(self, command: ResearchCommand) -> AsyncIterator[ResearchEvent]:
        """Run one research command and emit only stable Abundance domain events."""
        policy = ResearchCapabilityPolicy(command.mode)
        run_data = {"run_id": command.run_id}
        tasks: list[asyncio.Task[UnitCollection]] = []

        try:
            yield ResearchEvent(
                type="inquiry.scoping",
                stage=ResearchStage.INQUIRY,
                message="Prüfe den Rechercheauftrag",
                data=run_data,
            )
            plan = await self._planner.create_plan(command.inquiry, model=command.model)
            units = policy.authorize_plan(plan)
            yield ResearchEvent(
                type="plan.created",
                stage=ResearchStage.PLANNING,
                message="Rechercheplan erstellt",
                data={**run_data, "plan": plan.model_dump(mode="json")},
            )
            yield ResearchEvent(
                type="evidence.collection.started",
                stage=ResearchStage.EVIDENCE,
                message="Beginne die kontrollierte Evidenzsuche",
                data={**run_data, "unit_count": len(units)},
            )

            semaphore = asyncio.Semaphore(policy.limits.max_concurrency)
            for unit in units:
                yield ResearchEvent(
                    type="evidence.search.started",
                    stage=ResearchStage.EVIDENCE,
                    message="Durchsuche Quellen",
                    data={
                        **run_data,
                        "unit_id": unit.id,
                        "query": unit.question,
                        "relation": unit.relation.value,
                    },
                )
                tasks.append(
                    asyncio.create_task(
                        self._collect_unit(
                            unit,
                            semaphore=semaphore,
                            max_results=policy.limits.max_results_per_unit,
                        )
                    )
                )

            collected: list[EvidenceRecord] = []
            for pending in asyncio.as_completed(tasks):
                result = await pending
                for failure in result.failures:
                    yield ResearchEvent(
                        type="evidence.search.failed",
                        stage=ResearchStage.EVIDENCE,
                        message=failure.public_message,
                        data={
                            **run_data,
                            "unit_id": result.unit.id,
                            **failure.public_data(command.run_id),
                        },
                    )
                for record in result.evidence:
                    collected.append(record)

            evidence = policy.admit_evidence(collected)
            if not evidence:
                raise ResearchFailure(
                    FailureCode.PROVIDER_UNAVAILABLE,
                    "Es konnte keine belastbare Evidenz aufgenommen werden.",
                    retryable=True,
                )

            for record in evidence:
                yield ResearchEvent(
                    type="evidence.discovered",
                    stage=ResearchStage.EVIDENCE,
                    message="Evidenz aufgenommen",
                    data={
                        **run_data,
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
                )

            yield ResearchEvent(
                type="evidence.review.started",
                stage=ResearchStage.REVIEW,
                message="Prüfe Evidenz und Gegenbelege",
                data={**run_data, "evidence_count": len(evidence)},
            )
            yield ResearchEvent(
                type="synthesis.started",
                stage=ResearchStage.SYNTHESIS,
                message="Erstelle die evidenzgebundene Synthese",
                data=run_data,
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
            yield ResearchEvent(
                type="report.completed",
                stage=ResearchStage.SYNTHESIS,
                message="Recherchebericht abgeschlossen",
                data={
                    **run_data,
                    "content": report.markdown,
                    "report": public_report_payload(report),
                    "evaluation": evaluation.model_dump(mode="json"),
                },
            )
            yield ResearchEvent(
                type="run.completed",
                message="Recherche abgeschlossen",
                data={
                    **run_data,
                    "evidence_count": len(evidence),
                    "claim_count": len(report.claims),
                },
            )
        except asyncio.CancelledError:
            logger.info("Research run cancelled", extra={"run_id": command.run_id})
            raise
        except ResearchFailure as exc:
            logger.warning(
                "Research run failed: %s",
                exc.code.value,
                extra={"run_id": command.run_id, "failure_code": exc.code.value},
            )
            yield ResearchEvent(
                type="run.failed",
                message=exc.public_message,
                data={**run_data, **exc.public_data(command.run_id)},
            )
        except Exception:
            logger.exception("Unexpected research failure", extra={"run_id": command.run_id})
            failure = ResearchFailure(
                FailureCode.INTERNAL,
                "Die Recherche konnte nicht abgeschlossen werden.",
            )
            yield ResearchEvent(
                type="run.failed",
                message=failure.public_message,
                data={**run_data, **failure.public_data(command.run_id)},
            )
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    async def _collect_unit(
        self,
        unit: ResearchUnit,
        *,
        semaphore: asyncio.Semaphore,
        max_results: int,
    ) -> UnitCollection:
        async with semaphore:
            evidence: list[EvidenceRecord] = []
            failures: list[ResearchFailure] = []
            for source in self._evidence_sources:
                try:
                    records = await source.search(unit, max_results=max_results)
                    evidence.extend(records)
                except ResearchFailure as exc:
                    failures.append(exc)
                except Exception as exc:
                    failures.append(
                        ResearchFailure(
                            FailureCode.PROVIDER_UNAVAILABLE,
                            f"Die Evidenzquelle {source.name} ist nicht verfügbar.",
                            retryable=True,
                            cause=exc,
                        )
                    )
            return UnitCollection(unit=unit, evidence=evidence, failures=failures)
