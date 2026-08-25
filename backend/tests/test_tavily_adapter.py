import pytest

from abundance_research.adapters.tavily import TavilyEvidenceSource
from abundance_research.domain import EvidenceRelation, ResearchUnit, SourceKind


class FakeTavilyClient:
    def __init__(self) -> None:
        self.query = ""
        self.options: dict[str, object] = {}

    async def search(self, query: str, **kwargs: object) -> dict[str, object]:
        self.query = query
        self.options = kwargs
        return {
            "results": [
                {
                    "title": "Agency report",
                    "url": "https://agency.gov/reports/result",
                    "raw_content": "Direct official evidence",
                    "published_date": "2026-08-20T10:00:00Z",
                    "score": 0.92,
                },
                {"title": "Incomplete", "url": "https://example.org/missing"},
            ]
        }


@pytest.mark.asyncio
async def test_tavily_adapter_uses_one_read_only_bounded_search() -> None:
    client = FakeTavilyClient()
    source = TavilyEvidenceSource(client=client)
    unit = ResearchUnit(
        id="unit-1",
        question="Which official data tests the claim?",
        purpose="Find primary records",
        relation=EvidenceRelation.CHALLENGES,
    )

    records = await source.search(unit, max_results=2)

    assert client.query == unit.question
    assert client.options["max_results"] == 2
    assert client.options["include_images"] is False
    assert len(records) == 1
    assert records[0].relation is EvidenceRelation.CHALLENGES
    assert records[0].assessment.source_kind is SourceKind.PRIMARY
    assert records[0].assessment.is_primary is True
    assert records[0].metadata["provider"] == "tavily"
