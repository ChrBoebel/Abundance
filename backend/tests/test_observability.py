from datetime import datetime, timezone

import pytest

from abundance_research.events import ResearchEvent, ResearchStage
from abundance_research.observability import (
    ArtifactKind,
    ArtifactRevision,
    ModelUsage,
    OperationKind,
    OperationOutcome,
    OperationSpan,
    RunOutcome,
    RunTelemetry,
    operation_signal_payload,
    parse_operation_signal,
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
        graph_version="research-graph-v2",
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
    telemetry.record_operation(
        OperationSpan(
            kind=OperationKind.SEARCH,
            operation="evidence.search",
            stage="evidence",
            component="tavily",
            started_at=datetime(2026, 8, 25, 10, 0, 2, tzinfo=timezone.utc),
            duration_ms=120,
            outcome=OperationOutcome.SUCCEEDED,
            result_count=3,
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
    assert metrics.operation_count == 1
    assert metrics.failed_operation_count == 0
    assert metrics.operations[0].component == "tavily"
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
        graph_version="research-graph-v2",
    )
    telemetry.finish(RunOutcome.FAILED, failure_code="provider_unavailable")

    with pytest.raises(RuntimeError):
        telemetry.record_event(ResearchEvent(type="run.completed"))


def test_operation_signal_is_distinct_from_product_events() -> None:
    span = OperationSpan(
        kind=OperationKind.MODEL,
        operation="plan.create",
        stage="planning",
        component="openrouter",
        model="mercury",
        started_at=datetime(2026, 8, 25, 10, tzinfo=timezone.utc),
        duration_ms=42,
        outcome=OperationOutcome.FAILED,
        failure_code="rate_limited",
        retryable=True,
    )

    parsed = parse_operation_signal(operation_signal_payload(span))

    assert parsed == span
    assert parse_operation_signal(ResearchEvent(type="run.completed").model_dump()) is None
