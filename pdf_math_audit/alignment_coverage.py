from __future__ import annotations

from collections import Counter
from typing import Any

from pdf_math_audit.docling_regions import Region


def alignment_coverage(
    *,
    regions: list[Region],
    results: list[dict[str, Any]],
    glyphs: list[dict[str, Any]],
    assigned: set[tuple[int, int]],
    unassigned: list[dict[str, Any]],
    multiple: set[tuple[int, int]],
    boundary: set[tuple[int, int]],
    unassigned_indicators: list[dict[str, Any]],
    indicator_region_count: int,
    source_regions: list[dict[str, Any]],
) -> dict[str, int]:
    statuses = Counter(result["status"] for result in results)
    return {
        "regions_total": len(regions),
        "formula_regions": sum(region.kind == "formula" for region in regions),
        "inline_math_regions": sum(region.kind == "inline_math" for region in regions),
        "regions_traced": statuses["traced"],
        "regions_ambiguous": statuses["ambiguous"],
        "regions_unsupported": statuses["unsupported"],
        "regions_not_traced": statuses["not_traced"],
        "glyphs_assigned": len(assigned),
        "glyphs_observed": len(glyphs),
        "glyphs_unassigned": len(unassigned),
        "glyphs_with_multiple_regions": len(multiple),
        "boundary_glyphs": len(boundary),
        "pdf_math_indicators_unassigned": len(unassigned_indicators),
        "pdf_math_indicator_regions": indicator_region_count,
        "pdf_source_math_regions": len(source_regions),
        "pdf_source_math_regions_without_docling_overlap": sum(
            not region["docling_overlap_glyph_sequence_indices"]
            for region in source_regions
        ),
    }
