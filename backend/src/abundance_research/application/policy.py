"""Code-enforced limits for research scope and evidence admission."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from abundance_research.application.errors import FailureCode, ResearchFailure
from abundance_research.domain import (
    EvidenceRecord,
    EvidenceRelation,
    ResearchMode,
    ResearchPlan,
    ResearchUnit,
)

_TRACKING_PARAMETERS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
}


@dataclass(frozen=True, slots=True)
class ResearchLimits:
    """Resource limits selected by the user-facing research mode."""

    max_units: int
    max_results_per_unit: int
    max_concurrency: int
    max_total_evidence: int


_MODE_LIMITS = {
    ResearchMode.QUICK: ResearchLimits(3, 3, 1, 9),
    ResearchMode.BALANCED: ResearchLimits(6, 5, 3, 30),
    ResearchMode.THOROUGH: ResearchLimits(10, 8, 5, 60),
}


class ResearchCapabilityPolicy:
    """Authorize research units and normalize untrusted source results."""

    def __init__(self, mode: ResearchMode) -> None:
        """Select immutable limits for one user-facing research mode."""
        self.mode = mode
        self.limits = _MODE_LIMITS[mode]

    def authorize_plan(self, plan: ResearchPlan) -> list[ResearchUnit]:
        """Convert a plan into a bounded, deduplicated set of read-only units."""
        units: list[ResearchUnit] = []
        seen: set[str] = set()

        candidates = [
            *(
                (question, "Test the central research objective", EvidenceRelation.CONTEXT)
                for question in plan.research_questions
            ),
            *(
                (question, "Look for evidence that could overturn the working answer", EvidenceRelation.CHALLENGES)
                for question in plan.falsification_questions
            ),
        ]

        for index, (question, purpose, relation) in enumerate(candidates):
            normalized = " ".join(question.split()).strip()
            identity = normalized.casefold()
            if len(normalized) < 3 or identity in seen:
                continue
            seen.add(identity)
            units.append(
                ResearchUnit(
                    question=normalized[:500],
                    purpose=purpose,
                    relation=relation,
                    priority=max(0, 100 - index),
                )
            )
            if len(units) >= self.limits.max_units:
                break

        if not units:
            raise ResearchFailure(
                FailureCode.INVALID_INPUT,
                "Der Rechercheplan enthält keine ausführbare Evidenzfrage.",
            )
        return units

    def admit_evidence(self, records: list[EvidenceRecord]) -> list[EvidenceRecord]:
        """Reject invalid records, normalize URLs, and deduplicate source material."""
        admitted: list[EvidenceRecord] = []
        seen_urls: set[str] = set()
        for record in records:
            normalized_url = self.normalize_source_url(record.url)
            if not normalized_url or normalized_url in seen_urls:
                continue
            if not record.excerpt.strip() or not record.title.strip():
                continue
            seen_urls.add(normalized_url)
            admitted.append(record.model_copy(update={"url": normalized_url}))
            if len(admitted) >= self.limits.max_total_evidence:
                break
        return admitted

    @staticmethod
    def normalize_source_url(url: str) -> str | None:
        """Allow HTTP(S) evidence URLs and remove fragments and tracking parameters."""
        try:
            parts = urlsplit(url.strip())
            port = parts.port
        except ValueError:
            return None
        if (
            parts.scheme not in {"http", "https"}
            or not parts.hostname
            or parts.username
            or parts.password
        ):
            return None

        filtered_query = [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if not key.casefold().startswith("utm_") and key.casefold() not in _TRACKING_PARAMETERS
        ]
        host = parts.hostname.casefold()
        if port:
            host = f"{host}:{port}"
        return urlunsplit(
            (
                parts.scheme.casefold(),
                host,
                parts.path or "/",
                urlencode(filtered_query, doseq=True),
                "",
            )
        )
