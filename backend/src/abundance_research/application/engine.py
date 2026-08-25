"""Streaming application service backed by an Abundance LangGraph workflow."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator, Sequence
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver

from abundance_research.application.contracts import (
    EvidenceSource,
    PlanningModel,
    ResearchCommand,
    SynthesisModel,
)
from abundance_research.application.errors import FailureCode, ResearchFailure
from abundance_research.application.graph import (
    RESEARCH_GRAPH_VERSION,
    AbundanceResearchGraph,
    ResearchGraphState,
)
from abundance_research.application.policy import ResearchCapabilityPolicy
from abundance_research.events import ResearchEvent
from abundance_research.observability import (
    ArtifactKind,
    ArtifactRevision,
    ModelUsage,
    RunMetrics,
    RunOutcome,
    RunTelemetry,
)

logger = logging.getLogger(__name__)


class AbundanceResearchEngine:
    """Expose stable product events while LangGraph executes internal stages."""

    def __init__(
        self,
        planner: PlanningModel,
        evidence_sources: Sequence[EvidenceSource],
        synthesizer: SynthesisModel,
        *,
        checkpointer: BaseCheckpointSaver[Any] | None = None,
    ) -> None:
        """Compile the graph with explicit model and read-only search ports."""
        self.workflow = AbundanceResearchGraph(
            planner,
            evidence_sources,
            synthesizer,
            checkpointer=checkpointer,
        )
        usage_reporters: list[Any] = []
        for reporter in (planner, synthesizer):
            if callable(getattr(reporter, "drain_usage", None)) and not any(
                existing is reporter for existing in usage_reporters
            ):
                usage_reporters.append(reporter)
        self._usage_reporters = tuple(usage_reporters)
        artifact_reporters: list[Any] = []
        for reporter in (planner, synthesizer):
            if callable(getattr(reporter, "observability_artifacts", None)) and not any(
                existing is reporter for existing in artifact_reporters
            ):
                artifact_reporters.append(reporter)
        self._artifact_reporters = tuple(artifact_reporters)

    async def stream(self, command: ResearchCommand) -> AsyncGenerator[ResearchEvent, None]:
        """Execute one graph run and translate only custom product events."""
        policy = ResearchCapabilityPolicy(command.mode)
        initial_state: ResearchGraphState = {
            "command": command.to_payload(),
            "unit_results": [],
        }
        config: RunnableConfig = {
            "configurable": {"thread_id": command.run_id},
            "run_name": "Abundance research",
            "tags": ["abundance", f"mode:{command.mode.value}"],
            "metadata": {"run_id": command.run_id},
        }
        artifacts = [
            ArtifactRevision(
                kind=ArtifactKind.GRAPH,
                name="abundance-research",
                version=RESEARCH_GRAPH_VERSION,
            )
        ]
        for reporter in self._artifact_reporters:
            try:
                artifacts.extend(reporter.observability_artifacts(command.model))
            except Exception:
                logger.warning(
                    "Runtime artifact discovery failed",
                    extra={"run_id": command.run_id},
                )
        artifacts = list(
            {
                (artifact.kind, artifact.name, artifact.version): artifact
                for artifact in artifacts
            }.values()
        )
        telemetry = RunTelemetry(
            run_id=command.run_id,
            inquiry_id=command.inquiry.id,
            requested_model=command.model,
            mode=command.mode.value,
            graph_version=RESEARCH_GRAPH_VERSION,
            artifacts=artifacts,
        )
        self.workflow.begin_run(command.run_id, policy.limits.max_concurrency)

        def finish_metrics(
            outcome: RunOutcome,
            *,
            failure_code: str | None = None,
        ) -> RunMetrics:
            usage = ModelUsage()
            for reporter in self._usage_reporters:
                usage = usage.add(reporter.drain_usage(command.inquiry.id))
            return telemetry.finish(
                outcome,
                usage=usage,
                failure_code=failure_code,
            )

        try:
            async for chunk in self.workflow.compiled.astream(
                initial_state,
                config=config,
                stream_mode="custom",
                version="v2",
            ):
                if chunk.get("type") != "custom":
                    continue
                event = ResearchEvent.model_validate(chunk["data"])
                telemetry.record_event(event)
                if event.type == "run.completed":
                    metrics = finish_metrics(RunOutcome.COMPLETED)
                    logger.info(
                        "Research run completed",
                        extra={"run_id": command.run_id, "duration_ms": metrics.duration_ms},
                    )
                    yield ResearchEvent(
                        type="run.metrics",
                        message="Laufmetriken erfasst",
                        data={
                            "run_id": command.run_id,
                            "metrics": metrics.model_dump(mode="json"),
                        },
                    )
                yield event
        except asyncio.CancelledError:
            cancelled_metrics = (
                finish_metrics(RunOutcome.CANCELLED)
                if not telemetry.finished
                else None
            )
            logger.info(
                "Research run cancelled",
                extra={
                    "run_id": command.run_id,
                    "duration_ms": (
                        cancelled_metrics.duration_ms
                        if cancelled_metrics is not None
                        else None
                    ),
                },
            )
            raise
        except ResearchFailure as exc:
            metrics = finish_metrics(RunOutcome.FAILED, failure_code=exc.code.value)
            yield ResearchEvent(
                type="run.metrics",
                message="Laufmetriken erfasst",
                data={"run_id": command.run_id, "metrics": metrics.model_dump(mode="json")},
            )
            logger.warning(
                "Research run failed: %s",
                exc.code.value,
                extra={"run_id": command.run_id, "failure_code": exc.code.value},
            )
            yield ResearchEvent(
                type="run.failed",
                message=exc.public_message,
                data={"run_id": command.run_id, **exc.public_data(command.run_id)},
            )
        except Exception:
            metrics = finish_metrics(RunOutcome.FAILED, failure_code=FailureCode.INTERNAL.value)
            yield ResearchEvent(
                type="run.metrics",
                message="Laufmetriken erfasst",
                data={"run_id": command.run_id, "metrics": metrics.model_dump(mode="json")},
            )
            logger.exception("Unexpected research failure", extra={"run_id": command.run_id})
            failure = ResearchFailure(
                FailureCode.INTERNAL,
                "Die Recherche konnte nicht abgeschlossen werden.",
            )
            yield ResearchEvent(
                type="run.failed",
                message=failure.public_message,
                data={"run_id": command.run_id, **failure.public_data(command.run_id)},
            )
        finally:
            if not telemetry.finished:
                for reporter in self._usage_reporters:
                    reporter.drain_usage(command.inquiry.id)
            self.workflow.finish_run(command.run_id)
