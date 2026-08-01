from __future__ import annotations

import unicodedata
from typing import Any

from pdf_math_audit.evaluation_metrics import evaluation_metrics
from pdf_math_audit.events import ProgressCallback, progress_event
from pdf_math_audit.mathml_candidate import candidate_tokens


SEMANTIC_PROFILE = "type1-cff-agl-rendered-sequence-v3"


def _reason(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _evidence(glyph: dict[str, Any]) -> dict[str, Any]:
    return {
        "page": glyph["page"],
        "sequence_index": glyph["sequence_index"],
        "font_resource": glyph["font_resource"],
        "code": glyph["code"],
        "code_hex": glyph["code_hex"],
        "cff_gid": glyph["cff_gid"],
        "rendered_gid": glyph["rendered_gid"],
        "glyph_name": glyph["glyph_name"],
        "agl_unicode": glyph["unicode"],
        "to_unicode": glyph["to_unicode"],
        "rendered_unicode": glyph["rendered_unicode"],
        "rendered_origin_y": glyph["rendered_origin_y"],
        "rendered_size": glyph["rendered_size"],
    }


def _source_semantics(
    region: dict[str, Any],
    glyphs: list[dict[str, Any]],
) -> tuple[str, list[dict[str, str]], list[dict[str, str]]]:
    if region["status"] == "ambiguous":
        return "ambiguous", [
            _reason(
                "structural_alignment_ambiguous",
                "L’association structurelle de la région est ambiguë",
            )
        ], []
    if region["status"] != "traced":
        return "not_established", [
            _reason(
                "structural_alignment_not_traced",
                "La région ne possède aucune association structurelle établie",
            )
        ], []

    order = [
        (
            glyph["rawdict"]["block"],
            glyph["rawdict"]["line"],
            glyph["rawdict"]["span"],
            glyph["rawdict"]["char"],
        )
        for glyph in glyphs
    ]
    order_ambiguous = len(set(order)) != len(order) or order != sorted(order)
    if order_ambiguous:
        return "ambiguous", [
            _reason(
                "glyph_order_ambiguous",
                "L’ordre source et l’ordre de lecture MuPDF divergent",
            )
        ], []
    gid_mismatches = [
        glyph["sequence_index"]
        for glyph in glyphs
        if glyph["cff_gid"] != glyph["rendered_gid"]
    ]
    if gid_mismatches:
        return "not_established", [
            _reason(
                "rendered_gid_mismatch",
                "Le GID CFF et le GID rendu divergent pour les glyphes "
                + ", ".join(map(str, gid_mismatches)),
            )
        ], []
    conflicts = _source_signal_conflicts(glyphs)
    if conflicts:
        return "conflicting", [
            _reason(
                "source_signal_conflict",
                "Les signaux Unicode source se contredisent",
            )
        ], []
    return "established", [], []


def _source_signal_conflicts(glyphs: list[dict[str, Any]]) -> list[int]:
    return [
        glyph["sequence_index"]
        for glyph in glyphs
        if len(
            {glyph["unicode"], glyph["rendered_unicode"]}
            | ({glyph["to_unicode"]} if glyph["to_unicode"] is not None else set())
        )
        > 1
    ]


def _is_subsequence(candidate: list[str], source: list[str]) -> bool:
    source_iterator = iter(source)
    return all(
        any(token == source_token for source_token in source_iterator)
        for token in candidate
    )


def _evaluate_region(
    region: dict[str, Any],
    glyph_index: dict[tuple[int, int], dict[str, Any]],
) -> dict[str, Any]:
    glyphs = [
        glyph_index[(region["page"], sequence)]
        for sequence in region["glyph_sequence_indices"]
    ]
    source_text = unicodedata.normalize(
        "NFC", "".join(glyph["unicode"] for glyph in glyphs)
    )
    source_tokens = [character for character in source_text if not character.isspace()]
    parsed_candidate, candidate_reason = candidate_tokens(
        region["candidate_text"], region["candidate_format"]
    )
    semantic_status, semantic_reasons, semantic_resolution_rules = _source_semantics(
        region, glyphs
    )
    if candidate_reason:
        semantic_reasons.append(candidate_reason)

    candidate_status = "not_evaluated"
    verdict = "non_verifiable"
    if semantic_status == "established" and parsed_candidate is not None:
        if parsed_candidate == source_tokens:
            candidate_status = "matching"
            verdict = "conformant_within_scope"
        elif _is_subsequence(parsed_candidate, source_tokens):
            candidate_status = "missing"
            verdict = "contradicted"
        else:
            candidate_status = "contradicting"
            verdict = "contradicted"

    return region | {
        "semantic_profile": SEMANTIC_PROFILE,
        "semantic_status": semantic_status,
        "candidate_status": candidate_status,
        "verdict": verdict,
        "source_tokens": source_tokens,
        "candidate_tokens": parsed_candidate,
        "semantic_evidence": [_evidence(glyph) for glyph in glyphs],
        "semantic_reasons": semantic_reasons,
        "semantic_resolution_rules": semantic_resolution_rules,
        "source_signal_conflicts": _source_signal_conflicts(glyphs),
        "source_signal_missing": [
            glyph["sequence_index"]
            for glyph in glyphs
            if glyph["to_unicode"] is None
        ],
    }


def evaluate_regions(
    regions: list[dict[str, Any]],
    glyphs: list[dict[str, Any]],
    on_progress: ProgressCallback | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    glyph_index = {(glyph["page"], glyph["sequence_index"]): glyph for glyph in glyphs}
    total = len(regions)
    if on_progress:
        on_progress(progress_event("candidate_evaluation", 0, total))
    evaluated = []
    for completed, region in enumerate(regions, start=1):
        evaluated.append(_evaluate_region(region, glyph_index))
        if on_progress:
            on_progress(progress_event("candidate_evaluation", completed, total))

    return evaluated, evaluation_metrics(evaluated, SEMANTIC_PROFILE)
