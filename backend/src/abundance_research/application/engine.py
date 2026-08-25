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
    AbundanceResearchGraph,
    ResearchGraphState,
)
from abundance_research.application.policy import ResearchCapabilityPolicy
from abundance_research.events import ResearchEvent

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
        try:
            async for chunk in self.workflow.compiled.astream(
                initial_state,
                config=config,
                stream_mode="custom",
                version="v2",
            ):
                if chunk.get("type") != "custom":
                    continue
                yield ResearchEvent.model_validate(chunk["data"])
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
                data={"run_id": command.run_id, **exc.public_data(command.run_id)},
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
                data={"run_id": command.run_id, **failure.public_data(command.run_id)},
            )
        finally:
            self.workflow.finish_run(command.run_id)
