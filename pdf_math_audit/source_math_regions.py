from __future__ import annotations

from collections import defaultdict
from typing import Any

from pdf_math_audit.geometry import overlaps
from pdf_math_audit.math_fonts import math_and_variable_fonts
from pdf_math_audit.pdf_indicators import is_math_indicator


_ATOM_CHARACTERS = frozenset("()[]{}_")
_PROSE_PUNCTUATION = frozenset(",.;")


def _span_groups(glyphs: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    for glyph in sorted(glyphs, key=lambda item: item["sequence_index"]):
        span = glyph["rawdict"]["span"]
        if not groups or groups[-1][-1]["rawdict"]["span"] != span:
            groups.append([glyph])
        else:
            groups[-1].append(glyph)
    return groups


def _primitive_kind(
    glyph: dict[str, Any], math_fonts: set[str], short_bold: bool
) -> str:
    text = glyph["unicode"]
    if glyph["font_resource"] in math_fonts or is_math_indicator(text) or short_bold:
        return "seed"
    if text and all(character.isdigit() or character in _ATOM_CHARACTERS for character in text):
        return "atom"
    if text in _PROSE_PUNCTUATION:
        return "boundary"
    return "prose"


def _tokens(
    glyphs: list[dict[str, Any]], math_fonts: set[str], bold_fonts: set[str]
) -> list[dict[str, Any]]:
    tokens: list[dict[str, Any]] = []
    for group in _span_groups(glyphs):
        text = "".join(glyph["unicode"] for glyph in group)
        short_bold = (
            group[0]["font_resource"] in bold_fonts
            and text.isalpha()
            and len(text) <= 2
        )
        for glyph in group:
            kind = _primitive_kind(glyph, math_fonts, short_bold)
            if tokens and tokens[-1]["span"] == glyph["rawdict"]["span"] and tokens[-1]["kind"] == kind:
                tokens[-1]["glyphs"].append(glyph)
            else:
                tokens.append(
                    {
                        "span": glyph["rawdict"]["span"],
                        "kind": kind,
                        "glyphs": [glyph],
                    }
                )
    return tokens


def _text(token: dict[str, Any]) -> str:
    return "".join(glyph["unicode"] for glyph in token["glyphs"])


def _grammar_connectors(tokens: list[dict[str, Any]]) -> set[int]:
    return {
        index
        for index in range(1, len(tokens) - 1)
        if tokens[index]["kind"] == "prose"
        and tokens[index - 1]["kind"] in {"seed", "atom"}
        and tokens[index + 1]["kind"] in {"seed", "atom"}
        and (
            _text(tokens[index]).casefold() == "if"
            or _text(tokens[index + 1]).startswith("(")
        )
    }


def _preceding_variable(
    tokens: list[dict[str, Any]], start: int
) -> list[dict[str, Any]]:
    if start == 0 or tokens[start]["kind"] != "seed":
        return []
    previous = tokens[start - 1]
    current = tokens[start]
    previous_glyphs = previous["glyphs"]
    current_glyphs = current["glyphs"]
    touching = previous_glyphs[-1]["bbox"][2] >= current_glyphs[0]["bbox"][0]
    same_baseline = (
        previous_glyphs[-1]["rendered_origin_y"]
        == current_glyphs[0]["rendered_origin_y"]
    )
    same_size = (
        previous_glyphs[-1]["rendered_size"]
        == current_glyphs[0]["rendered_size"]
    )
    if (
        previous["kind"] == "prose"
        and previous_glyphs[-1]["unicode"].isalpha()
        and is_math_indicator(_text(current))
        and touching
        and same_baseline
        and same_size
    ):
        return [previous_glyphs[-1]]
    return []


def _line_candidates(tokens: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    connectors = _grammar_connectors(tokens)
    marked = [
        token["kind"] in {"seed", "atom"} or index in connectors
        for index, token in enumerate(tokens)
    ]
    candidates = []
    start = 0
    while start < len(tokens):
        if not marked[start]:
            start += 1
            continue
        end = start
        while end + 1 < len(tokens) and marked[end + 1]:
            end += 1
        if any(token["kind"] == "seed" for token in tokens[start : end + 1]):
            anchor = _preceding_variable(tokens, start)
            candidates.append(
                anchor
                + [
                    glyph
                    for token in tokens[start : end + 1]
                    for glyph in token["glyphs"]
                ]
            )
        start = end + 1
    return candidates


def _bbox(glyphs: list[dict[str, Any]]) -> list[float]:
    return [
        min(glyph["bbox"][0] for glyph in glyphs),
        min(glyph["bbox"][1] for glyph in glyphs),
        max(glyph["bbox"][2] for glyph in glyphs),
        max(glyph["bbox"][3] for glyph in glyphs),
    ]


def _trim_unbalanced_delimiters(
    glyphs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    pairs = {"(": ")", "[": "]", "{": "}"}
    trimmed = list(glyphs)
    while trimmed:
        opening = trimmed[0]["unicode"]
        closing = pairs.get(opening)
        if closing is None:
            break
        text = "".join(glyph["unicode"] for glyph in trimmed)
        if text.count(opening) <= text.count(closing):
            break
        trimmed.pop(0)
    return trimmed


def _merge_overlapping(
    candidates: list[tuple[int, list[dict[str, Any]]]],
) -> list[tuple[int, list[dict[str, Any]]]]:
    merged: list[tuple[int, list[dict[str, Any]]]] = []
    for page, glyphs in candidates:
        touching = [
            index
            for index, (other_page, other) in enumerate(merged)
            if page == other_page
            and overlaps(tuple(_bbox(glyphs)), _bbox(other))
            and min(
                max(glyph["rendered_size"] for glyph in glyphs),
                max(glyph["rendered_size"] for glyph in other),
            )
            < 0.8
            * max(
                max(glyph["rendered_size"] for glyph in glyphs),
                max(glyph["rendered_size"] for glyph in other),
            )
        ]
        if not touching:
            merged.append((page, glyphs))
            continue
        combined = list(glyphs)
        for index in reversed(touching):
            _other_page, other = merged.pop(index)
            combined.extend(other)
        unique = {glyph["sequence_index"]: glyph for glyph in combined}
        merged.append((page, [unique[index] for index in sorted(unique)]))
    return sorted(merged, key=lambda item: (item[0], item[1][0]["sequence_index"]))


def _region(page: int, glyphs: list[dict[str, Any]]) -> dict[str, Any]:
    glyphs = _trim_unbalanced_delimiters(glyphs)
    indices = [glyph["sequence_index"] for glyph in glyphs]
    return {
        "region_id": f"pdf-source:{page}:{indices[0]}",
        "kind": "pdf_source_math",
        "page": page,
        "bbox": _bbox(glyphs),
        "bbox_coord_origin": "TOPLEFT",
        "localization_method": "pdf_source_typography",
        "status": "traced",
        "glyph_count": len(glyphs),
        "glyph_sequence_indices": indices,
        "source_glyph_text": "".join(glyph["unicode"] for glyph in glyphs),
        "semantic_status": "not_established",
        "candidate_status": "not_evaluated",
        "verdict": "non_verifiable",
        "semantic_reasons": [
            {
                "code": "docling_candidate_not_linked",
                "message": "La région source n’est pas encore reliée à un candidat Docling",
            }
        ],
        "semantic_evidence": [],
    }


def source_math_regions(
    glyphs: list[dict[str, Any]],
    page_fonts: dict[int, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    by_line: dict[tuple[int, int, int], list[dict[str, Any]]] = defaultdict(list)
    for glyph in glyphs:
        rawdict = glyph["rawdict"]
        by_line[(glyph["page"], rawdict["block"], rawdict["line"])].append(glyph)

    candidates = []
    glyphs_by_page: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for glyph in glyphs:
        glyphs_by_page[glyph["page"]].append(glyph)
    roles = {
        page: math_and_variable_fonts(page_fonts, page_glyphs, page)
        for page, page_glyphs in glyphs_by_page.items()
    }
    for (page, _block, _line), line_glyphs in sorted(by_line.items()):
        math_fonts, bold_fonts = roles[page]
        tokens = _tokens(line_glyphs, math_fonts, bold_fonts)
        candidates.extend((page, glyphs) for glyphs in _line_candidates(tokens))
    return [_region(page, glyphs) for page, glyphs in _merge_overlapping(candidates)]
