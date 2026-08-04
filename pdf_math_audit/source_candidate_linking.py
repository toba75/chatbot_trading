from __future__ import annotations

from typing import Any

from docling_core.types.doc import DocItemLabel, DoclingDocument

from pdf_math_audit.geometry import contains_center
from pdf_math_audit.text_alignment import (
    document_characters,
    matching_positions,
    source_characters,
)


def _reason(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _bbox(document: DoclingDocument, provenance: Any) -> tuple[float, ...]:
    page = document.pages[provenance.page_no]
    return tuple(
        float(value)
        for value in provenance.bbox.to_top_left_origin(page.size.height).as_tuple()
    )


def _source_bbox(
    document: DoclingDocument,
    provenance: Any,
    source_page_box: list[float],
) -> tuple[float, ...]:
    page = document.pages[provenance.page_no]
    left, top, right, bottom = _bbox(document, provenance)
    source_left, source_top, source_right, source_bottom = source_page_box
    scale_x = (source_right - source_left) / page.size.width
    scale_y = (source_bottom - source_top) / page.size.height
    return (
        source_left + left * scale_x,
        source_top + top * scale_y,
        source_left + right * scale_x,
        source_top + bottom * scale_y,
    )


def _containers(
    document: DoclingDocument,
    items: list[Any],
    region: dict[str, Any],
    source_page_box: list[float],
) -> list[tuple[Any, tuple[float, ...]]]:
    center = (
        (region["bbox"][0] + region["bbox"][2]) / 2,
        (region["bbox"][1] + region["bbox"][3]) / 2,
    )
    return [
        (item, _source_bbox(document, provenance, source_page_box))
        for item in items
        for provenance in item.prov
        if provenance.page_no == region["page"]
        and (
            (box := _source_bbox(document, provenance, source_page_box))[0]
            <= center[0]
            <= box[2]
            and box[1]
            <= center[1]
            <= box[3]
        )
    ]


def _expanded_latex_command(text: str, start: int, end: int) -> tuple[int, int]:
    for position in {start, end - 1}:
        if 0 <= position < len(text) and text[position] == "\\":
            command_end = position + 1
            while command_end < len(text) and text[command_end].isalpha():
                command_end += 1
            end = max(end, command_end)
    balance = text[start:end].count("{") - text[start:end].count("}")
    while balance > 0 and end < len(text):
        if text[end] == "{":
            balance += 1
        elif text[end] == "}":
            balance -= 1
        end += 1
    return start, end


_STRUCTURAL_WRAPPERS = {
    "bar",
    "boldsymbol",
    "hat",
    "mathbb",
    "mathbf",
    "mathcal",
    "mathit",
    "mathrm",
    "mathsf",
    "mathtt",
    "overline",
    "text",
    "underline",
    "vec",
}


def _expanded_latex_wrapper(text: str, start: int, end: int) -> tuple[int, int]:
    while start > 0:
        opening = start - 1
        while opening >= 0 and text[opening].isspace():
            opening -= 1
        if opening < 0 or text[opening] != "{":
            break
        command_end = opening
        while command_end > 0 and text[command_end - 1].isspace():
            command_end -= 1
        command_start = command_end
        while command_start > 0 and text[command_start - 1].isalpha():
            command_start -= 1
        if command_start == 0 or text[command_start - 1] != "\\":
            break
        command_start -= 1
        if text[command_start + 1 : command_end] not in _STRUCTURAL_WRAPPERS:
            break

        depth = 1
        closing = opening + 1
        while closing < len(text) and depth:
            if text[closing] == "{":
                depth += 1
            elif text[closing] == "}":
                depth -= 1
            closing += 1
        if depth or end > closing:
            break
        start, end = command_start, closing
    return start, end


def _expanded_delimiters(
    text: str, start: int, end: int, source_text: str
) -> tuple[int, int]:
    if text[:start].count("$") % 2:
        start = text.rfind("$", 0, start)
    if text[start:end].count("$") % 2:
        closing = text.find("$", end)
        if closing >= 0:
            end = closing + 1
    pairs = {"{": "}", "[": "]"}
    if source_text[:1] in pairs:
        before = start - 1
        while before >= 0 and text[before].isspace():
            before -= 1
        if before >= 0 and text[before] == source_text[0]:
            start = before
    if source_text[-1:] in pairs.values():
        after = end
        while after < len(text) and text[after].isspace():
            after += 1
        if after < len(text) and text[after] == source_text[-1]:
            end = after + 1
    return start, end


def _candidate_format(item: Any) -> str:
    return "latex" if item.label == DocItemLabel.FORMULA else "mixed_text"


def _is_contiguous(positions: list[int]) -> bool:
    return bool(positions) and positions == list(range(positions[0], positions[-1] + 1))


def _linked(
    document: DoclingDocument,
    region: dict[str, Any],
    glyphs: list[dict[str, Any]],
    source_page_boxes: dict[int, list[float]],
) -> dict[str, Any]:
    source_page_box = source_page_boxes[region["page"]]
    text_containers = _containers(document, document.texts, region, source_page_box)
    if len(text_containers) != 1:
        picture_containers = _containers(
            document, document.pictures, region, source_page_box
        )
        if not text_containers and picture_containers:
            picture = picture_containers[0][0]
            return region | {
                "docling_ref": picture.self_ref,
                "candidate_source_kind": "picture",
                "candidate_text": "",
                "candidate_format": None,
                "candidate_charspan": None,
                "candidate_link_status": "not_linked",
                "candidate_alignment_method": None,
                "candidate_link_reason": _reason(
                    "docling_picture_candidate_missing",
                    "La région appartient à une picture Docling sans transcription candidate",
                ),
            }
        reason = (
            _reason(
                "docling_text_container_ambiguous",
                "Plusieurs éléments textuels Docling contiennent la région source",
            )
            if text_containers
            else _reason(
                "docling_text_container_missing",
                "Aucun élément textuel Docling ne contient la région source",
            )
        )
        return region | {
            "docling_ref": None,
            "candidate_source_kind": None,
            "candidate_text": "",
            "candidate_format": None,
            "candidate_charspan": None,
            "candidate_link_status": "not_linked",
            "candidate_alignment_method": None,
            "candidate_link_reason": reason,
        }
    item, container_bbox = text_containers[0]
    container_glyphs = [
        glyph
        for glyph in glyphs
        if glyph["page"] == region["page"]
        and contains_center(container_bbox, tuple(glyph["bbox"]))
    ]
    document_mapping = document_characters(item.text)
    source_mapping = source_characters(container_glyphs)
    matching = matching_positions(
        "".join(character for character, _index in document_mapping),
        "".join(character for character, _glyph in source_mapping),
    )
    target = set(region["glyph_sequence_indices"])
    target_source_positions = [
        position
        for position, (_character, glyph) in enumerate(source_mapping)
        if glyph["sequence_index"] in target
    ]
    target_positions = set(target_source_positions)
    matched_positions = {
        source_position: document_position
        for document_position, source_position in matching.items()
        if source_position in target_positions
    }
    document_positions = sorted(matched_positions.values())
    alignment_is_incomplete = (
        target_positions != set(matched_positions)
        or not _is_contiguous(target_source_positions)
    )
    alignment_method = "normalized_bbox_and_canonical_text_glyph_alignment"
    if (
        item.label != DocItemLabel.FORMULA
        and alignment_is_incomplete
        and target_source_positions
        and target_source_positions[0] in matched_positions
        and target_source_positions[-1] in matched_positions
    ):
        first = matched_positions[target_source_positions[0]]
        last = matched_positions[target_source_positions[-1]]
        exact_span_length = last - first + 1 == len(target_source_positions)
        majority_is_matched = len(matched_positions) * 2 > len(target_positions)
        if first <= last and exact_span_length and majority_is_matched:
            document_positions = list(range(first, last + 1))
            alignment_is_incomplete = False
            alignment_method = "canonical_boundary_anchored_text_glyph_alignment"
    if not document_positions or (
        item.label != DocItemLabel.FORMULA and alignment_is_incomplete
    ):
        return region | {
            "docling_ref": item.self_ref,
            "candidate_source_kind": "text",
            "candidate_text": "",
            "candidate_format": _candidate_format(item),
            "candidate_charspan": None,
            "candidate_link_status": "not_linked",
            "candidate_alignment_method": None,
            "candidate_link_reason": _reason(
                "docling_text_alignment_incomplete",
                "Un fragment de texte mixte exige l’alignement continu de tous les glyphes source",
            ),
        }
    original_positions = [document_mapping[position][1] for position in document_positions]
    start, end = min(original_positions), max(original_positions) + 1
    start, end = _expanded_latex_command(item.text, start, end)
    start, end = _expanded_latex_wrapper(item.text, start, end)
    start, end = _expanded_delimiters(
        item.text, start, end, region["source_glyph_text"]
    )
    return region | {
        "docling_ref": item.self_ref,
        "candidate_source_kind": "text",
        "candidate_text": item.text[start:end],
        "candidate_format": _candidate_format(item),
        "candidate_charspan": [start, end],
        "candidate_link_status": "linked",
        "candidate_alignment_method": alignment_method,
        "candidate_link_reason": None,
    }


def link_source_candidates(
    document: DoclingDocument,
    regions: list[dict[str, Any]],
    glyphs: list[dict[str, Any]],
    source_page_boxes: dict[int, list[float]],
) -> list[dict[str, Any]]:
    return [
        _linked(document, region, glyphs, source_page_boxes) for region in regions
    ]
