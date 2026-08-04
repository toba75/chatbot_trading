from __future__ import annotations

from typing import Any

from docling_core.types.doc import DoclingDocument

from pdf_math_audit.events import ProgressCallback
from pdf_math_audit.geometry import overlaps
from pdf_math_audit.semantic_evaluation import evaluate_regions
from pdf_math_audit.source_candidate_linking import link_source_candidates
from pdf_math_audit.source_math_regions import source_math_regions


def evaluate_source_regions(
    document: DoclingDocument,
    glyphs: list[dict[str, Any]],
    pdf_report: dict[str, Any],
    associated: set[tuple[int, int]],
    on_progress: ProgressCallback | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    page_fonts = {page["page"]: page["fonts"] for page in pdf_report["pages"]}
    page_rules = {
        page["page"]: page.get("horizontal_rules", []) for page in pdf_report["pages"]
    }
    partial_pages = {
        page["page"]
        for page in pdf_report["pages"]
        if page["status"] == "partially_traced"
    }
    opaque_regions = {
        page["page"]: page.get("opaque_regions", [])
        for page in pdf_report["pages"]
        if page["status"] == "traced_with_exclusions"
    }
    source_page_boxes = {page["page"]: page["box"] for page in pdf_report["pages"]}
    regions = source_math_regions(glyphs, page_fonts, page_rules)
    for region in regions:
        if region["page"] in partial_pages:
            region["status"] = "not_traced"
            region["trace_limitation"] = "pdf_page_partially_traced"
        intersections = [
            exclusion
            for exclusion in opaque_regions.get(region["page"], [])
            if overlaps(tuple(region["bbox"]), exclusion["bbox"])
        ]
        if intersections:
            region["status"] = "not_traced"
            region["trace_limitation"] = "pdf_opaque_region_intersection"
            region["trace_exclusions"] = intersections
        region["docling_overlap_glyph_sequence_indices"] = [
            index
            for index in region["glyph_sequence_indices"]
            if (region["page"], index) in associated
        ]
    linked = link_source_candidates(document, regions, glyphs, source_page_boxes)
    return evaluate_regions(linked, glyphs, on_progress=on_progress)
