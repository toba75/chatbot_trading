from __future__ import annotations

import re
from typing import Any

import fitz
from docling_core.types.doc import DocItemLabel, DoclingDocument


TEXT_REF = re.compile(r"#/texts/(\d+)")


def overlapping_region_ids(regions: list[dict[str, Any]]) -> set[str]:
    by_ref: dict[str, list[dict[str, Any]]] = {}
    for region in regions:
        if TEXT_REF.fullmatch(str(region.get("docling_ref", ""))) and isinstance(
            region.get("candidate_charspan"), list
        ):
            by_ref.setdefault(region["docling_ref"], []).append(region)
    overlaps = set()
    for candidates in by_ref.values():
        ordered = sorted(candidates, key=lambda item: item["candidate_charspan"][0])
        for left, right in zip(ordered, ordered[1:], strict=False):
            if right["candidate_charspan"][0] < left["candidate_charspan"][1]:
                overlaps.update((left["region_id"], right["region_id"]))
    return overlaps


def ineligibility(region: dict[str, Any], document: DoclingDocument) -> str | None:
    if region.get("verdict") != "contradicted":
        return "region_not_contradicted"
    if (
        region.get("status") != "traced"
        or region.get("semantic_status") != "established"
    ):
        return "source_not_established"
    if region.get("candidate_link_status") != "linked":
        return "candidate_link_not_unique"
    if region.get("source_relation_reason") is not None:
        return region["source_relation_reason"]
    if not isinstance(region.get("source_canonical_tokens"), list) or not isinstance(
        region.get("source_relation_signature"), list
    ):
        return "source_relations_not_established"
    match = TEXT_REF.fullmatch(str(region.get("docling_ref", "")))
    if match is None or int(match.group(1)) >= len(document.texts):
        return "docling_text_reference_unsupported"
    span = region.get("candidate_charspan")
    if not isinstance(span, list) or len(span) != 2:
        return "candidate_charspan_missing"
    start, end = span
    node = document.texts[int(match.group(1))]
    if not all(isinstance(value, int) for value in span) or not (
        0 <= start < end <= len(node.text)
    ):
        return "candidate_charspan_invalid"
    if node.text[start:end] != region.get("candidate_text"):
        return "candidate_locus_mismatch"
    if node.label == DocItemLabel.FORMULA and span != [0, len(node.text)]:
        return "formula_partial_replacement_unsupported"
    bbox = region.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        return "source_bbox_missing"
    return None


def render_crop(
    page: fitz.Page, bbox: list[float], *, padding_points: float, dpi: int
) -> tuple[bytes, list[float]]:
    region = fitz.Rect(bbox)
    clip = (
        fitz.Rect(
            region.x0 - padding_points,
            region.y0 - padding_points,
            region.x1 + padding_points,
            region.y1 + padding_points,
        )
        & page.rect
    )
    if not clip.contains(region):
        raise ValueError("crop_incomplete")
    pixmap = page.get_pixmap(clip=clip, dpi=dpi, alpha=False)
    return pixmap.tobytes("png"), [clip.x0, clip.y0, clip.x1, clip.y1]
