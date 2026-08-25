from collections.abc import AsyncIterator

from fastapi.testclient import TestClient
from pydantic import SecretStr

from abundance_research.application.contracts import ResearchCommand
from abundance_research.events import ResearchEvent
from abundance_research.settings import AbundanceSettings
from backend_server import create_app


class FakeEngine:
    async def stream(self, command: ResearchCommand) -> AsyncIterator[ResearchEvent]:
        yield ResearchEvent(
            type="report.completed",
            data={"run_id": command.run_id, "content": "# Safe report"},
        )
        yield ResearchEvent(type="run.completed", data={"run_id": command.run_id})


def test_stream_api_uses_domain_contract_and_monotonic_event_ids() -> None:
    client = TestClient(create_app(lambda: FakeEngine()))

    response = client.post(
        "/api/v1/research-runs/stream",
        json={"inquiry": "What does the evidence show?", "model": "mercury"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-run-id"].startswith("run-")
    assert "id: 1\ndata:" in response.text
    assert "id: 2\ndata:" in response.text
    assert '"type":"run.accepted"' in response.text
    assert '"type":"report.completed"' in response.text


def test_stream_api_rejects_unknown_model_before_engine_execution() -> None:
    client = TestClient(create_app(lambda: FakeEngine()))

    response = client.post(
        "/api/v1/research-runs/stream",
        json={"inquiry": "Research this question", "model": "unreviewed/model"},
    )

    assert response.status_code == 422


def test_stream_api_enforces_configured_internal_token() -> None:
    token = "service-token-with-at-least-32-characters"
    settings = AbundanceSettings(internal_api_token=SecretStr(token))
    client = TestClient(create_app(lambda: FakeEngine(), settings=settings))
    payload = {"inquiry": "What does the evidence show?", "model": "mercury"}

    unauthorized = client.post("/api/v1/research-runs/stream", json=payload)
    authorized = client.post(
        "/api/v1/research-runs/stream",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200


def test_readiness_returns_safe_configuration_failure() -> None:
    from abundance_research.application.errors import FailureCode, ResearchFailure

    def unavailable():
        raise ResearchFailure(FailureCode.CONFIGURATION, "Provider setup is incomplete")

    client = TestClient(create_app(unavailable))

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "configuration_error",
        "message": "Provider setup is incomplete",
    }
