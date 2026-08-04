from __future__ import annotations

import re
from typing import Any

import fitz
from docling_core.types.doc import DocItemLabel, DoclingDocument

from pdf_math_audit.latex_locus import formula_locus


TEXT_REF = re.compile(r"#/texts/(\d+)")
MISSING_CANDIDATE_REASONS = {
    "docling_picture_candidate_missing",
    "docling_text_container_missing",
}


def _missing_candidate(region: dict[str, Any]) -> bool:
    reason = region.get("candidate_link_reason")
    return (
        isinstance(reason, dict)
        and reason.get("code") in MISSING_CANDIDATE_REASONS
    )


def _target(
    kind: str,
    regions: list[dict[str, Any]],
    document: DoclingDocument,
) -> dict[str, Any]:
    ordered = sorted(
        regions,
        key=lambda region: min(region.get("glyph_sequence_indices") or [0]),
    )
    first = ordered[0]
    bboxes = [region["bbox"] for region in ordered]
    target = {
        "target_id": (
            first["region_id"]
            if len(ordered) == 1
            else f"{kind}:{first['region_id']}"
        ),
        "kind": kind,
        "regions": ordered,
        "page": first["page"],
        "bbox": [
            min(bbox[0] for bbox in bboxes),
            min(bbox[1] for bbox in bboxes),
            max(bbox[2] for bbox in bboxes),
            max(bbox[3] for bbox in bboxes),
        ],
        "docling_ref": first.get("docling_ref"),
        "candidate_format": first.get("candidate_format"),
    }
    if kind == "formula_replacement":
        match = TEXT_REF.fullmatch(str(first["docling_ref"]))
        if match is None:
            raise ValueError("docling_text_reference_unsupported")
        node = document.texts[int(match.group(1))]
        expanded = []
        minimum_start = 0
        for region in ordered:
            span = region.get("candidate_charspan")
            if (
                not isinstance(span, list)
                or len(span) != 2
                or not all(isinstance(value, int) for value in span)
                or not (0 <= span[0] < span[1] <= len(node.text))
            ):
                expanded.append(region)
                continue
            start, end, candidate_text = formula_locus(
                node.text,
                region,
                minimum_start=minimum_start,
            )
            expanded.append(
                region
                | {
                    "candidate_charspan": [start, end],
                    "candidate_text": candidate_text,
                }
            )
            minimum_start = end
        target["regions"] = expanded
        target.update(
            candidate_charspan=[0, len(node.text)],
            candidate_text=node.text,
            candidate_format="latex",
        )
    elif kind == "merged_replacement":
        match = TEXT_REF.fullmatch(str(first["docling_ref"]))
        if match is None:
            raise ValueError("docling_text_reference_unsupported")
        spans = [region["candidate_charspan"] for region in ordered]
        start = min(span[0] for span in spans)
        end = max(span[1] for span in spans)
        node = document.texts[int(match.group(1))]
        target.update(
            candidate_charspan=[start, end],
            candidate_text=node.text[start:end],
            candidate_format="mixed_text",
        )
    else:
        target.update(
            candidate_charspan=first.get("candidate_charspan"),
            candidate_text=first.get("candidate_text", ""),
        )
    return target


def correction_targets(
    regions: list[dict[str, Any]], document: DoclingDocument
) -> tuple[list[dict[str, Any]], int]:
    candidates = [
        region
        for region in regions
        if region.get("verdict") == "contradicted" or _missing_candidate(region)
    ]
    assigned: set[str] = set()
    targets: list[dict[str, Any]] = []

    formula_regions: dict[str, list[dict[str, Any]]] = {}
    for region in candidates:
        if region.get("verdict") != "contradicted":
            continue
        match = TEXT_REF.fullmatch(str(region.get("docling_ref", "")))
        if (
            match is not None
            and int(match.group(1)) < len(document.texts)
            and document.texts[int(match.group(1))].label == DocItemLabel.FORMULA
        ):
            formula_regions.setdefault(region["docling_ref"], []).append(region)
    for group in formula_regions.values():
        targets.append(_target("formula_replacement", group, document))
        assigned.update(region["region_id"] for region in group)

    by_ref: dict[str, list[dict[str, Any]]] = {}
    for region in candidates:
        if region["region_id"] in assigned or region.get("verdict") != "contradicted":
            continue
        if TEXT_REF.fullmatch(str(region.get("docling_ref", ""))) and isinstance(
            region.get("candidate_charspan"), list
        ):
            by_ref.setdefault(region["docling_ref"], []).append(region)
    for group in by_ref.values():
        ordered = sorted(group, key=lambda region: region["candidate_charspan"][0])
        component = [ordered[0]]
        component_end = ordered[0]["candidate_charspan"][1]
        for region in ordered[1:]:
            start, end = region["candidate_charspan"]
            if start < component_end:
                component.append(region)
                component_end = max(component_end, end)
            else:
                if len(component) > 1:
                    targets.append(_target("merged_replacement", component, document))
                    assigned.update(item["region_id"] for item in component)
                component = [region]
                component_end = end
        if len(component) > 1:
            targets.append(_target("merged_replacement", component, document))
            assigned.update(item["region_id"] for item in component)

    for region in candidates:
        if region["region_id"] in assigned:
            continue
        kind = "formula_insertion" if _missing_candidate(region) else "replacement"
        targets.append(_target(kind, [region], document))

    targets.sort(
        key=lambda target: (
            target["page"],
            min(target["regions"][0].get("glyph_sequence_indices") or [0]),
        )
    )
    return targets, len(candidates)


def _source_ineligibility(region: dict[str, Any]) -> str | None:
    if (
        region.get("status") != "traced"
        or region.get("semantic_status") != "established"
    ):
        return "source_not_established"
    if region.get("source_relation_reason") is not None:
        return region["source_relation_reason"]
    if not isinstance(region.get("source_canonical_tokens"), list) or not isinstance(
        region.get("source_relation_signature"), list
    ):
        return "source_relations_not_established"
    bbox = region.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        return "source_bbox_missing"
    return None


def acquisition_ineligibility(region: dict[str, Any]) -> str | None:
    if not _missing_candidate(region):
        return "candidate_missing_reason_unsupported"
    return _source_ineligibility(region)


def ineligibility(
    region: dict[str, Any],
    document: DoclingDocument,
    *,
    allow_partial_formula: bool = False,
) -> str | None:
    if region.get("verdict") != "contradicted":
        return "region_not_contradicted"
    if reason := _source_ineligibility(region):
        return reason
    if region.get("candidate_link_status") != "linked":
        return "candidate_link_not_unique"
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
    if (
        node.label == DocItemLabel.FORMULA
        and span != [0, len(node.text)]
        and not allow_partial_formula
    ):
        return "formula_partial_replacement_unsupported"
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
