from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz
from docling_core.types.doc import DoclingDocument

from pdf_math_audit.correction_application import (
    apply_target,
    target_ineligibility,
)
from pdf_math_audit.correction_targets import correction_targets
from pdf_math_audit.correction_evidence import checkpoint_record
from pdf_math_audit.correction_proposals import (
    ProposalClient,
    propose_proven_latex,
)
from pdf_math_audit.derived_document import derive_document_and_page_html
from pdf_math_audit.events import ProgressCallback, progress_event
from pdf_math_audit.gemma_proposal import ProposalError, propose_formula


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
    targets, region_count = correction_targets(regions, document)
    records: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    engine_counts: dict[str, int] = {}
    vision_calls = 0
    evidence = io.BytesIO()
    if on_progress:
        on_progress(progress_event("correction_proposal", 0, len(targets)))
    with (
        fitz.open(pdf_path) as pdf,
        zipfile.ZipFile(evidence, "w", zipfile.ZIP_DEFLATED) as archive,
    ):
        for completed, target in enumerate(targets, start=1):
            record: dict[str, Any] = {
                "target_id": target["target_id"],
                "kind": target["kind"],
                "region_ids": [
                    region["region_id"] for region in target["regions"]
                ],
                "region_id": target["regions"][0]["region_id"],
                "page": target["page"],
                "docling_ref": target.get("docling_ref"),
                "charspan": target.get("candidate_charspan"),
                "before": target.get("candidate_text"),
                "source_proofs": [
                    {
                        "region_id": region["region_id"],
                        "candidate_charspan": region.get("candidate_charspan"),
                        "candidate_text": region.get("candidate_text"),
                        "tokens": region.get("source_canonical_tokens"),
                        "signature": region.get("source_relation_signature"),
                        "relations": region.get("source_relations"),
                    }
                    for region in target["regions"]
                ],
            }
            if len(target["regions"]) == 1:
                source = target["regions"][0]
                record.update(
                    source_tokens=source.get("source_canonical_tokens"),
                    source_signature=source.get("source_relation_signature"),
                    source_relations=source.get("source_relations"),
                )
            reason = target_ineligibility(target, document)
            try:
                if reason:
                    raise ValueError(reason)
                proposals = []
                attempts = []
                for region in target["regions"]:
                    attempt = propose_proven_latex(
                        region,
                        pdf[region["page"] - 1],
                        archive,
                        config,
                        proposal_client,
                        checkpoint_evidence,
                        require_independent_vision=(
                            target["kind"] == "formula_replacement"
                        ),
                    )
                    attempts.append(attempt.details)
                    if "vision_proposal" in attempt.details:
                        vision_calls += 1
                    if attempt.rejection_reason is not None or attempt.latex is None:
                        record["proposals"] = attempts
                        if len(target["regions"]) == 1:
                            record.update(
                                proposal=attempt.details.get("vision_proposal"),
                                proposal_tokens=attempt.details.get(
                                    "vision_proposal_tokens"
                                ),
                                proposal_signature=attempt.details.get(
                                    "vision_proposal_signature"
                                ),
                            )
                        raise ValueError(attempt.rejection_reason or "proposal_missing")
                    proposals.append(attempt.latex)
                after, mathml = apply_target(target, proposals)
                for attempt in attempts:
                    engine = attempt["selected_engine"]
                    engine_counts[engine] = engine_counts.get(engine, 0) + 1
                record.update(
                    status="accepted",
                    proposals=attempts,
                    proposal=(proposals[0] if len(proposals) == 1 else None),
                    proposal_tokens=(
                        attempts[0].get("proposal_tokens")
                        if len(attempts) == 1
                        else None
                    ),
                    proposal_signature=(
                        attempts[0].get("proposal_signature")
                        if len(attempts) == 1
                        else None
                    ),
                    after=after,
                    mathml=mathml,
                )
                accepted.append(record)
            except ProposalError as error:
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
        "regions": region_count,
        "targets": len(targets),
        "accepted": len(accepted),
        "accepted_regions": sum(len(record["region_ids"]) for record in accepted),
        "rejected": sum(record["status"] == "rejected" for record in records),
        "failed": failed,
        "engine": {
            "model": config.model,
            "dpi": config.dpi,
            "padding_points": config.padding_points,
            "strategy": "deterministic_source_then_proven_vision",
            "selected": engine_counts,
            "vision_calls": vision_calls,
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
