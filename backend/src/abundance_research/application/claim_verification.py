"""Deterministic boundaries for semantic claim verification."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence

from abundance_research.application.evidence_assessment import (
    bind_exact_quote,
    evidence_content_sha256,
)
from abundance_research.domain import (
    Claim,
    ClaimEvidenceVerification,
    ClaimVerificationSummary,
    ClaimVerificationVerdict,
    Confidence,
    ResearchReport,
    VerificationStatus,
)


def claim_content_sha256(claim: Claim) -> str:
    """Fingerprint normalized claim text without exposing it to observability."""
    normalized = re.sub(r"\s+", " ", claim.statement).strip().casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def unavailable_verification_summary(
    report: ResearchReport,
    *,
    status: VerificationStatus,
    failure_code: str | None = None,
) -> ClaimVerificationSummary:
    """Create a validated aggregate when shadow verification cannot execute."""
    evidence_ids = {record.id for record in report.evidence}
    cited_claims = [
        claim
        for claim in report.claims
        if any(evidence_id in evidence_ids for evidence_id in claim.evidence_ids)
    ]
    pair_count = sum(
        len({evidence_id for evidence_id in claim.evidence_ids if evidence_id in evidence_ids})
        for claim in report.claims
    )
    return ClaimVerificationSummary(
        status=status,
        claim_count=len(report.claims),
        cited_claim_count=len(cited_claims),
        pair_count=pair_count,
        unverifiable_claim_count=len(report.claims),
        high_confidence_unsubstantiated_count=sum(
            claim.confidence is Confidence.HIGH for claim in report.claims
        ),
        failure_code=failure_code,
    )


def summarize_claim_verifications(
    report: ResearchReport,
    verifications: Sequence[ClaimEvidenceVerification],
) -> ClaimVerificationSummary:
    """Aggregate only unique, valid claim/citation pairs into privacy-safe metrics."""
    claims = {claim.id: claim for claim in report.claims}
    evidence = {record.id: record for record in report.evidence}
    expected_pairs = {
        (claim.id, evidence_id)
        for claim in report.claims
        for evidence_id in claim.evidence_ids
        if evidence_id in evidence
    }
    bound: dict[tuple[str, str], ClaimEvidenceVerification] = {}
    for verification in verifications:
        pair = (verification.claim_id, verification.evidence_id)
        if pair not in expected_pairs or pair in bound:
            continue
        claim = claims[verification.claim_id]
        record = evidence[verification.evidence_id]
        if verification.claim_sha256 != claim_content_sha256(claim):
            continue
        if verification.evidence_sha256 != evidence_content_sha256(record):
            continue
        if verification.quote != bind_exact_quote(record, verification.quote):
            continue
        bound[pair] = verification

    claim_verdicts: dict[str, ClaimVerificationVerdict] = {}
    for claim in report.claims:
        verdicts = [
            verification.verdict
            for pair, verification in bound.items()
            if pair[0] == claim.id
        ]
        if ClaimVerificationVerdict.CONTRADICTS in verdicts:
            verdict = ClaimVerificationVerdict.CONTRADICTS
        elif ClaimVerificationVerdict.SUPPORTS in verdicts:
            verdict = ClaimVerificationVerdict.SUPPORTS
        elif ClaimVerificationVerdict.INSUFFICIENT in verdicts:
            verdict = ClaimVerificationVerdict.INSUFFICIENT
        else:
            verdict = ClaimVerificationVerdict.UNVERIFIABLE
        claim_verdicts[claim.id] = verdict

    cited_claim_ids = {claim_id for claim_id, _ in expected_pairs}
    verified_claim_ids = {claim_id for claim_id, _ in bound}
    verified_pair_count = len(bound)
    status = (
        VerificationStatus.COMPLETE
        if verified_pair_count == len(expected_pairs)
        else VerificationStatus.PARTIAL
    )
    return ClaimVerificationSummary(
        status=status,
        claim_count=len(report.claims),
        cited_claim_count=len(cited_claim_ids),
        verified_claim_count=len(verified_claim_ids),
        pair_count=len(expected_pairs),
        verified_pair_count=verified_pair_count,
        coverage_ratio=(
            len(verified_claim_ids) / len(cited_claim_ids) if cited_claim_ids else 0.0
        ),
        supported_claim_count=sum(
            verdict is ClaimVerificationVerdict.SUPPORTS
            for verdict in claim_verdicts.values()
        ),
        contradicted_claim_count=sum(
            verdict is ClaimVerificationVerdict.CONTRADICTS
            for verdict in claim_verdicts.values()
        ),
        insufficient_claim_count=sum(
            verdict is ClaimVerificationVerdict.INSUFFICIENT
            for verdict in claim_verdicts.values()
        ),
        unverifiable_claim_count=sum(
            verdict is ClaimVerificationVerdict.UNVERIFIABLE
            for verdict in claim_verdicts.values()
        ),
        high_confidence_unsubstantiated_count=sum(
            claim.confidence is Confidence.HIGH
            and claim_verdicts[claim.id] is not ClaimVerificationVerdict.SUPPORTS
            for claim in report.claims
        ),
        exact_quote_ratio=(
            sum(verification.quote is not None for verification in bound.values())
            / verified_pair_count
            if verified_pair_count
            else 0.0
        ),
    )
