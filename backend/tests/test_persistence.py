from abundance_research.application.contracts import ResearchCommand
from abundance_research.domain import Inquiry, ResearchMode
from abundance_research.persistence import InMemoryResearchRunRepository, RunFeedback


def command(run_id: str = "run-persisted") -> ResearchCommand:
    inquiry = Inquiry(question="What evidence should be retained?")
    return ResearchCommand(
        run_id=run_id,
        inquiry=inquiry,
        model="mercury",
        mode=ResearchMode.BALANCED,
    )


async def test_memory_repository_preserves_run_feedback_and_capability_share() -> None:
    repository = InMemoryResearchRunRepository()
    research_command = command()

    await repository.create(research_command)
    await repository.complete(
        research_command.run_id,
        {"title": "Durable result", "claims": []},
        {"claim_evidence_coverage": 1.0},
    )
    await repository.record_metrics(research_command.run_id, {"duration_ms": 25})
    feedback_id = await repository.add_feedback(
        RunFeedback(run_id=research_command.run_id, claim_id="claim-1", rating=1)
    )
    token = await repository.create_share(research_command.run_id)

    stored = await repository.get(research_command.run_id)
    shared = await repository.get_shared(token)
    assert stored is not None
    assert stored.status == "completed"
    assert stored.metrics == {"duration_ms": 25}
    assert feedback_id.startswith("feedback-")
    assert shared == stored
    assert await repository.get_shared(f"{token}x") is None


async def test_memory_repository_marks_unsettled_run_cancelled() -> None:
    repository = InMemoryResearchRunRepository()
    research_command = command("run-cancelled")

    await repository.create(research_command)
    await repository.cancel(research_command.run_id)

    stored = await repository.get(research_command.run_id)
    assert stored is not None
    assert stored.status == "cancelled"
