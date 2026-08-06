from __future__ import annotations

import unicodedata
from collections import defaultdict
from typing import Any


def is_math_indicator(text: str) -> bool:
    return any(unicodedata.category(character) == "Sm" for character in text)


def glyph_reference(page: int, glyph: dict[str, Any]) -> dict[str, Any]:
    return {
        "page": page,
        "sequence_index": glyph["sequence_index"],
        "glyph_name": glyph["glyph_name"],
        "unicode": glyph["source_unicode"],
        "source_unicode": glyph["source_unicode"],
        "source_unicode_method": glyph["source_unicode_method"],
        "agl_unicode": glyph["agl_unicode"],
        "bbox": glyph["rendered"]["bbox"],
        "font_resource": glyph["font_resource"],
        "code": glyph["code"],
        "code_hex": glyph["code_hex"],
        "cff_gid": glyph["cff_gid"],
        "font_math_glyph_evidence": glyph.get("font_math_glyph_evidence", []),
        "rendered_gid": glyph["rendered"]["gid"],
        "to_unicode": glyph["to_unicode"],
        "rendered_unicode": glyph["rendered"]["unicode_text"],
        "rendered_font": glyph["rendered"]["font"],
        "rendered_origin_x": glyph["rendered"]["origin"][0],
        "rendered_origin_y": glyph["rendered"]["origin"][1],
        "rendered_size": glyph["rendered"]["size"],
        "rawdict": glyph["rawdict"],
    }


def unassigned_glyphs(
    glyphs: list[dict[str, Any]], assigned: set[tuple[int, int]]
) -> list[dict[str, Any]]:
    return [
        glyph
        for glyph in glyphs
        if (glyph["page"], glyph["sequence_index"]) not in assigned
    ]


def unassigned_index(unassigned: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_page: dict[int, list[int]] = defaultdict(list)
    for glyph in unassigned:
        by_page[glyph["page"]].append(glyph["sequence_index"])
    return [
        {"page": page, "glyph_sequence_indices": sorted(indices)}
        for page, indices in sorted(by_page.items())
    ]


def indicator_regions(unassigned: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_line: dict[tuple[int, int, int], list[dict[str, Any]]] = defaultdict(list)
    for glyph in unassigned:
        rawdict = glyph["rawdict"]
        by_line[(glyph["page"], rawdict["block"], rawdict["line"])].append(glyph)

    regions = []
    for (page, _block, _line), glyphs in sorted(by_line.items()):
        indicators = [glyph for glyph in glyphs if is_math_indicator(glyph["unicode"])]
        if not indicators:
            continue
        ordered = sorted(glyphs, key=lambda glyph: glyph["sequence_index"])
        regions.append(
            {
                "page": page,
                "bbox": ordered[0]["rawdict"]["line_bbox"],
                "bbox_coord_origin": "TOPLEFT",
                "method": "unassigned_unicode_math_symbol_in_pdf_line",
                "glyph_sequence_indices": [
                    glyph["sequence_index"] for glyph in ordered
                ],
                "source_glyph_text": "".join(glyph["unicode"] for glyph in ordered),
                "indicator_glyph_sequence_indices": [
                    glyph["sequence_index"] for glyph in indicators
                ],
            }
        )
    return regions
