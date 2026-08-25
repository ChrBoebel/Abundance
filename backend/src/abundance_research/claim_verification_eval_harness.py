"""Reproducible capability evaluation for claim verification."""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from abundance_research.adapters.models import (
    CLAIM_VERIFICATION_PROMPT_VERSION,
    ModelCatalog,
)
from abundance_research.application.claim_verification import claim_content_sha256
from abundance_research.application.contracts import ClaimVerificationModel
from abundance_research.application.errors import ResearchFailure
from abundance_research.application.evidence_assessment import (
    bind_exact_quote,
    evidence_content_sha256,
)
from abundance_research.bootstrap import build_research_model
from abundance_research.domain import (
    Claim,
    ClaimEvidenceVerification,
    ClaimVerificationVerdict,
    Confidence,
    EvidenceRecord,
    Inquiry,
    ResearchReport,
)


class ClaimVerificationExpectation(BaseModel):
    """Reviewed semantic expectation for one claim/evidence pair."""

    verdict: ClaimVerificationVerdict
    quote_contains: str = Field(min_length=3, max_length=500)
    limitation_terms: list[str] = Field(default_factory=list, max_length=5)


class ClaimVerificationEvalCase(BaseModel):
    """One versioned claim/evidence fixture."""

    id: str = Field(pattern=r"^[a-z0-9-]+$")
    category: str = Field(min_length=2, max_length=80)
    inquiry: str = Field(min_length=3, max_length=2000)
    claim: Claim
    evidence: EvidenceRecord
    expectation: ClaimVerificationExpectation

    @model_validator(mode="after")
    def require_bound_fixture(self) -> ClaimVerificationEvalCase:
        """Ensure the fixture itself uses the claim's admitted citation."""
        if self.evidence.id not in self.claim.evidence_ids:
            raise ValueError("claim verification fixture must cite its evidence")
        return self


class ClaimVerificationEvalDataset(BaseModel):
    """Cross-domain golden dataset for semantic citation checks."""

    version: str
    cases: list[ClaimVerificationEvalCase] = Field(min_length=10, max_length=60)

    @model_validator(mode="after")
    def validate_dataset(self) -> ClaimVerificationEvalDataset:
        """Reject duplicates, narrow domains, and missing verdict classes."""
        ids = [case.id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("claim verification case identifiers must be unique")
        if len({case.category for case in self.cases}) < 6:
            raise ValueError("claim verification dataset must cover at least six categories")
        verdicts = {case.expectation.verdict for case in self.cases}
        if verdicts != set(ClaimVerificationVerdict):
            raise ValueError("claim verification dataset must cover every verdict")
        return self


class ClaimVerificationEvalResult(BaseModel):
    """Explain failed dimensions for one claim/evidence fixture."""

    case_id: str
    passed: bool
    failures: list[str] = Field(default_factory=list)
    observed_verdict: ClaimVerificationVerdict | None = None
    has_bound_quote: bool = False
    missing_limitation_terms: list[str] = Field(default_factory=list)


class ClaimVerificationEvalReport(BaseModel):
    """One deterministic baseline or stochastic candidate trial."""

    dataset_version: str
    system: str
    results: list[ClaimVerificationEvalResult]

    @property
    def pass_rate(self) -> float:
        """Return the fraction of cases passing every reviewed dimension."""
        return sum(result.passed for result in self.results) / len(self.results)


class ClaimVerificationEvalSuite(BaseModel):
    """Repeated candidate trials used to guard against lucky single runs."""

    dataset_version: str
    system: str
    trials: list[ClaimVerificationEvalReport] = Field(min_length=1, max_length=10)

    @property
    def mean_pass_rate(self) -> float:
        """Return the arithmetic mean across repeated candidate trials."""
        return sum(trial.pass_rate for trial in self.trials) / len(self.trials)

    @property
    def minimum_pass_rate(self) -> float:
        """Return the weakest trial to expose stochastic regressions."""
        return min(trial.pass_rate for trial in self.trials)

    @property
    def failure_signatures(self) -> dict[str, int]:
        """Count stable failure codes across every trial."""
        return dict(
            Counter(
                failure
                for trial in self.trials
                for result in trial.results
                for failure in result.failures
            )
        )


class ClaimVerificationPromotionDecision(BaseModel):
    """Explain whether the candidate is measurably safer than the baseline."""

    passed: bool
    baseline_pass_rate: float
    candidate_mean_pass_rate: float
    candidate_minimum_pass_rate: float
    trial_count: int
    required_trial_count: int
    required_mean_pass_rate: float
    required_minimum_pass_rate: float
    failure_codes: list[str] = Field(default_factory=list)


class ClaimVerificationCandidateArtifact(BaseModel):
    """Machine-readable candidate trials and their promotion decision."""

    model_alias: str
    model_revision: str
    verifier_version: str
    suite: ClaimVerificationEvalSuite
    promotion: ClaimVerificationPromotionDecision


def load_claim_verification_dataset(path: Path) -> ClaimVerificationEvalDataset:
    """Load and validate the source-controlled golden dataset."""
    return ClaimVerificationEvalDataset.model_validate_json(path.read_text(encoding="utf-8"))


def score_claim_verification(
    case: ClaimVerificationEvalCase,
    verification: ClaimEvidenceVerification,
) -> ClaimVerificationEvalResult:
    """Score semantic verdict, provenance hashes, quote binding, and limitations."""
    failures: list[str] = []
    if verification.claim_id != case.claim.id:
        failures.append("wrong_claim_id")
    if verification.evidence_id != case.evidence.id:
        failures.append("wrong_evidence_id")
    if verification.verdict is not case.expectation.verdict:
        failures.append("wrong_verdict")
    if verification.claim_sha256 != claim_content_sha256(case.claim):
        failures.append("wrong_claim_hash")
    if verification.evidence_sha256 != evidence_content_sha256(case.evidence):
        failures.append("wrong_evidence_hash")
    if verification.quote != bind_exact_quote(case.evidence, verification.quote):
        failures.append("unbound_quote")
    if verification.quote is None or (
        case.expectation.quote_contains.casefold()
        not in verification.quote.casefold()
    ):
        failures.append("missing_expected_quote")
    limitations = " ".join(verification.limitations).casefold()
    missing_limitation_terms = [
        term
        for term in case.expectation.limitation_terms
        if term.casefold() not in limitations
    ]
    if missing_limitation_terms:
        failures.append("missing_expected_limitation")
    return ClaimVerificationEvalResult(
        case_id=case.id,
        passed=not failures,
        failures=failures,
        observed_verdict=verification.verdict,
        has_bound_quote=(
            verification.quote is not None
            and verification.quote == bind_exact_quote(case.evidence, verification.quote)
        ),
        missing_limitation_terms=missing_limitation_terms,
    )


def legacy_verification(case: ClaimVerificationEvalCase) -> ClaimEvidenceVerification:
    """Represent the previous citation-present-equals-supported heuristic."""
    return ClaimEvidenceVerification(
        claim_id=case.claim.id,
        evidence_id=case.evidence.id,
        verdict=ClaimVerificationVerdict.SUPPORTS,
        quote=None,
        confidence=Confidence.LOW,
        claim_sha256=claim_content_sha256(case.claim),
        evidence_sha256=evidence_content_sha256(case.evidence),
        verifier_version="legacy-citation-presence",
    )


def evaluate_legacy_baseline(
    dataset: ClaimVerificationEvalDataset,
) -> ClaimVerificationEvalReport:
    """Capture failures produced by citation-presence heuristics."""
    return ClaimVerificationEvalReport(
        dataset_version=dataset.version,
        system="legacy-citation-presence",
        results=[
            score_claim_verification(case, legacy_verification(case))
            for case in dataset.cases
        ],
    )


async def evaluate_live_verifier(
    dataset: ClaimVerificationEvalDataset,
    verifier: ClaimVerificationModel,
    *,
    model: str,
    max_concurrency: int = 3,
) -> ClaimVerificationEvalReport:
    """Evaluate one bounded model call for each reviewed fixture."""
    semaphore = asyncio.Semaphore(max_concurrency)

    async def evaluate_case(
        case: ClaimVerificationEvalCase,
    ) -> ClaimVerificationEvalResult:
        async with semaphore:
            inquiry = Inquiry(question=case.inquiry)
            report = ResearchReport(
                inquiry_id=inquiry.id,
                title="Claim verification fixture",
                summary="A single reviewed claim/evidence pair.",
                claims=[case.claim],
                evidence=[case.evidence],
            )
            try:
                verifications = await verifier.verify_claims(
                    inquiry,
                    report,
                    model=model,
                )
            except ResearchFailure as exc:
                return ClaimVerificationEvalResult(
                    case_id=case.id,
                    passed=False,
                    failures=[f"execution_{exc.code.value}"],
                )
            verification = next(
                (
                    item
                    for item in verifications
                    if item.claim_id == case.claim.id
                    and item.evidence_id == case.evidence.id
                ),
                None,
            )
            return (
                score_claim_verification(case, verification)
                if verification is not None
                else ClaimVerificationEvalResult(
                    case_id=case.id,
                    passed=False,
                    failures=["missing_verification"],
                )
            )

    results = await asyncio.gather(
        *(evaluate_case(case) for case in dataset.cases)
    )
    return ClaimVerificationEvalReport(
        dataset_version=dataset.version,
        system=f"live:{model}",
        results=results,
    )


def decide_promotion(
    baseline: ClaimVerificationEvalReport,
    candidate: ClaimVerificationEvalSuite,
    *,
    required_mean_pass_rate: float = 0.80,
    required_minimum_pass_rate: float = 0.70,
    required_trial_count: int = 3,
) -> ClaimVerificationPromotionDecision:
    """Require repeatable material improvement before rollout."""
    failures: list[str] = []
    if baseline.dataset_version != candidate.dataset_version:
        failures.append("dataset_version_mismatch")
    if candidate.mean_pass_rate <= baseline.pass_rate:
        failures.append("no_measured_improvement")
    if candidate.mean_pass_rate < required_mean_pass_rate:
        failures.append("mean_pass_rate_below_gate")
    if candidate.minimum_pass_rate < required_minimum_pass_rate:
        failures.append("minimum_pass_rate_below_gate")
    if len(candidate.trials) < required_trial_count:
        failures.append("insufficient_trial_count")
    return ClaimVerificationPromotionDecision(
        passed=not failures,
        baseline_pass_rate=baseline.pass_rate,
        candidate_mean_pass_rate=candidate.mean_pass_rate,
        candidate_minimum_pass_rate=candidate.minimum_pass_rate,
        trial_count=len(candidate.trials),
        required_trial_count=required_trial_count,
        required_mean_pass_rate=required_mean_pass_rate,
        required_minimum_pass_rate=required_minimum_pass_rate,
        failure_codes=failures,
    )


def build_parser() -> argparse.ArgumentParser:
    """Create the component-evaluation CLI contract."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evals/claim-verification-cases.json"),
    )
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--legacy-baseline", action="store_true")
    parser.add_argument("--model")
    parser.add_argument("--runs", type=int, default=3, choices=range(1, 11))
    parser.add_argument("--max-concurrency", type=int, default=3, choices=range(1, 9))
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path("evals/baselines/claim-verification-legacy.json"),
    )
    parser.add_argument("--output", type=Path)
    return parser


async def _main() -> int:
    args = build_parser().parse_args()
    dataset = load_claim_verification_dataset(args.dataset)
    if args.validate_only:
        return 0
    if args.legacy_baseline:
        output = args.output or Path("evals/baselines/claim-verification-legacy.json")
        payload: BaseModel = evaluate_legacy_baseline(dataset)
    elif args.model:
        verifier = build_research_model()
        trials = [
            await evaluate_live_verifier(
                dataset,
                verifier,
                model=args.model,
                max_concurrency=args.max_concurrency,
            )
            for _ in range(args.runs)
        ]
        suite = ClaimVerificationEvalSuite(
            dataset_version=dataset.version,
            system=f"live:{args.model}",
            trials=trials,
        )
        baseline = ClaimVerificationEvalReport.model_validate_json(
            args.baseline.read_text(encoding="utf-8")
        )
        payload = ClaimVerificationCandidateArtifact(
            model_alias=args.model,
            model_revision=ModelCatalog.resolve(args.model),
            verifier_version=CLAIM_VERIFICATION_PROMPT_VERSION,
            suite=suite,
            promotion=decide_promotion(baseline, suite),
        )
        output = args.output or Path("evals/results/claim-verification-candidate.json")
    else:
        raise SystemExit(
            "--legacy-baseline or --model is required unless --validate-only is used"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
    return (
        1
        if isinstance(payload, ClaimVerificationCandidateArtifact)
        and not payload.promotion.passed
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
