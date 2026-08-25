"""Reproducible quality-gate harness for Abundance research reports."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from abundance_research.application.contracts import ResearchCommand
from abundance_research.bootstrap import build_research_engine
from abundance_research.domain import Inquiry, ResearchMode
from abundance_research.evaluation import ReportEvaluation


class EvalExpectation(BaseModel):
    """Deterministic thresholds for one reference inquiry."""

    min_sources: int = Field(default=3, ge=1, le=50)
    min_claim_evidence_coverage: float = Field(default=0.8, ge=0, le=1)
    min_challenged_claim_ratio: float = Field(default=0.2, ge=0, le=1)
    min_primary_source_ratio: float = Field(default=0.0, ge=0, le=1)
    min_focus_term_coverage: float = Field(default=0.5, ge=0, le=1)
    max_duration_ms: int | None = Field(default=None, ge=1)
    max_cost_usd: float | None = Field(default=None, ge=0)


class EvalCase(BaseModel):
    """One versioned, domain-representative research inquiry."""

    id: str = Field(pattern=r"^[a-z0-9-]+$")
    category: str = Field(min_length=2, max_length=80)
    inquiry: str = Field(min_length=10, max_length=2000)
    mode: ResearchMode = ResearchMode.BALANCED
    focus_terms: list[str] = Field(min_length=2, max_length=12)
    expectations: EvalExpectation = Field(default_factory=EvalExpectation)


class EvalDataset(BaseModel):
    """A bounded regression suite treated as a source-controlled fixture."""

    version: str
    cases: list[EvalCase] = Field(min_length=20, max_length=50)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> EvalDataset:
        """Reject ambiguous case identifiers and insufficient domain breadth."""
        ids = [case.id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("eval case identifiers must be unique")
        if len({case.category for case in self.cases}) < 6:
            raise ValueError("eval dataset must cover at least six categories")
        return self


class EvalObservation(BaseModel):
    """Provider-independent output captured from one research run."""

    content: str
    evaluation: ReportEvaluation
    metrics: dict[str, Any] = Field(default_factory=dict)


class EvalResult(BaseModel):
    """Explain why one observation passed or failed its case contract."""

    case_id: str
    passed: bool
    failures: list[str] = Field(default_factory=list)
    focus_term_coverage: float = Field(ge=0, le=1)
    evaluation: ReportEvaluation
    metrics: dict[str, Any] = Field(default_factory=dict)


class EvalRunReport(BaseModel):
    """Machine-readable comparison report for one or more model aliases."""

    dataset_version: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    results_by_model: dict[str, list[EvalResult]]

    def pass_rate(self, model: str) -> float:
        """Return the fraction of cases meeting every deterministic threshold."""
        results = self.results_by_model.get(model, [])
        return sum(result.passed for result in results) / len(results) if results else 0.0


def load_dataset(path: Path) -> EvalDataset:
    """Load and validate a versioned JSON dataset."""
    return EvalDataset.model_validate_json(path.read_text(encoding="utf-8"))


def score_observation(case: EvalCase, observation: EvalObservation) -> EvalResult:
    """Score relevance, evidence structure, latency, and known provider cost."""
    expectation = case.expectations
    evaluation = observation.evaluation
    normalized_content = observation.content.casefold()
    matched_terms = sum(term.casefold() in normalized_content for term in case.focus_terms)
    focus_coverage = matched_terms / len(case.focus_terms)
    failures: list[str] = []
    checks = (
        (evaluation.total_sources >= expectation.min_sources, "insufficient_sources"),
        (
            evaluation.claim_evidence_coverage >= expectation.min_claim_evidence_coverage,
            "insufficient_claim_evidence_coverage",
        ),
        (
            evaluation.challenged_claim_ratio >= expectation.min_challenged_claim_ratio,
            "insufficient_counterevidence",
        ),
        (
            evaluation.primary_source_ratio >= expectation.min_primary_source_ratio,
            "insufficient_primary_sources",
        ),
        (evaluation.broken_evidence_links == 0, "broken_evidence_links"),
        (focus_coverage >= expectation.min_focus_term_coverage, "insufficient_topic_focus"),
    )
    failures.extend(reason for passed, reason in checks if not passed)
    duration = observation.metrics.get("duration_ms")
    if expectation.max_duration_ms is not None and (
        not isinstance(duration, int) or duration > expectation.max_duration_ms
    ):
        failures.append("duration_budget_exceeded")
    cost = observation.metrics.get("usage", {}).get("cost_usd")
    if expectation.max_cost_usd is not None and (
        not isinstance(cost, int | float) or cost > expectation.max_cost_usd
    ):
        failures.append("cost_budget_exceeded")
    return EvalResult(
        case_id=case.id,
        passed=not failures,
        failures=failures,
        focus_term_coverage=focus_coverage,
        evaluation=evaluation,
        metrics=observation.metrics,
    )


async def run_live_case(case: EvalCase, model: str) -> EvalResult:
    """Execute a case with configured providers and retain only public output."""
    engine = build_research_engine()
    inquiry = Inquiry(question=case.inquiry, mode=case.mode)
    command = ResearchCommand(
        run_id=f"eval-{uuid4().hex}",
        inquiry=inquiry,
        model=model,
        mode=case.mode,
    )
    content = ""
    evaluation: ReportEvaluation | None = None
    metrics: dict[str, Any] = {}
    async for event in engine.stream(command):
        if event.type == "report.completed":
            content = str(event.data.get("content", ""))
            evaluation = ReportEvaluation.model_validate(event.data.get("evaluation", {}))
        elif event.type == "run.metrics":
            metrics = dict(event.data.get("metrics", {}))
        elif event.type == "run.failed":
            raise RuntimeError(f"Eval run failed with {event.data.get('code', 'unknown')}")
    if evaluation is None:
        raise RuntimeError("Eval run completed without a report evaluation")
    return score_observation(
        case,
        EvalObservation(content=content, evaluation=evaluation, metrics=metrics),
    )


async def run_live_dataset(
    dataset: EvalDataset,
    models: list[str],
    *,
    limit: int | None = None,
) -> EvalRunReport:
    """Run model variants sequentially to keep cost and rate limits explicit."""
    selected_cases = dataset.cases[:limit] if limit is not None else dataset.cases
    results: dict[str, list[EvalResult]] = {}
    for model in models:
        results[model] = [await run_live_case(case, model) for case in selected_cases]
    return EvalRunReport(dataset_version=dataset.version, results_by_model=results)


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line contract used locally and in CI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("evals/reference-cases.json"))
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--models", nargs="+", default=[])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path, default=Path("evals/results/latest.json"))
    parser.add_argument("--min-pass-rate", type=float, default=0.9)
    return parser


async def _main() -> int:
    args = build_parser().parse_args()
    dataset = load_dataset(args.dataset)
    if args.validate_only:
        return 0
    if not args.models:
        raise SystemExit("--models is required unless --validate-only is used")
    report = await run_live_dataset(dataset, args.models, limit=args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return 0 if all(report.pass_rate(model) >= args.min_pass_rate for model in args.models) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
