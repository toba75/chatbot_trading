from __future__ import annotations

import unicodedata
from typing import Any

from pdf_math_audit.evaluation_metrics import evaluation_metrics
from pdf_math_audit.events import ProgressCallback, progress_event
from pdf_math_audit.fonts import (
    TEX_EXTENSIBLE_DELIMITER_FONTS,
    TEX_EXTENSIBLE_DELIMITER_GLYPHS,
    TEX_GLYPH_RENDERED_FONTS,
    TEX_GLYPH_UNICODE,
)
from pdf_math_audit.mathml_candidate import candidate_analysis
from pdf_math_audit.source_relations import canonical_source_tokens


SEMANTIC_PROFILE = "embedded-font-rendered-structure-v6"


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
        "source_unicode": glyph["source_unicode"],
        "source_unicode_method": glyph["source_unicode_method"],
        "agl_unicode": glyph["agl_unicode"],
        "to_unicode": glyph["to_unicode"],
        "rendered_unicode": glyph["rendered_unicode"],
        "rendered_font": glyph.get("rendered_font"),
        "rendered_origin_x": glyph.get("rendered_origin_x"),
        "rendered_origin_y": glyph["rendered_origin_y"],
        "rendered_size": glyph["rendered_size"],
    }


def _source_semantics(
    region: dict[str, Any],
    glyphs: list[dict[str, Any]],
) -> tuple[str, list[dict[str, str]], list[dict[str, str]]]:
    if region["status"] == "ambiguous":
        return (
            "ambiguous",
            [
                _reason(
                    "structural_alignment_ambiguous",
                    "L’association structurelle de la région est ambiguë",
                )
            ],
            [],
        )
    if region["status"] != "traced":
        limitation = region.get("trace_limitation")
        return (
            "not_established",
            [
                _reason(
                    limitation or "structural_alignment_not_traced",
                    (
                        "La région intersecte une zone PDF opaque non qualifiée"
                        if limitation == "pdf_opaque_region_intersection"
                        else "La région ne possède aucune association structurelle établie"
                    ),
                )
            ],
            [],
        )

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
        return (
            "ambiguous",
            [
                _reason(
                    "glyph_order_ambiguous",
                    "L’ordre source et l’ordre de lecture MuPDF divergent",
                )
            ],
            [],
        )
    gid_mismatches = [
        glyph["sequence_index"]
        for glyph in glyphs
        if glyph["cff_gid"] != glyph["rendered_gid"]
    ]
    if gid_mismatches:
        return (
            "not_established",
            [
                _reason(
                    "rendered_gid_mismatch",
                    "Le GID CFF et le GID rendu divergent pour les glyphes "
                    + ", ".join(map(str, gid_mismatches)),
                )
            ],
            [],
        )
    if any(_is_extensible_delimiter_fragment(glyph) for glyph in glyphs):
        return (
            "not_established",
            [
                _reason(
                    "source_extensible_delimiter_fragment",
                    "La rÃ©gion ne contient quâ€™un fragment de dÃ©limiteur extensible",
                )
            ],
            [],
        )
    conflicts = _source_signal_conflicts(glyphs)
    if conflicts:
        return (
            "conflicting",
            [
                _reason(
                    "source_signal_conflict",
                    "Les signaux Unicode source se contredisent",
                )
            ],
            [],
        )
    resolution_rules = []
    if any(_tex_glyph_name_resolves(glyph) for glyph in glyphs):
        resolution_rules.append(
            _reason(
                "cff_tex_glyph_name_authoritative",
                "Le nom du glyphe CFF TeX résout les signaux Unicode divergents",
            )
        )
    return "established", [], resolution_rules


def _tex_glyph_name_resolves(glyph: dict[str, Any]) -> bool:
    expected = TEX_GLYPH_UNICODE.get(glyph["glyph_name"])
    rendered_fonts = TEX_GLYPH_RENDERED_FONTS.get(glyph["glyph_name"])
    rendered_font = str(glyph.get("rendered_font", ""))
    return (
        expected is not None
        and rendered_fonts is not None
        and glyph["unicode"] == expected
        and rendered_font in rendered_fonts
    )


def _is_extensible_delimiter_fragment(glyph: dict[str, Any]) -> bool:
    return (
        glyph["glyph_name"] in TEX_EXTENSIBLE_DELIMITER_GLYPHS
        and glyph.get("rendered_font") in TEX_EXTENSIBLE_DELIMITER_FONTS
    )


def _source_signal_conflicts(glyphs: list[dict[str, Any]]) -> list[int]:
    return [
        glyph["sequence_index"]
        for glyph in glyphs
        if not _tex_glyph_name_resolves(glyph)
        and not _is_extensible_delimiter_fragment(glyph)
        and len(
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


def _candidate_failure_stage(
    region: dict[str, Any], candidate_reason: dict[str, str] | None
) -> str | None:
    if candidate_reason is not None:
        if candidate_reason["code"] == "candidate_latex_invalid":
            return "latex_parsing"
        if candidate_reason["code"] in {
            "candidate_relation_invalid",
            "candidate_relation_unsupported",
        }:
            return "math_structure"
        return "candidate_evaluation"

    link_reason = region.get("candidate_link_reason")
    if not isinstance(link_reason, dict):
        return None
    if link_reason.get("code") == "docling_text_alignment_incomplete":
        return "text_alignment"
    if link_reason.get("code") in {
        "docling_picture_candidate_missing",
        "docling_text_container_missing",
        "docling_text_container_ambiguous",
    }:
        return "candidate_acquisition"
    return None


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
    (
        source_canonical_tokens,
        source_relation_signature,
        source_relations,
        source_relation_reason,
    ) = canonical_source_tokens(glyphs, region.get("structural_rules"))
    (
        parsed_candidate,
        candidate_relation_signature,
        candidate_reason,
    ) = candidate_analysis(region["candidate_text"], region["candidate_format"])
    semantic_status, semantic_reasons, semantic_resolution_rules = _source_semantics(
        region, glyphs
    )
    if semantic_status == "established" and source_relation_reason:
        semantic_status = "not_established"
        semantic_reasons.append(
            _reason(
                source_relation_reason,
                "La structure indice/exposant de la source n’est pas établie",
            )
        )
    if candidate_reason:
        semantic_reasons.append(candidate_reason)
    elif parsed_candidate == []:
        semantic_reasons.append(
            _reason(
                "candidate_content_missing",
                "Aucun contenu candidat n’est disponible pour la comparaison",
            )
        )

    candidate_status = "not_evaluated"
    verdict = "non_verifiable"
    source_comparison_tokens = source_canonical_tokens or source_tokens
    invalid_structured_candidate = (
        semantic_status == "established"
        and region.get("candidate_link_status") == "linked"
        and bool(region.get("candidate_text", "").strip())
        and source_relation_signature is not None
        and any(token.startswith("<") for token in source_relation_signature)
        and candidate_reason is not None
        and candidate_reason["code"] == "candidate_latex_invalid"
    )
    structure_comparable = (
        source_relation_signature is None or candidate_relation_signature is not None
    )
    if invalid_structured_candidate:
        candidate_status = "contradicting"
        verdict = "contradicted"
    elif semantic_status == "established" and parsed_candidate and structure_comparable:
        tokens_match = parsed_candidate == source_comparison_tokens
        relations_match = (
            source_relation_signature is None
            or candidate_relation_signature == source_relation_signature
        )
        if tokens_match:
            candidate_status = "matching" if relations_match else "contradicting"
            verdict = "conformant_within_scope" if relations_match else "contradicted"
        elif _is_subsequence(parsed_candidate, source_comparison_tokens):
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
        "source_canonical_tokens": source_canonical_tokens,
        "source_relation_signature": source_relation_signature,
        "source_relations": source_relations,
        "source_relation_reason": source_relation_reason,
        "candidate_tokens": parsed_candidate,
        "candidate_relation_signature": candidate_relation_signature,
        "candidate_failure_stage": _candidate_failure_stage(
            region, candidate_reason
        ),
        "semantic_evidence": [_evidence(glyph) for glyph in glyphs],
        "semantic_reasons": semantic_reasons,
        "semantic_resolution_rules": semantic_resolution_rules,
        "source_signal_conflicts": _source_signal_conflicts(glyphs),
        "source_signal_missing": [
            glyph["sequence_index"] for glyph in glyphs if glyph["to_unicode"] is None
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
