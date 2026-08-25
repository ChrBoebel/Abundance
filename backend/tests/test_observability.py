from datetime import datetime, timezone

import pytest

from abundance_research.events import ResearchEvent, ResearchStage
from abundance_research.observability import (
    ArtifactKind,
    ArtifactRevision,
    ModelUsage,
    RunOutcome,
    RunTelemetry,
)


def test_run_telemetry_builds_privacy_safe_reproducibility_manifest() -> None:
    monotonic_values = iter([10.0, 11.0, 13.0, 15.0, 18.0])
    utc_values = iter(
        [
            datetime(2026, 8, 25, 10, tzinfo=timezone.utc),
            datetime(2026, 8, 25, 10, 0, 8, tzinfo=timezone.utc),
        ]
    )
    telemetry = RunTelemetry(
        run_id="run-1",
        inquiry_id="inq-1",
        requested_model="mercury",
        mode="balanced",
        graph_version="research-graph-v1",
        artifacts=[
            ArtifactRevision(
                kind=ArtifactKind.PROMPT,
                name="planning",
                version="planning-v1",
            )
        ],
        monotonic=lambda: next(monotonic_values),
        utcnow=lambda: next(utc_values),
    )

    telemetry.record_event(
        ResearchEvent(type="inquiry.scoping", stage=ResearchStage.INQUIRY)
    )
    telemetry.record_event(
        ResearchEvent(type="plan.created", stage=ResearchStage.PLANNING)
    )
    telemetry.record_event(
        ResearchEvent(
            type="run.completed",
            data={"evidence_count": 6, "claim_count": 2},
        )
    )
    metrics = telemetry.finish(
        RunOutcome.COMPLETED,
        usage=ModelUsage(input_tokens=10, output_tokens=5, total_tokens=15),
    )

    assert metrics.duration_ms == 8000
    assert metrics.stage_duration_ms == {"inquiry": 2000, "planning": 5000}
    assert metrics.event_count == 3
    assert metrics.evidence_count == 6
    assert metrics.claim_count == 2
    assert metrics.manifest is not None
    assert metrics.manifest.outcome is RunOutcome.COMPLETED
    assert metrics.manifest.artifacts[0].version == "planning-v1"
    payload = metrics.model_dump_json()
    assert "question" not in payload
    assert "prompt text" not in payload


def test_run_telemetry_rejects_events_after_finish() -> None:
    telemetry = RunTelemetry(
        run_id="run-1",
        inquiry_id="inq-1",
        requested_model="mercury",
        mode="quick",
        graph_version="research-graph-v1",
    )
    telemetry.finish(RunOutcome.FAILED, failure_code="provider_unavailable")

    with pytest.raises(RuntimeError):
        telemetry.record_event(ResearchEvent(type="run.completed"))
