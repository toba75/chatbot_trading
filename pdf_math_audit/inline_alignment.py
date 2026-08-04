from __future__ import annotations

from dataclasses import replace
from collections import defaultdict
from typing import Any

from docling_core.types.doc import DoclingDocument

from pdf_math_audit.docling_regions import Region
from pdf_math_audit.geometry import contains_center
from pdf_math_audit.text_alignment import (
    document_characters as aligned_document_characters,
    matching_positions,
    source_characters as aligned_source_characters,
)


def _reason(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _occurrences(text: str, fragment: str) -> list[int]:
    positions = []
    start = 0
    while (position := text.find(fragment, start)) >= 0:
        positions.append(position)
        start = position + 1
    return positions


def _unique_context_start(
    document_text: str,
    source_text: str,
    target_start: int,
    target_end: int,
) -> int | None:
    left, right = target_start, target_end
    positions = _occurrences(source_text, document_text[left:right])
    while len(positions) > 1 and (left > 0 or right < len(document_text)):
        options = []
        if left > 0:
            expanded = _occurrences(source_text, document_text[left - 1 : right])
            if expanded:
                options.append((len(expanded), 0, left - 1, right, expanded))
        if right < len(document_text):
            expanded = _occurrences(source_text, document_text[left : right + 1])
            if expanded:
                options.append((len(expanded), 1, left, right + 1, expanded))
        if not options:
            break
        _count, _side, left, right, positions = min(options)
    if len(positions) != 1:
        return None
    return positions[0] + target_start - left


def _target_span(
    region: Region, characters: list[tuple[str, int]]
) -> tuple[int, int] | None:
    positions = [
        position
        for position, (_character, original) in enumerate(characters)
        if region.charspan[0] <= original < region.charspan[1]
    ]
    if not positions:
        return None
    start, end = min(positions), max(positions) + 1
    marker = region.candidate_text.lstrip()
    if start > 0 and marker.startswith(("$_", "$^")):
        start -= 1
    return start, end


def _bbox(glyphs: list[dict[str, Any]]) -> tuple[float, float, float, float]:
    return (
        min(glyph["bbox"][0] for glyph in glyphs),
        min(glyph["bbox"][1] for glyph in glyphs),
        max(glyph["bbox"][2] for glyph in glyphs),
        max(glyph["bbox"][3] for glyph in glyphs),
    )


def _localize(
    document: DoclingDocument,
    region: Region,
    glyphs: list[dict[str, Any]],
) -> tuple[Region, list[dict[str, Any]]]:
    if (
        region.kind != "inline_math"
        or region.page is None
        or region.container_bbox is None
        or region.reason is None
        or region.reason["code"] != "inline_math_bbox_unavailable"
    ):
        return region, []
    items = [item for item in document.texts if item.self_ref == region.docling_ref]
    if len(items) != 1:
        return replace(
            region,
            reason=_reason(
                "inline_math_docling_reference_invalid",
                "La référence Docling du fragment inline n’est pas résolue",
            ),
        ), []
    item = items[0]
    document_characters = aligned_document_characters(item.text)
    target_span = _target_span(region, document_characters)
    if target_span is None:
        return replace(
            region,
            reason=_reason(
                "inline_math_no_alignable_character",
                "Le fragment inline ne contient aucun caractère alignable",
            ),
        ), []
    target_start, target_end = target_span
    container_glyphs = [
        glyph
        for glyph in glyphs
        if glyph["page"] == region.page
        and contains_center(region.container_bbox, tuple(glyph["bbox"]))
    ]
    source_characters = aligned_source_characters(container_glyphs)
    document_text = "".join(character for character, _index in document_characters)
    source_text = "".join(character for character, _glyph in source_characters)
    source_start = _unique_context_start(
        document_text, source_text, target_start, target_end
    )
    matching = matching_positions(document_text, source_text)
    mapped_positions = [matching.get(position) for position in range(target_start, target_end)]
    if (
        source_start is None
        or None in mapped_positions
        or mapped_positions != list(range(source_start, source_start + target_end - target_start))
    ):
        return replace(
            region,
            reason=_reason(
                "inline_math_source_alignment_ambiguous",
                "Le fragment inline n’a pas d’alignement textuel source univoque",
            ),
        ), []
    selected = []
    for _character, glyph in source_characters[source_start : source_start + target_end - target_start]:
        if not selected or glyph["sequence_index"] != selected[-1]["sequence_index"]:
            selected.append(glyph)
    anchored = document_characters[target_start][1] < region.charspan[0]
    return (
        replace(
            region,
            bbox=_bbox(selected),
            reason=None,
            localization_method=(
                "unique_text_context_with_preceding_script_anchor"
                if anchored
                else "unique_text_context"
            ),
        ),
        selected,
    )


def localize_inline_regions(
    document: DoclingDocument,
    regions: list[Region],
    glyphs: list[dict[str, Any]],
) -> tuple[list[Region], dict[str, list[dict[str, Any]]]]:
    localized = [_localize(document, region, glyphs) for region in regions]
    return (
        [region for region, _assigned in localized],
        {
            region.region_id: assigned
            for region, assigned in localized
            if assigned
        },
    )


def assignment_conflicts(
    assignments: dict[str, list[dict[str, Any]]],
) -> defaultdict[str, list[dict[str, Any]]]:
    owners: dict[
        tuple[int, int], list[tuple[str, dict[str, Any]]]
    ] = defaultdict(list)
    for region_id, glyphs in assignments.items():
        for glyph in glyphs:
            owners[(glyph["page"], glyph["sequence_index"])].append(
                (region_id, glyph)
            )
    conflicts: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidates in owners.values():
        if len(candidates) > 1:
            for region_id, glyph in candidates:
                conflicts[region_id].append(glyph)
    return conflicts
