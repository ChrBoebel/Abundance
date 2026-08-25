import asyncio
from pathlib import Path

import pytest

from abundance_research.application.claim_verification import claim_content_sha256
from abundance_research.application.evidence_assessment import evidence_content_sha256
from abundance_research.claim_verification_eval_harness import (
    ClaimVerificationCandidateArtifact,
    ClaimVerificationEvalReport,
    ClaimVerificationEvalSuite,
    decide_promotion,
    evaluate_legacy_baseline,
    evaluate_live_verifier,
    load_claim_verification_dataset,
    score_claim_verification,
)
from abundance_research.domain import (
    ClaimEvidenceVerification,
    Confidence,
    ResearchReport,
)

DATASET = Path(__file__).parents[1] / "evals" / "claim-verification-cases.json"
BASELINE = (
    Path(__file__).parents[1]
    / "evals"
    / "baselines"
    / "claim-verification-legacy.json"
)
ACCEPTED_CANDIDATE = (
    Path(__file__).parents[1]
    / "evals"
    / "baselines"
    / "claim-verification-deepseek-v4-flash-v3.json"
)


def test_claim_verification_dataset_is_versioned_unique_and_balanced() -> None:
    dataset = load_claim_verification_dataset(DATASET)

    assert dataset.version == "2026-08-25.1"
    assert len(dataset.cases) == 12
    assert len({case.id for case in dataset.cases}) == 12
    assert len({case.category for case in dataset.cases}) >= 6
    assert {case.expectation.verdict.value for case in dataset.cases} == {
        "supports",
        "contradicts",
        "insufficient",
        "unverifiable",
    }


def test_legacy_baseline_captures_citation_presence_failure() -> None:
    report = evaluate_legacy_baseline(load_claim_verification_dataset(DATASET))

    assert report.system == "legacy-citation-presence"
    assert report.pass_rate == 0
    failures = {failure for result in report.results for failure in result.failures}
    assert failures == {
        "wrong_verdict",
        "missing_expected_quote",
        "missing_expected_limitation",
    }


def test_committed_claim_verification_baseline_matches_fixture() -> None:
    expected = evaluate_legacy_baseline(load_claim_verification_dataset(DATASET))
    committed = ClaimVerificationEvalReport.model_validate_json(
        BASELINE.read_text(encoding="utf-8")
    )

    assert committed == expected


def test_accepted_deepseek_v4_flash_candidate_passes_promotion_gate() -> None:
    artifact = ClaimVerificationCandidateArtifact.model_validate_json(
        ACCEPTED_CANDIDATE.read_text(encoding="utf-8")
    )

    assert artifact.model_alias == "deepseek-v4-flash"
    assert artifact.model_revision == "deepseek/deepseek-v4-flash-0731"
    assert artifact.verifier_version == "claim-verification-v3"
    assert artifact.suite.dataset_version == "2026-08-25.1"
    assert artifact.suite.system == "live:deepseek-v4-flash"
    assert artifact.promotion.passed
    assert artifact.promotion.trial_count == 3
    assert artifact.promotion.candidate_mean_pass_rate == pytest.approx(8 / 9)
    assert artifact.promotion.candidate_minimum_pass_rate == pytest.approx(5 / 6)


def reviewed_verification(case) -> ClaimEvidenceVerification:
    return ClaimEvidenceVerification(
        claim_id=case.claim.id,
        evidence_id=case.evidence.id,
        verdict=case.expectation.verdict,
        quote=case.evidence.excerpt,
        limitations=case.expectation.limitation_terms,
        confidence=Confidence.HIGH,
        claim_sha256=claim_content_sha256(case.claim),
        evidence_sha256=evidence_content_sha256(case.evidence),
        verifier_version="reviewed-fixture-v1",
    )


def test_score_accepts_bound_reviewed_verification() -> None:
    case = load_claim_verification_dataset(DATASET).cases[0]

    result = score_claim_verification(case, reviewed_verification(case))

    assert result.passed
    assert result.failures == []


@pytest.mark.asyncio
async def test_live_component_eval_scores_bound_verifier_outputs() -> None:
    dataset = load_claim_verification_dataset(DATASET)
    cases_by_pair = {
        (case.claim.id, case.evidence.id): case for case in dataset.cases
    }

    class ReviewedFixtureVerifier:
        async def verify_claims(self, inquiry, report: ResearchReport, *, model):
            return [
                reviewed_verification(
                    cases_by_pair[(claim.id, evidence_id)]
                )
                for claim in report.claims
                for evidence_id in claim.evidence_ids
            ]

    report = await evaluate_live_verifier(
        dataset,
        ReviewedFixtureVerifier(),
        model="fixture",
    )

    assert report.pass_rate == 1


@pytest.mark.asyncio
async def test_live_component_eval_bounds_parallel_provider_calls() -> None:
    dataset = load_claim_verification_dataset(DATASET)
    cases_by_pair = {
        (case.claim.id, case.evidence.id): case for case in dataset.cases
    }

    class TrackingVerifier:
        active = 0
        max_active = 0

        async def verify_claims(self, inquiry, report: ResearchReport, *, model):
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            await asyncio.sleep(0.005)
            self.active -= 1
            return [
                reviewed_verification(
                    cases_by_pair[(claim.id, evidence_id)]
                )
                for claim in report.claims
                for evidence_id in claim.evidence_ids
            ]

    verifier = TrackingVerifier()
    report = await evaluate_live_verifier(
        dataset,
        verifier,
        model="fixture",
        max_concurrency=2,
    )

    assert report.pass_rate == 1
    assert verifier.max_active == 2


def test_promotion_requires_repeatable_material_improvement() -> None:
    dataset = load_claim_verification_dataset(DATASET)
    baseline = evaluate_legacy_baseline(dataset)
    passing = ClaimVerificationEvalReport(
        dataset_version=dataset.version,
        system="candidate",
        results=[
            score_claim_verification(case, reviewed_verification(case))
            for case in dataset.cases
        ],
    )
    suite = ClaimVerificationEvalSuite(
        dataset_version=dataset.version,
        system="candidate",
        trials=[passing, passing, passing],
    )

    decision = decide_promotion(baseline, suite)

    assert decision.passed
    assert decision.candidate_mean_pass_rate == 1
    assert decision.candidate_minimum_pass_rate == 1
    assert decision.trial_count == 3


def test_promotion_rejects_a_lucky_single_trial() -> None:
    dataset = load_claim_verification_dataset(DATASET)
    baseline = evaluate_legacy_baseline(dataset)
    passing = ClaimVerificationEvalReport(
        dataset_version=dataset.version,
        system="candidate",
        results=[
            score_claim_verification(case, reviewed_verification(case))
            for case in dataset.cases
        ],
    )
    suite = ClaimVerificationEvalSuite(
        dataset_version=dataset.version,
        system="candidate",
        trials=[passing],
    )

    decision = decide_promotion(baseline, suite)

    assert not decision.passed
    assert "insufficient_trial_count" in decision.failure_codes


def test_promotion_rejects_a_regressing_trial() -> None:
    dataset = load_claim_verification_dataset(DATASET)
    baseline = evaluate_legacy_baseline(dataset)
    passing = ClaimVerificationEvalReport(
        dataset_version=dataset.version,
        system="candidate",
        results=[
            score_claim_verification(case, reviewed_verification(case))
            for case in dataset.cases
        ],
    )
    failing = evaluate_legacy_baseline(dataset).model_copy(update={"system": "candidate"})
    suite = ClaimVerificationEvalSuite(
        dataset_version=dataset.version,
        system="candidate",
        trials=[passing, passing, failing],
    )

    decision = decide_promotion(baseline, suite)

    assert not decision.passed
    assert "minimum_pass_rate_below_gate" in decision.failure_codes
