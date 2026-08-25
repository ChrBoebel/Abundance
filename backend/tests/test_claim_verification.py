from abundance_research.application.claim_verification import (
    claim_content_sha256,
    summarize_claim_verifications,
    unavailable_verification_summary,
)
from abundance_research.application.evidence_assessment import evidence_content_sha256
from abundance_research.domain import (
    Claim,
    ClaimEvidenceVerification,
    ClaimVerificationVerdict,
    Confidence,
    EvidenceRecord,
    ResearchReport,
    VerificationStatus,
)


def report_fixture() -> ResearchReport:
    first = EvidenceRecord(
        id="ev-support",
        title="Measured result",
        url="https://example.org/result",
        excerpt="The controlled evaluation measured a 12 percent reduction.",
    )
    second = EvidenceRecord(
        id="ev-challenge",
        title="Replication",
        url="https://example.org/replication",
        excerpt="The independent replication found no statistically significant reduction.",
    )
    return ResearchReport(
        inquiry_id="inq-test",
        title="Verification fixture",
        summary="A bounded test report.",
        claims=[
            Claim(
                id="claim-supported",
                statement="The controlled evaluation measured a reduction.",
                evidence_ids=[first.id],
                confidence=Confidence.HIGH,
            ),
            Claim(
                id="claim-mixed",
                statement="Every evaluation measured a reduction.",
                evidence_ids=[first.id, second.id],
                confidence=Confidence.HIGH,
            ),
            Claim(
                id="claim-unlinked",
                statement="A future replication will confirm the result.",
                confidence=Confidence.HIGH,
            ),
        ],
        evidence=[first, second],
    )


def verification(
    report: ResearchReport,
    *,
    claim_id: str,
    evidence_id: str,
    verdict: ClaimVerificationVerdict,
    quote: str | None,
) -> ClaimEvidenceVerification:
    claim = next(item for item in report.claims if item.id == claim_id)
    evidence = next(item for item in report.evidence if item.id == evidence_id)
    return ClaimEvidenceVerification(
        claim_id=claim_id,
        evidence_id=evidence_id,
        verdict=verdict,
        quote=quote,
        confidence=Confidence.HIGH,
        claim_sha256=claim_content_sha256(claim),
        evidence_sha256=evidence_content_sha256(evidence),
        verifier_version="claim-verification-v1",
    )


def test_claim_hash_is_stable_across_whitespace_and_case() -> None:
    first = Claim(statement="A measured RESULT")
    second = Claim(statement="  a   measured result  ")

    assert claim_content_sha256(first) == claim_content_sha256(second)


def test_summary_uses_contradiction_precedence_and_counts_unlinked_claims() -> None:
    report = report_fixture()
    results = [
        verification(
            report,
            claim_id="claim-supported",
            evidence_id="ev-support",
            verdict=ClaimVerificationVerdict.SUPPORTS,
            quote="measured a 12 percent reduction",
        ),
        verification(
            report,
            claim_id="claim-mixed",
            evidence_id="ev-support",
            verdict=ClaimVerificationVerdict.SUPPORTS,
            quote="measured a 12 percent reduction",
        ),
        verification(
            report,
            claim_id="claim-mixed",
            evidence_id="ev-challenge",
            verdict=ClaimVerificationVerdict.CONTRADICTS,
            quote="found no statistically significant reduction",
        ),
    ]

    summary = summarize_claim_verifications(report, results)

    assert summary.status is VerificationStatus.COMPLETE
    assert summary.claim_count == 3
    assert summary.cited_claim_count == 2
    assert summary.verified_claim_count == 2
    assert summary.pair_count == 3
    assert summary.verified_pair_count == 3
    assert summary.coverage_ratio == 1
    assert summary.supported_claim_count == 1
    assert summary.contradicted_claim_count == 1
    assert summary.unverifiable_claim_count == 1
    assert summary.high_confidence_unsubstantiated_count == 2
    assert summary.exact_quote_ratio == 1


def test_summary_rejects_invented_pairs_hashes_quotes_and_duplicates() -> None:
    report = report_fixture()
    valid = verification(
        report,
        claim_id="claim-supported",
        evidence_id="ev-support",
        verdict=ClaimVerificationVerdict.SUPPORTS,
        quote="measured a 12 percent reduction",
    )
    invented_pair = valid.model_copy(update={"evidence_id": "ev-invented"})
    wrong_hash = valid.model_copy(update={"claim_sha256": "0" * 64})
    invented_quote = valid.model_copy(update={"quote": "A fabricated quotation."})
    duplicate = valid.model_copy(update={"verdict": ClaimVerificationVerdict.CONTRADICTS})

    summary = summarize_claim_verifications(
        report,
        [valid, invented_pair, wrong_hash, invented_quote, duplicate],
    )

    assert summary.status is VerificationStatus.PARTIAL
    assert summary.verified_pair_count == 1
    assert summary.supported_claim_count == 1
    assert summary.contradicted_claim_count == 0
    assert summary.high_confidence_unsubstantiated_count == 2


def test_unavailable_summary_never_claims_semantic_support() -> None:
    report = report_fixture()

    summary = unavailable_verification_summary(
        report,
        status=VerificationStatus.UNAVAILABLE,
        failure_code="provider_unavailable",
    )

    assert summary.status is VerificationStatus.UNAVAILABLE
    assert summary.supported_claim_count == 0
    assert summary.unverifiable_claim_count == 3
    assert summary.high_confidence_unsubstantiated_count == 3
    assert summary.failure_code == "provider_unavailable"
