from __future__ import annotations

import math


MIN_GLYPH_OVERLAP_RATIO = 0.5
PAGE_SIZE_TOLERANCE_POINTS = 0.5


def page_geometry_matches(
    pdf_box: list[float], docling_width: float, docling_height: float
) -> bool:
    return all(
        math.isclose(value, expected, abs_tol=PAGE_SIZE_TOLERANCE_POINTS)
        for value, expected in (
            (pdf_box[0], 0),
            (pdf_box[1], 0),
            (pdf_box[2] - pdf_box[0], docling_width),
            (pdf_box[3] - pdf_box[1], docling_height),
        )
    )


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
