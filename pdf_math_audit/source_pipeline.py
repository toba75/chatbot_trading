from __future__ import annotations

from typing import Any

from docling_core.types.doc import DoclingDocument

from pdf_math_audit.events import ProgressCallback
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
    regions = source_math_regions(glyphs, page_fonts)
    for region in regions:
        region["docling_overlap_glyph_sequence_indices"] = [
            index
            for index in region["glyph_sequence_indices"]
            if (region["page"], index) in associated
        ]
    linked = link_source_candidates(document, regions, glyphs)
    return evaluate_regions(linked, glyphs, on_progress=on_progress)
