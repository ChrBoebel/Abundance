from pathlib import Path

import pytest

from abundance_research.application.evidence_assessment import evidence_content_sha256
from abundance_research.assessment_eval_harness import (
    AssessmentEvalReport,
    evaluate_legacy_baseline,
    evaluate_live_assessor,
    load_assessment_dataset,
    score_assessment,
)
from abundance_research.domain import (
    AssessedEvidenceRelation,
    Confidence,
    EvidenceAssessment,
    SourceKind,
)

DATASET = Path(__file__).parents[1] / "evals" / "evidence-assessment-cases.json"
BASELINE = (
    Path(__file__).parents[1]
    / "evals"
    / "baselines"
    / "evidence-assessment-legacy.json"
)


def test_assessment_dataset_is_versioned_unique_and_cross_domain() -> None:
    dataset = load_assessment_dataset(DATASET)

    assert dataset.version == "2026-08-25.1"
    assert len(dataset.cases) == 10
    assert len({case.id for case in dataset.cases}) == 10
    assert len({case.category for case in dataset.cases}) >= 4


def test_legacy_baseline_captures_missing_semantic_assessment() -> None:
    report = evaluate_legacy_baseline(load_assessment_dataset(DATASET))

    assert report.system == "legacy-retrieval-metadata"
    assert report.pass_rate == 0
    assert all(not result.passed for result in report.results)
    failures = {failure for result in report.results for failure in result.failures}
    assert "wrong_relation" in failures
    assert "wrong_primary_status" in failures
    assert "missing_expected_quote" in failures


def test_committed_legacy_baseline_matches_current_fixture() -> None:
    expected = evaluate_legacy_baseline(load_assessment_dataset(DATASET))
    committed = AssessmentEvalReport.model_validate_json(BASELINE.read_text(encoding="utf-8"))

    assert committed == expected


def test_assessment_score_accepts_bound_reviewed_classification() -> None:
    case = load_assessment_dataset(DATASET).cases[0]
    assessment = EvidenceAssessment(
        evidence_id=case.evidence.id,
        relation=AssessedEvidenceRelation.SUPPORTS,
        relevance=Confidence.HIGH,
        source_kind=SourceKind.PRIMARY,
        is_primary=True,
        quote=(
            "The preregistered evaluation found that average travel time fell by "
            "12 percent relative to the matched control corridors."
        ),
        confidence=Confidence.HIGH,
        content_sha256=evidence_content_sha256(case.evidence),
        assessor_version="evidence-assessment-v1",
    )

    result = score_assessment(case, assessment)

    assert result.passed
    assert result.failures == []


@pytest.mark.asyncio
async def test_live_component_eval_scores_bound_assessor_outputs() -> None:
    dataset = load_assessment_dataset(DATASET)
    cases_by_evidence = {case.evidence.id: case for case in dataset.cases}

    class ReviewedFixtureAssessor:
        async def assess_evidence(self, inquiry, evidence, *, model):
            results = []
            for record in evidence:
                case = cases_by_evidence[record.id]
                expected = case.expectation
                results.append(
                    EvidenceAssessment(
                        evidence_id=record.id,
                        relation=expected.relation,
                        relevance=expected.relevance,
                        source_kind=expected.source_kind,
                        is_primary=expected.is_primary,
                        quote=record.excerpt if expected.quote_contains else None,
                        limitations=expected.limitation_terms,
                        confidence=Confidence.HIGH,
                        content_sha256=evidence_content_sha256(record),
                        assessor_version="reviewed-fixture-v1",
                    )
                )
            return results

    report = await evaluate_live_assessor(
        dataset,
        ReviewedFixtureAssessor(),
        model="fixture",
    )

    assert report.system == "live:fixture"
    assert report.pass_rate == 1
