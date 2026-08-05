from __future__ import annotations

import math
from typing import Any


MIN_GLYPH_OVERLAP_RATIO = 0.5
PAGE_SIZE_TOLERANCE_POINTS = 0.5


def page_geometry_matches(
    pdf_box: list[float], docling_width: float, docling_height: float
) -> bool:
    return page_geometry_scale(pdf_box, docling_width, docling_height) is not None


def page_geometry_scale(
    pdf_box: list[float], docling_width: float, docling_height: float
) -> tuple[float, float] | None:
    if (
        not math.isclose(pdf_box[0], 0, abs_tol=PAGE_SIZE_TOLERANCE_POINTS)
        or not math.isclose(pdf_box[1], 0, abs_tol=PAGE_SIZE_TOLERANCE_POINTS)
        or docling_width <= 0
        or docling_height <= 0
    ):
        return None
    pdf_width = pdf_box[2] - pdf_box[0]
    pdf_height = pdf_box[3] - pdf_box[1]
    scale_x = pdf_width / docling_width
    scale_y = pdf_height / docling_height
    if not math.isclose(scale_x, scale_y, rel_tol=1e-3):
        return None
    scale = (scale_x + scale_y) / 2
    residual = max(
        abs(docling_width * scale - pdf_width),
        abs(docling_height * scale - pdf_height),
    )
    if residual > PAGE_SIZE_TOLERANCE_POINTS:
        return None
    return scale, residual


def scale_bbox(
    bbox: tuple[float, float, float, float] | None, scale: float
) -> tuple[float, float, float, float] | None:
    return None if bbox is None else tuple(value * scale for value in bbox)


def overlaps(region: tuple[float, ...], glyph: list[float]) -> bool:
    return max(region[0], glyph[0]) < min(region[2], glyph[2]) and max(
        region[1], glyph[1]
    ) < min(region[3], glyph[3])


def contains_center(region: tuple[float, ...], glyph: list[float]) -> bool:
    center_x = (glyph[0] + glyph[2]) / 2
    center_y = (glyph[1] + glyph[3]) / 2
    return region[0] <= center_x <= region[2] and region[1] <= center_y <= region[3]


def overlap_ratio(region: tuple[float, ...], glyph: list[float]) -> float:
    glyph_area = (glyph[2] - glyph[0]) * (glyph[3] - glyph[1])
    if glyph_area <= 0:
        return 0.0
    intersection_width = max(0.0, min(region[2], glyph[2]) - max(region[0], glyph[0]))
    intersection_height = max(0.0, min(region[3], glyph[3]) - max(region[1], glyph[1]))
    return intersection_width * intersection_height / glyph_area


def rule_covers_horizontal_span(
    rule: dict[str, float | int], glyphs: list[dict[str, Any]]
) -> bool:
    glyph_x0 = min(glyph["bbox"][0] for glyph in glyphs)
    glyph_x1 = max(glyph["bbox"][2] for glyph in glyphs)
    tolerance = min(max(0.1, float(rule["width"])), (glyph_x1 - glyph_x0) * 0.2)
    return (
        float(rule["x0"]) <= glyph_x0 + tolerance
        and float(rule["x1"]) >= glyph_x1 - tolerance
    )


def rule_fits_horizontal_span(
    rule: dict[str, float | int], glyphs: list[dict[str, Any]]
) -> bool:
    glyph_x0 = min(glyph["bbox"][0] for glyph in glyphs)
    glyph_x1 = max(glyph["bbox"][2] for glyph in glyphs)
    tolerance = min(max(1.0, float(rule["width"]) * 2), (glyph_x1 - glyph_x0) * 0.25)
    return (
        float(rule["x0"]) >= glyph_x0 - tolerance
        and float(rule["x1"]) <= glyph_x1 + tolerance
    )
