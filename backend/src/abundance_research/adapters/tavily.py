"""Read-only Tavily evidence adapter."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from hashlib import sha256
from typing import Any, Protocol
from urllib.parse import urlsplit

from tavily import AsyncTavilyClient

from abundance_research.application.errors import FailureCode, ResearchFailure
from abundance_research.domain import (
    Confidence,
    EvidenceRecord,
    ResearchUnit,
    SourceAssessment,
    SourceKind,
)


class TavilyClient(Protocol):
    """Narrow client surface used by the evidence adapter."""

    async def search(self, query: str, **kwargs: Any) -> Mapping[str, Any]:
        """Return one Tavily search response."""


class TavilyEvidenceSource:
    """Normalize Tavily results into bounded Abundance evidence records."""

    name = "tavily"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: TavilyClient | None = None,
        timeout_seconds: float = 45.0,
        max_excerpt_chars: int = 12000,
    ) -> None:
        """Initialize a read-only client or accept a test double."""
        if client is None and not api_key:
            raise ResearchFailure(
                FailureCode.CONFIGURATION,
                "Die Evidenzsuche ist nicht konfiguriert.",
            )
        self._client: TavilyClient = client or AsyncTavilyClient(api_key=api_key)
        self._timeout_seconds = timeout_seconds
        self._max_excerpt_chars = max_excerpt_chars

    async def search(
        self,
        unit: ResearchUnit,
        *,
        max_results: int,
    ) -> Sequence[EvidenceRecord]:
        """Search once for a policy-approved question and normalize the response."""
        try:
            response = await self._client.search(
                unit.question,
                search_depth="advanced",
                max_results=max_results,
                include_answer=False,
                include_raw_content="text",
                include_images=False,
                timeout=self._timeout_seconds,
            )
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            code = FailureCode.RATE_LIMITED if status == 429 else FailureCode.PROVIDER_UNAVAILABLE
            raise ResearchFailure(
                code,
                "Die Evidenzsuche ist vorübergehend nicht verfügbar.",
                retryable=status == 429 or status is None or (isinstance(status, int) and status >= 500),
                cause=exc,
            ) from exc

        results = response.get("results", [])
        if not isinstance(results, list):
            return []
        records: list[EvidenceRecord] = []
        for item in results[:max_results]:
            if not isinstance(item, Mapping):
                continue
            record = self._normalize_result(item, unit)
            if record is not None:
                records.append(record)
        return records

    def _normalize_result(
        self,
        item: Mapping[str, Any],
        unit: ResearchUnit,
    ) -> EvidenceRecord | None:
        url = str(item.get("url") or "").strip()
        title = str(item.get("title") or "").strip()
        excerpt = str(item.get("raw_content") or item.get("content") or "").strip()
        if not url or not title or not excerpt:
            return None

        assessment = self._assess_source(url)
        published_at = self._parse_timestamp(item.get("published_date"))
        evidence_id = f"ev-{sha256(url.encode('utf-8')).hexdigest()[:20]}"
        return EvidenceRecord(
            id=evidence_id,
            title=title[:500],
            url=url[:4000],
            excerpt=excerpt[: self._max_excerpt_chars],
            published_at=published_at,
            assessment=assessment,
            relation=unit.relation,
            research_unit_id=unit.id,
            metadata={
                "provider": self.name,
                "query": unit.question,
                "score": item.get("score"),
            },
        )

    @staticmethod
    def _assess_source(url: str) -> SourceAssessment:
        host = (urlsplit(url).hostname or "").casefold()
        path = urlsplit(url).path.casefold()
        is_government = host.endswith(".gov") or ".gov." in host
        is_academic = host.endswith(".edu") or "arxiv.org" in host or "pubmed" in host
        is_primary = is_government or is_academic or "/docs/" in path or "/documentation/" in path
        kind = (
            SourceKind.PRIMARY
            if is_government
            else SourceKind.ACADEMIC
            if is_academic
            else SourceKind.OTHER
        )
        return SourceAssessment(
            source_kind=kind,
            credibility=Confidence.HIGH if is_primary else Confidence.MEDIUM,
            relevance=Confidence.MEDIUM,
            is_primary=is_primary,
            limitations=[] if is_primary else ["Primary-source status was not established automatically."],
        )

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
