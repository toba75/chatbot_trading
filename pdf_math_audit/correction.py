from __future__ import annotations

import hashlib
import html
import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import fitz
from docling_core.types.doc import DoclingDocument
from latex2mathml.converter import convert

from pdf_math_audit.correction_targets import (
    ineligibility,
    overlapping_region_ids,
    render_crop,
)
from pdf_math_audit.correction_evidence import (
    checkpoint_record,
    evidence_key,
    record_failure,
    record_success,
)
from pdf_math_audit.derived_document import derive_document_and_page_html
from pdf_math_audit.events import ProgressCallback, progress_event
from pdf_math_audit.gemma_proposal import Proposal, ProposalError, propose_formula
from pdf_math_audit.mathml_candidate import candidate_analysis


@dataclass(frozen=True)
class CorrectionConfig:
    endpoint: str
    model: str
    dpi: int
    padding_points: float
    timeout_seconds: int
    max_response_bytes: int


@dataclass(frozen=True)
class CorrectionResult:
    summary: dict[str, Any]
    records: bytes
    evidence: bytes
    document: bytes | None
    html: bytes | None
    markdown: bytes | None


ProposalClient = Callable[..., Proposal]


def _rendered_mathml(latex: str, region_id: str, *, display: str) -> str:
    correction_id = html.escape(region_id, quote=True)
    return (
        convert(latex)
        .replace('display="inline"', f'display="{display}"', 1)
        .replace("<math ", f'<math data-correction-id="{correction_id}" ', 1)
    )


def _prompt(region: dict[str, Any]) -> str:
    tokens = json.dumps(region["source_canonical_tokens"], ensure_ascii=False)
    signature = json.dumps(region["source_relation_signature"], ensure_ascii=False)
    return (
        "Transcribe only the mathematical expression in this crop as valid LaTeX. "
        "Return raw LaTeX without dollar delimiters, prose, or code fence. Preserve "
        "all braces, indices, exponents, symbols, and their relations. The PDF "
        "drawing program independently proves this logical glyph sequence: "
        f"{tokens}. Its structural signature is {signature}, where sub and sup markers "
        "are mandatory relations. Use both to resolve visual ambiguity; do not add any token."
    )


def correct_document(
    pdf_path: Path,
    document: DoclingDocument,
    regions: list[dict[str, Any]],
    config: CorrectionConfig,
    *,
    on_progress: ProgressCallback | None = None,
    proposal_client: ProposalClient = propose_formula,
    checkpoint_records: Path | None = None,
    checkpoint_evidence: Path | None = None,
) -> CorrectionResult:
    targets = [region for region in regions if region.get("verdict") == "contradicted"]
    overlaps = overlapping_region_ids(targets)
    records: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    evidence = io.BytesIO()
    if on_progress:
        on_progress(progress_event("correction_proposal", 0, len(targets)))
    with (
        fitz.open(pdf_path) as pdf,
        zipfile.ZipFile(evidence, "w", zipfile.ZIP_DEFLATED) as archive,
    ):
        for completed, region in enumerate(targets, start=1):
            image: bytes | None = None
            key: str | None = None
            record: dict[str, Any] = {
                "region_id": region["region_id"],
                "page": region["page"],
                "docling_ref": region.get("docling_ref"),
                "charspan": region.get("candidate_charspan"),
                "before": region.get("candidate_text"),
                "source_tokens": region.get("source_canonical_tokens"),
                "source_signature": region.get("source_relation_signature"),
                "source_relations": region.get("source_relations"),
            }
            reason = (
                "candidate_loci_overlap"
                if region["region_id"] in overlaps
                else ineligibility(region, document)
            )
            try:
                if reason:
                    raise ValueError(reason)
                image, crop_bbox = render_crop(
                    pdf[region["page"] - 1],
                    region["bbox"],
                    padding_points=config.padding_points,
                    dpi=config.dpi,
                )
                prompt = _prompt(region)
                key = evidence_key(region["region_id"])
                record.update(
                    crop_bbox=crop_bbox,
                    crop_sha256=hashlib.sha256(image).hexdigest(),
                    prompt=prompt,
                    model=config.model,
                )
                proposal = proposal_client(
                    endpoint=config.endpoint,
                    model=config.model,
                    prompt=prompt,
                    image=image,
                    timeout_seconds=config.timeout_seconds,
                    max_response_bytes=config.max_response_bytes,
                )
                record_success(archive, checkpoint_evidence, key, image, proposal)
                tokens, signature, parse_reason = candidate_analysis(proposal.latex)
                record.update(
                    proposal=proposal.latex,
                    proposal_tokens=tokens,
                    proposal_signature=signature,
                )
                if (
                    parse_reason
                    or tokens != region["source_canonical_tokens"]
                    or signature != region["source_relation_signature"]
                ):
                    raise ValueError("proposal_not_proven_by_source")
                formula = region.get("candidate_format") == "latex"
                record.update(
                    status="accepted",
                    after=proposal.latex if formula else f"${proposal.latex}$",
                    mathml=_rendered_mathml(
                        proposal.latex,
                        region["region_id"],
                        display="block" if formula else "inline",
                    ),
                )
                accepted.append(record)
            except ProposalError as error:
                if image is not None and key is not None:
                    record_failure(archive, checkpoint_evidence, key, image, error)
                record.update(
                    status="failed",
                    reason="proposal_service_failed",
                    error=str(error),
                    response_bytes=len(error.response or b""),
                    response_sha256=(
                        hashlib.sha256(error.response).hexdigest()
                        if error.response is not None
                        else None
                    ),
                )
            except ValueError as error:
                record.update(status="rejected", reason=str(error))
            records.append(record)
            checkpoint_record(checkpoint_records, record)
            if on_progress:
                on_progress(
                    progress_event("correction_proposal", completed, len(targets))
                )

    failed = sum(record["status"] == "failed" for record in records)
    if on_progress:
        on_progress(progress_event("correction_export", 0, 1 if accepted else 0))
    if failed:
        status = "failed"
    elif accepted:
        status = "corrected"
    elif targets:
        status = "rejected"
    else:
        status = "not_required"
    derived, derived_html = (
        derive_document_and_page_html(document, accepted) if accepted else (None, None)
    )
    if on_progress and accepted:
        on_progress(progress_event("correction_export", 1, 1))
    summary = {
        "status": status,
        "targets": len(targets),
        "accepted": len(accepted),
        "rejected": sum(record["status"] == "rejected" for record in records),
        "failed": failed,
        "engine": {
            "model": config.model,
            "dpi": config.dpi,
            "padding_points": config.padding_points,
        },
    }
    records_bytes = (
        json.dumps(
            {"summary": summary, "records": records}, ensure_ascii=False, indent=2
        )
        + "\n"
    ).encode("utf-8")
    if derived is None:
        return CorrectionResult(
            summary, records_bytes, evidence.getvalue(), None, None, None
        )
    document_bytes = (derived.model_dump_json(indent=2) + "\n").encode("utf-8")
    return CorrectionResult(
        summary,
        records_bytes,
        evidence.getvalue(),
        document_bytes,
        derived_html,
        derived.export_to_markdown().encode("utf-8"),
    )
