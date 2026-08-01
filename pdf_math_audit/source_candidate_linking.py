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


def _bbox(document: DoclingDocument, item: Any, provenance: Any) -> tuple[float, ...]:
    page = document.pages[provenance.page_no]
    return tuple(
        float(value)
        for value in provenance.bbox.to_top_left_origin(page.size.height).as_tuple()
    )


def _container(
    document: DoclingDocument, region: dict[str, Any]
) -> tuple[Any, tuple[float, ...]] | None:
    center = (
        (region["bbox"][0] + region["bbox"][2]) / 2,
        (region["bbox"][1] + region["bbox"][3]) / 2,
    )
    matching = [
        (item, _bbox(document, item, provenance))
        for item in document.texts
        for provenance in item.prov
        if provenance.page_no == region["page"]
        and (
            (box := _bbox(document, item, provenance))[0]
            <= center[0]
            <= box[2]
            and box[1]
            <= center[1]
            <= box[3]
        )
    ]
    if len(matching) != 1:
        return None
    return matching[0]


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
    opening = source_text[:1]
    closing = pairs.get(opening)
    if closing is not None and source_text.endswith(closing):
        before = start - 1
        while before >= 0 and text[before].isspace():
            before -= 1
        after = end
        while after < len(text) and text[after].isspace():
            after += 1
        if before >= 0 and text[before] == opening:
            start = before
        if after < len(text) and text[after] == closing:
            end = after + 1
    return start, end


def _candidate_format(item: Any) -> str:
    return "latex" if item.label == DocItemLabel.FORMULA else "mixed_text"


def _linked(
    document: DoclingDocument,
    region: dict[str, Any],
    glyphs: list[dict[str, Any]],
) -> dict[str, Any]:
    container = _container(document, region)
    if container is None:
        return region | {
            "docling_ref": None,
            "candidate_text": "",
            "candidate_format": None,
            "candidate_charspan": None,
            "candidate_link_status": "not_linked",
            "candidate_alignment_method": None,
            "candidate_link_reason": _reason(
                "docling_container_missing",
                "Aucun élément Docling unique ne contient la région source",
            ),
        }
    item, container_bbox = container
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
    document_positions = [
        document_position
        for document_position, source_position in matching.items()
        if source_mapping[source_position][1]["sequence_index"] in target
    ]
    if not document_positions:
        return region | {
            "docling_ref": item.self_ref,
            "candidate_text": "",
            "candidate_format": _candidate_format(item),
            "candidate_charspan": None,
            "candidate_link_status": "not_linked",
            "candidate_alignment_method": None,
            "candidate_link_reason": _reason(
                "docling_text_alignment_missing",
                "Aucun caractère Docling ne correspond aux glyphes de la région",
            ),
        }
    original_positions = [document_mapping[position][1] for position in document_positions]
    start, end = min(original_positions), max(original_positions) + 1
    start, end = _expanded_delimiters(
        item.text, start, end, region["source_glyph_text"]
    )
    return region | {
        "docling_ref": item.self_ref,
        "candidate_text": item.text[start:end],
        "candidate_format": _candidate_format(item),
        "candidate_charspan": [start, end],
        "candidate_link_status": "linked",
        "candidate_alignment_method": "global_text_glyph_alignment",
        "candidate_link_reason": None,
    }


def link_source_candidates(
    document: DoclingDocument,
    regions: list[dict[str, Any]],
    glyphs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [_linked(document, region, glyphs) for region in regions]
