from __future__ import annotations

from collections import defaultdict
from typing import Any

from pdf_math_audit.geometry import (
    overlaps,
    rule_covers_horizontal_span,
    rule_fits_horizontal_span,
)
from pdf_math_audit.math_fonts import math_and_variable_fonts
from pdf_math_audit.pdf_indicators import is_math_indicator


_ATOM_CHARACTERS = frozenset("()[]{}_")
_PROSE_PUNCTUATION = frozenset(",.;")
_ANNOTATED_OPERATOR_CHARACTERS = frozenset("=≈≝")
_STACKED_OPERATOR_GLYPHS = frozenset(
    {
        "productdisplay",
        "producttext",
        "radicalBig",
        "summationdisplay",
        "summationtext",
    }
)


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
    if text and all(
        character.isdigit() or character in _ATOM_CHARACTERS for character in text
    ):
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
            if (
                tokens
                and tokens[-1]["span"] == glyph["rawdict"]["span"]
                and tokens[-1]["kind"] == kind
            ):
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
        previous_glyphs[-1]["rendered_size"] == current_glyphs[0]["rendered_size"]
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
            if _should_merge(page, glyphs, other_page, other)
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


def _should_merge(
    page: int,
    glyphs: list[dict[str, Any]],
    other_page: int,
    other: list[dict[str, Any]],
) -> bool:
    if page != other_page:
        return False
    sequences = {glyph["sequence_index"] for glyph in glyphs}
    other_sequences = {glyph["sequence_index"] for glyph in other}
    if sequences <= other_sequences or other_sequences <= sequences:
        return True
    if sequences & other_sequences:
        return True
    sequential = max(sequences) + 1 == min(other_sequences) or max(
        other_sequences
    ) + 1 == min(sequences)
    if sequential:
        glyph_baseline = max(glyphs, key=lambda glyph: glyph["rendered_size"])
        other_baseline = max(other, key=lambda glyph: glyph["rendered_size"])
        horizontal_gap = max(
            0.0,
            max(_bbox(glyphs)[0], _bbox(other)[0])
            - min(_bbox(glyphs)[2], _bbox(other)[2]),
        )
        if abs(
            glyph_baseline["rendered_origin_y"] - other_baseline["rendered_origin_y"]
        ) <= max(
            glyph_baseline["rendered_size"], other_baseline["rendered_size"]
        ) * 0.1 and horizontal_gap <= max(
            glyph_baseline["rendered_size"], other_baseline["rendered_size"]
        ):
            return True
    glyph_bbox = _bbox(glyphs)
    other_bbox = _bbox(other)
    glyph_sizes = [glyph["rendered_size"] for glyph in glyphs]
    other_sizes = [glyph["rendered_size"] for glyph in other]
    glyph_size = max(glyph_sizes)
    other_size = max(other_sizes)
    stacked = any(
        glyph["glyph_name"] in _STACKED_OPERATOR_GLYPHS for glyph in [*glyphs, *other]
    )
    if stacked and sequential:
        horizontal_gap = max(
            0.0,
            max(glyph_bbox[0], other_bbox[0]) - min(glyph_bbox[2], other_bbox[2]),
        )
        vertical_gap = max(
            0.0,
            max(glyph_bbox[1], other_bbox[1]) - min(glyph_bbox[3], other_bbox[3]),
        )
        scale = max(glyph_size, other_size)
        if horizontal_gap <= scale and vertical_gap <= scale * 1.5:
            return True
    if not overlaps(tuple(glyph_bbox), other_bbox):
        return False
    glyph_has_script = _has_vertical_hierarchy(glyphs)
    other_has_script = _has_vertical_hierarchy(other)
    size_attachment = (
        max(glyph_sizes) < 0.8 * max(other_sizes)
        or max(other_sizes) < 0.8 * max(glyph_sizes)
    ) and not (glyph_has_script and other_has_script)
    return size_attachment or stacked


def _has_vertical_hierarchy(glyphs: list[dict[str, Any]]) -> bool:
    if len(glyphs) < 2:
        return False
    baseline = max(glyphs, key=lambda glyph: glyph["rendered_size"])
    tolerance = baseline["rendered_size"] * 0.05
    return any(
        abs(glyph["rendered_origin_y"] - baseline["rendered_origin_y"])
        > tolerance
        for glyph in glyphs
        if glyph is not baseline
    )


def _operator_annotation_candidates(
    glyphs_by_page: dict[int, list[dict[str, Any]]],
) -> list[tuple[int, list[dict[str, Any]]]]:
    candidates = []
    for page, glyphs in glyphs_by_page.items():
        for operator in glyphs:
            if operator["unicode"] not in _ANNOTATED_OPERATOR_CHARACTERS:
                continue
            operator_bbox = operator["bbox"]
            operator_width = operator_bbox[2] - operator_bbox[0]
            annotations = [
                glyph
                for glyph in glyphs
                if glyph["rawdict"]["block"] == operator["rawdict"]["block"]
                and glyph["rawdict"]["line"] != operator["rawdict"]["line"]
                and glyph["rendered_size"] < operator["rendered_size"] * 0.8
                and glyph["rendered_origin_y"]
                < operator["rendered_origin_y"] - operator["rendered_size"] * 0.1
                and operator["rendered_origin_y"] - glyph["rendered_origin_y"]
                <= operator["rendered_size"]
                and operator_bbox[0] - operator_width * 0.25
                <= (glyph["bbox"][0] + glyph["bbox"][2]) / 2
                <= operator_bbox[2] + operator_width * 0.25
            ]
            if annotations:
                candidates.append(
                    (
                        page,
                        sorted(
                            [operator, *annotations],
                            key=lambda glyph: glyph["sequence_index"],
                        ),
                    )
                )
    return candidates


def _rule_sides(
    glyphs: list[dict[str, Any]], rule: dict[str, float | int]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    above = []
    below = []
    crossing = []
    y = float(rule["y"])
    tolerance = max(0.5, float(rule["width"]))
    for glyph in glyphs:
        bbox = glyph["bbox"]
        center_x = (bbox[0] + bbox[2]) / 2
        if (
            not float(rule["x0"]) - tolerance
            <= center_x
            <= float(rule["x1"]) + tolerance
        ):
            continue
        vertical_reach = glyph["rendered_size"] * 0.6
        if bbox[3] <= y + tolerance and y - bbox[3] <= vertical_reach:
            above.append(glyph)
        elif bbox[1] >= y - tolerance and bbox[1] - y <= vertical_reach:
            below.append(glyph)
        elif bbox[1] < y < bbox[3]:
            crossing.append(glyph)
    return above, below, crossing


def _rule_covers(rule: dict[str, float | int], glyphs: list[dict[str, Any]]) -> bool:
    return rule_covers_horizontal_span(rule, glyphs)


def _rule_matches_span(
    rule: dict[str, float | int], glyphs: list[dict[str, Any]]
) -> bool:
    return rule_fits_horizontal_span(rule, glyphs)


def _fraction_candidates(
    glyphs_by_page: dict[int, list[dict[str, Any]]],
    page_rules: dict[int, list[dict[str, float | int]]],
    roles: dict[int, tuple[set[str], set[str]]],
) -> list[tuple[int, list[dict[str, Any]]]]:
    candidates = []
    for page, rules in page_rules.items():
        math_fonts, bold_fonts = roles.get(page, (set(), set()))
        for rule in rules:
            above, below, crossing = _rule_sides(glyphs_by_page.get(page, []), rule)
            selected = [*above, *below]
            permitted_fonts = math_fonts | bold_fonts
            if (
                above
                and below
                and not crossing
                and _rule_covers(rule, above)
                and _rule_covers(rule, below)
                and _rule_matches_span(rule, selected)
                and all(
                    glyph["font_resource"] in permitted_fonts
                    or is_math_indicator(glyph["unicode"])
                    or all(
                        character.isdigit() or character in _ATOM_CHARACTERS
                        for character in glyph["unicode"]
                    )
                    for glyph in selected
                )
            ):
                candidates.append((page, selected))
    return candidates


def _structural_rules(
    glyphs: list[dict[str, Any]], rules: list[dict[str, float | int]]
) -> dict[str, dict[str, float | int]]:
    structure = {}
    radicals = [glyph for glyph in glyphs if glyph["glyph_name"] == "radicalBig"]
    if len(radicals) == 1:
        radical_bbox = radicals[0]["bbox"]
        matches = [
            rule
            for rule in rules
            if abs(float(rule["x0"]) - radical_bbox[2]) <= 1.0
            and radical_bbox[1] - 1.0 <= float(rule["y"]) <= radical_bbox[3] + 1.0
        ]
        if len(matches) == 1:
            structure["radical"] = matches[0]

    fractions = []
    for rule in rules:
        above, below, crossing = _rule_sides(glyphs, rule)
        if (
            above
            and below
            and not crossing
            and _rule_covers(rule, above)
            and _rule_covers(rule, below)
            and _rule_matches_span(rule, [*above, *below])
        ):
            fractions.append(rule)
    if len(fractions) == 1:
        structure["fraction"] = fractions[0]
    return structure


def _region(
    page: int,
    glyphs: list[dict[str, Any]],
    rules: list[dict[str, float | int]],
) -> dict[str, Any]:
    indices = [glyph["sequence_index"] for glyph in glyphs]
    structural_rules = _structural_rules(glyphs, rules)
    bbox = _bbox(glyphs)
    for rule in structural_rules.values():
        bbox = [
            min(bbox[0], float(rule["x0"])),
            min(bbox[1], float(rule["y"])),
            max(bbox[2], float(rule["x1"])),
            max(bbox[3], float(rule["y"])),
        ]
    return {
        "region_id": f"pdf-source:{page}:{indices[0]}",
        "kind": "pdf_source_math",
        "page": page,
        "bbox": bbox,
        "bbox_coord_origin": "TOPLEFT",
        "localization_method": "pdf_source_typography",
        "status": "traced",
        "glyph_count": len(glyphs),
        "glyph_sequence_indices": indices,
        "source_glyph_text": "".join(glyph["unicode"] for glyph in glyphs),
        "structural_rules": structural_rules,
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
    page_rules: dict[int, list[dict[str, float | int]]] | None = None,
) -> list[dict[str, Any]]:
    page_rules = page_rules or {}
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
    candidates.extend(_operator_annotation_candidates(glyphs_by_page))
    candidates.extend(_fraction_candidates(glyphs_by_page, page_rules, roles))
    merged = [
        (page, trimmed)
        for page, region_glyphs in _merge_overlapping(candidates)
        if (trimmed := _trim_unbalanced_delimiters(region_glyphs))
    ]
    return [
        _region(page, region_glyphs, page_rules.get(page, []))
        for page, region_glyphs in merged
    ]
