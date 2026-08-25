from pathlib import Path

from abundance_research.eval_harness import (
    EvalObservation,
    load_dataset,
    score_observation,
)
from abundance_research.evaluation import ReportEvaluation

DATASET = Path(__file__).parents[1] / "evals" / "reference-cases.json"


def test_reference_dataset_is_bounded_unique_and_cross_domain() -> None:
    dataset = load_dataset(DATASET)

    assert len(dataset.cases) == 30
    assert len({case.id for case in dataset.cases}) == 30
    assert len({case.category for case in dataset.cases}) >= 10


def test_eval_score_explains_quality_gate_failures() -> None:
    case = load_dataset(DATASET).cases[0]
    observation = EvalObservation(
        content="Wärmepumpe Gasheizung Lebenszyklus Emission",
        evaluation=ReportEvaluation(
            total_claims=5,
            total_sources=6,
            claim_evidence_coverage=1,
            citation_integrity=1,
            evidence_utilization=0.75,
            challenged_claim_ratio=0.4,
            primary_source_ratio=0.5,
            source_domain_diversity=0.5,
            broken_evidence_links=0,
        ),
        metrics={"duration_ms": 1000, "usage": {"cost_usd": 0.01}},
    )

    result = score_observation(case, observation)

    assert result.passed
    assert result.failures == []
    assert result.focus_term_coverage == 1
    assert result.checks
    assert all(check.passed for check in result.checks)


def test_eval_score_rejects_uncited_off_topic_output() -> None:
    case = load_dataset(DATASET).cases[0]
    observation = EvalObservation(
        content="A generic answer without the requested concepts.",
        evaluation=ReportEvaluation(
            total_claims=3,
            total_sources=1,
            claim_evidence_coverage=0,
            citation_integrity=0,
            evidence_utilization=0,
            challenged_claim_ratio=0,
            primary_source_ratio=0,
            source_domain_diversity=0,
            broken_evidence_links=2,
            unsupported_high_confidence_claims=1,
        ),
        metrics={"duration_ms": 500000, "usage": {"cost_usd": 10}},
    )

    result = score_observation(case, observation)

    assert not result.passed
    assert "insufficient_sources" in result.failures
    assert "broken_evidence_links" in result.failures
    assert "insufficient_citation_integrity" in result.failures
    assert "unsupported_high_confidence_claims" in result.failures
    assert "insufficient_topic_focus" in result.failures
    assert "duration_budget_exceeded" in result.failures
    assert "cost_budget_exceeded" in result.failures
