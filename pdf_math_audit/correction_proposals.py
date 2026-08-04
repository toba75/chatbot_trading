from __future__ import annotations

import hashlib
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

import fitz

from pdf_math_audit.correction_evidence import (
    evidence_key,
    record_failure,
    record_success,
)
from pdf_math_audit.correction_targets import render_crop
from pdf_math_audit.gemma_proposal import Proposal, ProposalError
from pdf_math_audit.mathml_candidate import candidate_analysis
from pdf_math_audit.source_latex import proven_source_latex


class CorrectionSettings(Protocol):
    endpoint: str
    model: str
    dpi: int
    padding_points: float
    timeout_seconds: int
    max_response_bytes: int


ProposalClient = Callable[..., Proposal]
_SPACED_WORD = re.compile(r"(?<![A-Za-z])(?:[A-Za-z]\s+){3,}[A-Za-z](?![A-Za-z])")


@dataclass(frozen=True)
class ProposalAttempt:
    latex: str | None
    details: dict[str, Any]
    rejection_reason: str | None


def _prompt(region: dict[str, Any], *, independent_vision: bool) -> str:
    instruction = (
        "Transcribe only the mathematical expression in this crop as valid LaTeX. "
        "Return raw LaTeX without dollar delimiters, prose, or code fence. Preserve "
        "all braces, indices, exponents, symbols, and their relations."
    )
    if independent_vision:
        return instruction
    return (
        f"{instruction} The PDF drawing program independently proves this logical "
        f"glyph sequence: {region['source_canonical_tokens']}. Its structural "
        f"signature is {region['source_relation_signature']}, where sub and sup "
        "markers are mandatory relations. Use both to resolve visual ambiguity; "
        "do not add any token."
    )


def _matches_source(
    region: dict[str, Any], latex: str
) -> tuple[list[str] | None, list[str] | None, bool]:
    tokens, signature, reason = candidate_analysis(latex)
    return (
        tokens,
        signature,
        reason is None
        and tokens == region["source_canonical_tokens"]
        and signature == region["source_relation_signature"],
    )


def _deterministic_text_grouping_unproven(latex: str) -> bool:
    without_definition = re.sub(r"\bd\s+e\s+f\b", "", latex)
    return bool(_SPACED_WORD.search(without_definition))


def propose_proven_latex(
    region: dict[str, Any],
    page: fitz.Page,
    archive: zipfile.ZipFile,
    config: CorrectionSettings,
    proposal_client: ProposalClient,
    checkpoint_evidence: Path | None,
    *,
    require_independent_vision: bool,
) -> ProposalAttempt:
    deterministic, deterministic_reason = proven_source_latex(region)
    deterministic_for_selection = deterministic
    if (
        deterministic_for_selection is not None
        and _deterministic_text_grouping_unproven(deterministic_for_selection)
    ):
        deterministic_reason = "deterministic_text_grouping_unproven"
        deterministic_for_selection = None
    details: dict[str, Any] = {
        "deterministic_proposal": deterministic,
        "deterministic_rejection_reason": deterministic_reason,
    }
    if deterministic_for_selection is not None and not require_independent_vision:
        tokens, signature, matches = _matches_source(region, deterministic_for_selection)
        if not matches:  # proven_source_latex garantit déjà cette postcondition.
            raise RuntimeError("deterministic_source_proof_lost")
        details.update(
            selected_engine="deterministic_source",
            proposal_tokens=tokens,
            proposal_signature=signature,
        )
        return ProposalAttempt(deterministic_for_selection, details, None)

    image, crop_bbox = render_crop(
        page,
        region["bbox"],
        padding_points=(0.0 if require_independent_vision else config.padding_points),
        dpi=config.dpi,
    )
    prompt = _prompt(region, independent_vision=require_independent_vision)
    key = evidence_key(region["region_id"])
    details.update(
        crop_bbox=crop_bbox,
        crop_sha256=hashlib.sha256(image).hexdigest(),
        prompt=prompt,
        model=config.model,
    )
    try:
        proposal = proposal_client(
            endpoint=config.endpoint,
            model=config.model,
            prompt=prompt,
            image=image,
            timeout_seconds=config.timeout_seconds,
            max_response_bytes=config.max_response_bytes,
        )
    except ProposalError as error:
        record_failure(archive, checkpoint_evidence, key, image, error)
        raise
    record_success(archive, checkpoint_evidence, key, image, proposal)
    tokens, signature, matches = _matches_source(region, proposal.latex)
    details.update(
        vision_proposal=proposal.latex,
        vision_proposal_tokens=tokens,
        vision_proposal_signature=signature,
        vision_confirmation=("exact" if matches else None),
    )
    if not matches:
        reason = (
            "vision_confirmation_not_proven_by_source"
            if require_independent_vision
            else "proposal_not_proven_by_source"
        )
        return ProposalAttempt(None, details, reason)

    details.update(
        selected_engine="vision_proven_by_source",
        proposal_tokens=tokens,
        proposal_signature=signature,
    )
    return ProposalAttempt(proposal.latex, details, None)
