"""Streaming application service backed by an Abundance LangGraph workflow."""

from __future__ import annotations

import asyncio
import logging
import time
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
    AbundanceResearchGraph,
    ResearchGraphState,
)
from abundance_research.application.policy import ResearchCapabilityPolicy
from abundance_research.events import ResearchEvent
from abundance_research.observability import ModelUsage, RunMetrics

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
        self.workflow.begin_run(command.run_id, policy.limits.max_concurrency)
        started = time.perf_counter()
        stage_started = started
        current_stage: str | None = None
        stage_durations: dict[str, int] = {}
        event_count = 0
        evidence_count = 0
        claim_count = 0
        metrics_emitted = False

        def finish_metrics(now: float) -> RunMetrics:
            nonlocal current_stage, stage_started, metrics_emitted
            if current_stage is not None:
                stage_durations[current_stage] = stage_durations.get(current_stage, 0) + int(
                    (now - stage_started) * 1000
                )
                current_stage = None
            usage = ModelUsage()
            for reporter in self._usage_reporters:
                usage = usage.add(reporter.drain_usage(command.inquiry.id))
            metrics_emitted = True
            return RunMetrics(
                duration_ms=int((now - started) * 1000),
                stage_duration_ms=stage_durations,
                event_count=event_count,
                evidence_count=evidence_count,
                claim_count=claim_count,
                model=command.model,
                mode=command.mode.value,
                usage=usage,
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
                event_count += 1
                next_stage = event.stage.value if event.stage is not None else current_stage
                now = time.perf_counter()
                if next_stage != current_stage:
                    if current_stage is not None:
                        stage_durations[current_stage] = stage_durations.get(current_stage, 0) + int(
                            (now - stage_started) * 1000
                        )
                    current_stage = next_stage
                    stage_started = now
                if event.type == "run.completed":
                    evidence_count = int(event.data.get("evidence_count", 0))
                    claim_count = int(event.data.get("claim_count", 0))
                    metrics = finish_metrics(now)
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
            logger.info("Research run cancelled", extra={"run_id": command.run_id})
            raise
        except ResearchFailure as exc:
            metrics = finish_metrics(time.perf_counter())
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
            metrics = finish_metrics(time.perf_counter())
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
            if not metrics_emitted:
                for reporter in self._usage_reporters:
                    reporter.drain_usage(command.inquiry.id)
            self.workflow.finish_run(command.run_id)
