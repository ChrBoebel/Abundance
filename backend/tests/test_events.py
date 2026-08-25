from abundance_research.events import ResearchEventMapper, ResearchStage


def test_mapper_exposes_only_domain_event_contract() -> None:
    mapper = ResearchEventMapper()

    events = mapper.map(
        {
            "event": "on_chain_start",
            "metadata": {"langgraph_node": "review_evidence"},
            "data": {},
        }
    )

    assert len(events) == 1
    assert events[0].type == "evidence.review.started"
    assert events[0].stage is ResearchStage.REVIEW
    assert events[0].data == {}


def test_mapper_emits_report_only_once() -> None:
    mapper = ResearchEventMapper()
    raw_event = {
        "event": "on_chain_end",
        "data": {"output": {"final_report": "# Result"}},
    }

    first = mapper.map(raw_event)
    second = mapper.map(raw_event)

    assert first[0].type == "report.completed"
    assert first[0].data["content"] == "# Result"
    assert second == []
