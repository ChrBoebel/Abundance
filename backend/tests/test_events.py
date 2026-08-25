from datetime import timezone

from abundance_research.events import ResearchEvent, ResearchStage


def test_event_serializes_only_public_domain_fields() -> None:
    event = ResearchEvent(
        type="evidence.review.started",
        stage=ResearchStage.REVIEW,
        message="Prüfe Evidenz",
        data={"run_id": "run-1", "evidence_count": 3},
    )

    payload = event.model_dump(mode="json")

    assert payload["type"] == "evidence.review.started"
    assert payload["stage"] == "review"
    assert payload["data"] == {"run_id": "run-1", "evidence_count": 3}
    assert set(payload) == {"type", "stage", "message", "data", "timestamp"}


def test_event_timestamp_is_timezone_aware() -> None:
    event = ResearchEvent(type="run.accepted")

    assert event.timestamp.tzinfo is timezone.utc
