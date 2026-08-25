"""Deterministic Markdown rendering for structured research reports."""

from __future__ import annotations

from collections.abc import Sequence

from abundance_research.domain import Claim, Confidence, EvidenceRecord, ResearchReport


def _inline(value: str) -> str:
    """Keep generated values on one Markdown line and escape structural markers."""
    return " ".join(value.split()).replace("[", "\\[").replace("]", "\\]")


def _citations(claim: Claim, source_numbers: dict[str, int]) -> str:
    numbers = sorted({source_numbers[item] for item in claim.evidence_ids if item in source_numbers})
    return "".join(f"[{number}]" for number in numbers)


def render_report(report: ResearchReport) -> str:
    """Render only admitted evidence URLs and validated evidence references."""
    source_numbers = {record.id: index for index, record in enumerate(report.evidence, start=1)}
    lines = [
        f"# {_inline(report.title)}",
        "",
        "## Executive assessment",
        "",
        report.summary.strip(),
        "",
        f"**Confidence:** {report.confidence.value}",
        "",
        "## Claim and evidence matrix",
        "",
    ]

    for claim in report.claims:
        citation_text = _citations(claim, source_numbers)
        lines.extend(
            [
                f"### {_inline(claim.statement)} {citation_text}".rstrip(),
                "",
                f"**Confidence:** {claim.confidence.value}",
            ]
        )
        if claim.counter_evidence:
            lines.extend(["", "**Counterevidence:**"])
            for counter in claim.counter_evidence:
                counter_numbers = sorted(
                    {source_numbers[item] for item in counter.evidence_ids if item in source_numbers}
                )
                counter_citations = "".join(f"[{number}]" for number in counter_numbers)
                lines.append(f"- {_inline(counter.summary)} {counter_citations}".rstrip())
        if claim.uncertainty_notes:
            lines.extend(["", "**Uncertainty:**"])
            lines.extend(f"- {_inline(note)}" for note in claim.uncertainty_notes)
        lines.append("")

    lines.extend(["## Limitations and open questions", ""])
    if report.open_questions:
        for item in report.open_questions:
            lines.append(f"- **{_inline(item.question)}** — {_inline(item.why_it_matters)}")
            if item.suggested_next_step:
                lines.append(f"  Next step: {_inline(item.suggested_next_step)}")
    else:
        lines.append("No material open question was recorded.")

    lines.extend(["", "## Sources", ""])
    for number, record in enumerate(report.evidence, start=1):
        lines.append(f"[{number}] {_inline(record.title)}: {record.url}")

    return "\n".join(lines).strip() + "\n"


def finalize_report(report: ResearchReport) -> ResearchReport:
    """Attach deterministic Markdown to an otherwise structured report."""
    return report.model_copy(update={"markdown": render_report(report)})


def enforce_report_contract(
    report: ResearchReport,
    *,
    inquiry_id: str,
    evidence: Sequence[EvidenceRecord],
) -> ResearchReport:
    """Bind any synthesis adapter output to the admitted application evidence."""
    allowed_ids = {record.id for record in evidence}
    claims: list[Claim] = []
    for claim in report.claims:
        evidence_ids = list(dict.fromkeys(ref for ref in claim.evidence_ids if ref in allowed_ids))
        counters = [
            counter.model_copy(
                update={
                    "evidence_ids": list(
                        dict.fromkeys(ref for ref in counter.evidence_ids if ref in allowed_ids)
                    )
                }
            )
            for counter in claim.counter_evidence
        ]
        uncertainty = list(claim.uncertainty_notes)
        confidence = claim.confidence
        if not evidence_ids:
            confidence = Confidence.LOW
            uncertainty.append("No admitted evidence directly supports this claim.")
        claims.append(
            claim.model_copy(
                update={
                    "evidence_ids": evidence_ids,
                    "counter_evidence": counters,
                    "confidence": confidence,
                    "uncertainty_notes": list(dict.fromkeys(uncertainty)),
                }
            )
        )
    return report.model_copy(
        update={
            "inquiry_id": inquiry_id,
            "claims": claims,
            "evidence": list(evidence),
            "markdown": "",
        }
    )
