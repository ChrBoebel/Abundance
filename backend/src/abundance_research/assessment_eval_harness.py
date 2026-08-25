"""Deterministic evaluation harness for evidence-assessment capability."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from abundance_research.application.contracts import EvidenceAssessmentModel
from abundance_research.application.errors import ResearchFailure
from abundance_research.application.evidence_assessment import (
    bind_exact_quote,
    evidence_content_sha256,
)
from abundance_research.bootstrap import build_research_model
from abundance_research.domain import (
    AssessedEvidenceRelation,
    Confidence,
    EvidenceAssessment,
    EvidenceRecord,
    Inquiry,
    SourceKind,
)


class AssessmentExpectation(BaseModel):
    """Expected classification for one curated evidence record."""

    relation: AssessedEvidenceRelation
    relevance: Confidence
    source_kind: SourceKind
    is_primary: bool
    quote_contains: str | None = Field(default=None, min_length=3, max_length=500)
    limitation_terms: list[str] = Field(default_factory=list, max_length=5)


class AssessmentEvalCase(BaseModel):
    """One versioned inquiry/evidence pair with a reviewed expectation."""

    id: str = Field(pattern=r"^[a-z0-9-]+$")
    category: str = Field(min_length=2, max_length=80)
    inquiry: str = Field(min_length=3, max_length=2000)
    evidence: EvidenceRecord
    expectation: AssessmentExpectation


class AssessmentEvalDataset(BaseModel):
    """Bounded golden dataset for component-level assessment regression."""

    version: str
    cases: list[AssessmentEvalCase] = Field(min_length=8, max_length=50)

    @model_validator(mode="after")
    def validate_dataset(self) -> AssessmentEvalDataset:
        """Reject duplicated cases and datasets without meaningful breadth."""
        ids = [case.id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("assessment eval case identifiers must be unique")
        if len({case.category for case in self.cases}) < 4:
            raise ValueError("assessment eval dataset must cover at least four categories")
        return self


class AssessmentEvalResult(BaseModel):
    """Explain the failed dimensions for one assessment fixture."""

    case_id: str
    passed: bool
    failures: list[str] = Field(default_factory=list)


class AssessmentEvalReport(BaseModel):
    """Machine-readable component baseline or candidate report."""

    dataset_version: str
    system: str
    results: list[AssessmentEvalResult]

    @property
    def pass_rate(self) -> float:
        """Return the fraction of cases meeting every reviewed expectation."""
        return sum(result.passed for result in self.results) / len(self.results)


def load_assessment_dataset(path: Path) -> AssessmentEvalDataset:
    """Load and validate a source-controlled assessment fixture."""
    return AssessmentEvalDataset.model_validate_json(path.read_text(encoding="utf-8"))


def score_assessment(
    case: AssessmentEvalCase,
    assessment: EvidenceAssessment,
) -> AssessmentEvalResult:
    """Score classification, provenance, quote binding, and limitations."""
    expectation = case.expectation
    failures: list[str] = []
    if assessment.evidence_id != case.evidence.id:
        failures.append("wrong_evidence_id")
    if assessment.relation is not expectation.relation:
        failures.append("wrong_relation")
    if assessment.relevance is not expectation.relevance:
        failures.append("wrong_relevance")
    if assessment.source_kind is not expectation.source_kind:
        failures.append("wrong_source_kind")
    if assessment.is_primary != expectation.is_primary:
        failures.append("wrong_primary_status")
    if assessment.content_sha256 != evidence_content_sha256(case.evidence):
        failures.append("wrong_content_hash")
    if assessment.quote != bind_exact_quote(case.evidence, assessment.quote):
        failures.append("unbound_quote")
    if expectation.quote_contains is not None and (
        assessment.quote is None
        or expectation.quote_contains.casefold() not in assessment.quote.casefold()
    ):
        failures.append("missing_expected_quote")
    normalized_limitations = " ".join(assessment.limitations).casefold()
    if any(
        term.casefold() not in normalized_limitations
        for term in expectation.limitation_terms
    ):
        failures.append("missing_expected_limitation")
    return AssessmentEvalResult(
        case_id=case.id,
        passed=not failures,
        failures=failures,
    )


def legacy_assessment(case: AssessmentEvalCase) -> EvidenceAssessment:
    """Represent the pre-assessment behavior for a reproducible baseline."""
    record = case.evidence
    return EvidenceAssessment(
        evidence_id=record.id,
        relation=AssessedEvidenceRelation(record.relation.value),
        relevance=record.assessment.relevance,
        source_kind=record.assessment.source_kind,
        is_primary=record.assessment.is_primary,
        quote=None,
        limitations=record.assessment.limitations,
        confidence=Confidence.LOW,
        content_sha256=evidence_content_sha256(record),
        assessor_version="legacy-retrieval-metadata",
    )


def evaluate_legacy_baseline(dataset: AssessmentEvalDataset) -> AssessmentEvalReport:
    """Capture failure signatures of inherited retrieval classifications."""
    return AssessmentEvalReport(
        dataset_version=dataset.version,
        system="legacy-retrieval-metadata",
        results=[
            score_assessment(case, legacy_assessment(case))
            for case in dataset.cases
        ],
    )


async def evaluate_live_assessor(
    dataset: AssessmentEvalDataset,
    assessor: EvidenceAssessmentModel,
    *,
    model: str,
) -> AssessmentEvalReport:
    """Run one bounded model assessment for each golden component fixture."""
    results: list[AssessmentEvalResult] = []
    for case in dataset.cases:
        inquiry = Inquiry(question=case.inquiry)
        try:
            assessments = await assessor.assess_evidence(
                inquiry,
                [case.evidence],
                model=model,
            )
        except ResearchFailure as exc:
            results.append(
                AssessmentEvalResult(
                    case_id=case.id,
                    passed=False,
                    failures=[f"execution_{exc.code.value}"],
                )
            )
            continue
        assessment = next(
            (
                item
                for item in assessments
                if item.evidence_id == case.evidence.id
            ),
            None,
        )
        results.append(
            score_assessment(case, assessment)
            if assessment is not None
            else AssessmentEvalResult(
                case_id=case.id,
                passed=False,
                failures=["missing_assessment"],
            )
        )
    return AssessmentEvalReport(
        dataset_version=dataset.version,
        system=f"live:{model}",
        results=results,
    )


def build_parser() -> argparse.ArgumentParser:
    """Create the component-eval CLI contract."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evals/evidence-assessment-cases.json"),
    )
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--legacy-baseline", action="store_true")
    parser.add_argument("--model")
    parser.add_argument("--output", type=Path)
    return parser


async def _main() -> int:
    """Validate fixtures or write the deterministic legacy baseline."""
    args = build_parser().parse_args()
    dataset = load_assessment_dataset(args.dataset)
    if args.validate_only:
        return 0
    if args.legacy_baseline:
        report = evaluate_legacy_baseline(dataset)
        output = args.output or Path(
            "evals/baselines/evidence-assessment-legacy.json"
        )
    elif args.model:
        report = await evaluate_live_assessor(
            dataset,
            build_research_model(),
            model=args.model,
        )
        output = args.output or Path(
            "evals/results/evidence-assessment-candidate.json"
        )
    else:
        raise SystemExit(
            "--legacy-baseline or --model is required unless --validate-only is used"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
