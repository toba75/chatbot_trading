from __future__ import annotations

import html
import re
from typing import Any

from docling_core.types.doc import DoclingDocument
from latex2mathml.converter import convert

from pdf_math_audit.correction_targets import (
    ineligibility,
)
from pdf_math_audit.mathml_candidate import candidate_analysis
from pdf_math_audit.relation_signature import normalize_relation_signature


_SPACED_WORD = re.compile(r"(?<![A-Za-z])(?:[A-Za-z]\s+){3,}[A-Za-z](?![A-Za-z])")
_RAW_COMMAND = re.compile(r"\\[A-Za-z]+")


def _contains_prose(text: str) -> bool:
    return bool(re.search(r"[A-Za-z]{2,}", text))


def _normalize_renderable_latex(latex: str) -> str:
    return re.sub(r"\\arg\b", r"\\operatorname{arg}", latex)


def _latex_safety_reason(latex: str) -> str | None:
    without_definition = re.sub(r"\bd\s+e\s+f\b", "", latex)
    if _SPACED_WORD.search(without_definition):
        return "mathematical_text_grouping_unproven"
    return None


def target_ineligibility(
    target: dict[str, Any], document: DoclingDocument
) -> str | None:
    if target["kind"] == "formula_insertion":
        return "formula_insertion_rendering_unproven"
    if (
        target["kind"] == "replacement"
        and target.get("candidate_format") != "latex"
        and _contains_prose(target.get("candidate_text", ""))
    ):
        return "candidate_contains_prose"
    for region in target["regions"]:
        reason = ineligibility(
            region,
            document,
            allow_partial_formula=target["kind"] == "formula_replacement",
        )
        if reason is not None:
            return reason
    if target["kind"] not in {"merged_replacement", "formula_replacement"}:
        return None

    raw_sequences = [
        region.get("glyph_sequence_indices") for region in target["regions"]
    ]
    if not all(isinstance(sequence, list) and sequence for sequence in raw_sequences):
        return "source_loci_missing"
    sequences = [set(sequence) for sequence in raw_sequences]
    if any(
        left & right
        for index, left in enumerate(sequences)
        for right in sequences[index + 1 :]
    ):
        return "source_loci_overlap"
    if target["kind"] == "merged_replacement":
        return "merged_replacement_context_unproven"
    return None


def _replacement(target: dict[str, Any], proposals: list[str]) -> tuple[str, str]:
    kind = target["kind"]
    if kind == "formula_replacement":
        corrected = target["candidate_text"]
        patches = sorted(
            zip(target["regions"], proposals, strict=True),
            key=lambda item: item[0]["candidate_charspan"][0],
            reverse=True,
        )
        ascending = list(reversed(patches))
        if any(
            left[0]["candidate_charspan"][1]
            > right[0]["candidate_charspan"][0]
            for left, right in zip(ascending, ascending[1:])
        ):
            raise ValueError("full_formula_reconstruction_unproven")
        if any(
            corrected[region["candidate_charspan"][0] : region["candidate_charspan"][1]]
            != region["candidate_text"]
            for region, _latex in patches
        ):
            raise ValueError("full_formula_reconstruction_unproven")
        for region, latex in patches:
            start, end = region["candidate_charspan"]
            corrected = corrected[:start] + latex + corrected[end:]
        tokens, signature, reason = candidate_analysis(corrected)
        expected_tokens = [
            token
            for region, _latex in ascending
            for token in region["source_canonical_tokens"]
        ]
        expected_signature = normalize_relation_signature(
            [
                token
                for region, _latex in ascending
                for token in region["source_relation_signature"]
            ]
        )
        if reason or tokens != expected_tokens or signature != expected_signature:
            raise ValueError("full_formula_reconstruction_unproven")
        return corrected, "block"
    if kind == "merged_replacement":
        latex = " ".join(proposals)
        tokens, signature, reason = candidate_analysis(latex)
        expected_tokens = [
            token
            for region in target["regions"]
            for token in region["source_canonical_tokens"]
        ]
        expected_signature = normalize_relation_signature(
            [
                token
                for region in target["regions"]
                for token in region["source_relation_signature"]
            ]
        )
        if reason or tokens != expected_tokens or signature != expected_signature:
            raise ValueError("merged_proposal_not_proven_by_source")
        return f"${latex}$", "inline"
    latex = proposals[0]
    if kind == "formula_insertion" or target.get("candidate_format") == "latex":
        return latex, "block"
    return f"${latex}$", "inline"


def apply_target(
    target: dict[str, Any], proposals: list[str]
) -> tuple[str, str]:
    after, display = _replacement(target, proposals)
    latex = after[1:-1] if display == "inline" else after
    latex = _normalize_renderable_latex(latex)
    if reason := _latex_safety_reason(latex):
        raise ValueError(reason)
    after = f"${latex}$" if display == "inline" else latex
    correction_id = html.escape(target["target_id"], quote=True)
    try:
        converted = convert(latex)
    except Exception as error:
        if error.__class__.__module__.startswith("latex2mathml"):
            raise ValueError("corrected_latex_not_renderable") from error
        raise
    if _RAW_COMMAND.search(converted):
        raise ValueError("corrected_latex_command_unrendered")
    mathml = converted.replace(
        'display="inline"', f'display="{display}"', 1
    ).replace("<math ", f'<math data-correction-id="{correction_id}" ', 1)
    return after, mathml
