from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from typing import Any

from docling_core.types.doc import DoclingDocument

from pdf_math_audit.alignment_coverage import alignment_coverage
from pdf_math_audit.docling_regions import Region, extract_regions
from pdf_math_audit.events import ProgressCallback, progress_event
from pdf_math_audit.geometry import (
    MIN_GLYPH_OVERLAP_RATIO,
    PAGE_SIZE_TOLERANCE_POINTS,
    contains_center,
    overlap_ratio,
    overlaps,
    page_geometry_matches,
    page_geometry_scale,
    scale_bbox,
)
from pdf_math_audit.inline_alignment import assignment_conflicts, localize_inline_regions
from pdf_math_audit.pdf_indicators import (
    glyph_reference,
    indicator_regions,
    is_math_indicator,
    unassigned_glyphs,
    unassigned_index,
)
from pdf_math_audit.source_pipeline import evaluate_source_regions


def _reason(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _glyph_keys(
    regions: list[dict[str, Any]], field: str, status: str | None = None
) -> set[tuple[int, int]]:
    return {
        (region["page"], sequence)
        for region in regions
        if status is None or region["status"] == status
        for sequence in region[field]
    }


class DoclingAlignment:
    def __init__(self, document: DoclingDocument) -> None:
        self.document = document
        self.regions = extract_regions(document)
        self._formula_by_page: dict[int, list[Region]] = defaultdict(list)
        for region in self.regions:
            if (
                region.kind == "formula"
                and region.page is not None
                and region.bbox is not None
                and region.reason is None
            ):
                self._formula_by_page[region.page].append(region)
        self._assigned: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._boundary: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._multiple: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._glyphs: list[dict[str, Any]] = []

    def observe_glyph(self, page: int, glyph: dict[str, Any]) -> None:
        reference = glyph_reference(page, glyph)
        self._glyphs.append(reference)
        self._assign_glyph(reference)

    def _assign_glyph(self, reference: dict[str, Any]) -> None:
        page = reference["page"]
        glyph_bbox = reference["bbox"]
        regions = self._formula_by_page.get(page, [])
        centered = [
            region
            for region in regions
            if contains_center(region.bbox, glyph_bbox)  # type: ignore[arg-type]
            and overlap_ratio(region.bbox, glyph_bbox) >= MIN_GLYPH_OVERLAP_RATIO  # type: ignore[arg-type]
        ]
        overlapping = [
            region
            for region in regions
            if overlaps(region.bbox, glyph_bbox)  # type: ignore[arg-type]
        ]
        for region in centered:
            self._assigned[region.region_id].append(reference)
        if len(centered) > 1:
            for region in centered:
                self._multiple[region.region_id].append(reference)
        for region in overlapping:
            if region not in centered:
                self._boundary[region.region_id].append(reference)

    def _normalize_regions(
        self, pages: dict[int, Any]
    ) -> tuple[list[Region], list[dict[str, Any]]]:
        scales: dict[int, float] = {}
        transforms = []
        for page_number, docling_page in self.document.pages.items():
            if page_number not in pages:
                continue
            pdf_box = pages[page_number]["box"]
            geometry = page_geometry_scale(
                pdf_box, docling_page.size.width, docling_page.size.height
            )
            if geometry is None:
                continue
            scale, residual = geometry
            scales[page_number] = scale
            transforms.append(
                {
                    "page": page_number,
                    "method": "uniform_page_scale",
                    "docling_size": [
                        float(docling_page.size.width),
                        float(docling_page.size.height),
                    ],
                    "pdf_box": [float(value) for value in pdf_box],
                    "scale": scale,
                    "max_residual_points": residual,
                }
            )
        return [
            replace(
                region,
                bbox=scale_bbox(region.bbox, scales[region.page]),
                container_bbox=scale_bbox(
                    region.container_bbox, scales[region.page]
                ),
            )
            if region.page in scales
            else region
            for region in self.regions
        ], transforms

    def _reset_assignments(self, regions: list[Region]) -> None:
        self._formula_by_page = defaultdict(list)
        for region in regions:
            if (
                region.kind == "formula"
                and region.page is not None
                and region.bbox is not None
                and region.reason is None
            ):
                self._formula_by_page[region.page].append(region)
        self._assigned = defaultdict(list)
        self._boundary = defaultdict(list)
        self._multiple = defaultdict(list)
        for glyph in self._glyphs:
            self._assign_glyph(glyph)

    def _page_geometry_matches(self, region: Region, pages: dict[int, Any]) -> bool:
        docling_size = self.document.pages[region.page].size
        return page_geometry_matches(
            pages[region.page]["box"],
            docling_size.width,
            docling_size.height,
        )

    def _region_result(self, region: Region, pages: dict[int, Any]) -> dict[str, Any]:
        glyphs = sorted(
            self._assigned.get(region.region_id, []),
            key=lambda glyph: glyph["sequence_index"],
        )
        boundary = self._boundary.get(region.region_id, [])
        multiple = self._multiple.get(region.region_id, [])
        reasons = []
        trace_exclusions = []
        status = "traced"
        if region.reason is not None:
            status = "not_traced"
            reasons.append(region.reason)
        elif region.page not in pages:
            status = "not_traced"
            reasons.append(
                _reason(
                    "pdf_page_not_traced",
                    "La page PDF ne fournit aucune trace exploitable",
                )
            )
        elif pages[region.page]["status"] == "traced_with_exclusions" and (
            trace_exclusions := [
                exclusion
                for exclusion in pages[region.page].get("opaque_regions", [])
                if overlaps(region.bbox, exclusion["bbox"])  # type: ignore[arg-type]
            ]
        ):
            status = "not_traced"
            glyphs = []
            boundary = []
            multiple = []
            reasons.append(
                _reason(
                    "pdf_opaque_region_intersection",
                    "La région Docling intersecte une zone PDF opaque non qualifiée",
                )
            )
        elif pages[region.page]["status"] == "partially_traced":
            status = "not_traced"
            glyphs = []
            boundary = []
            multiple = []
            reasons.append(
                _reason(
                    "pdf_page_partially_traced",
                    "La région Docling ne peut pas être prouvée sur une page partiellement tracée",
                )
            )
            reasons.extend(pages[region.page]["reasons"])
        elif pages[region.page]["status"] not in {
            "traced",
            "traced_with_exclusions",
        }:
            status = pages[region.page]["status"]
            glyphs = []
            boundary = []
            multiple = []
            reasons.extend(pages[region.page]["reasons"])
        elif not self._page_geometry_matches(region, pages):
            status = "ambiguous"
            glyphs = []
            boundary = []
            multiple = []
            reasons.append(
                _reason(
                    "page_geometry_mismatch",
                    "Les géométries de page PDF et Docling divergent",
                )
            )
        elif multiple:
            status = "ambiguous"
            reasons.append(
                _reason(
                    "glyph_assigned_to_multiple_regions",
                    "Au moins un glyphe appartient à plusieurs régions",
                )
            )
        elif boundary:
            status = "ambiguous"
            reasons.append(
                _reason(
                    "boundary_glyph_intersection",
                    "Un glyphe coupe la frontière ou reste majoritairement extérieur",
                )
            )
        elif not glyphs:
            status = "not_traced"
            reasons.append(
                _reason(
                    "no_glyph_center_in_bbox",
                    "Aucun centre de glyphe ne se trouve dans la provenance",
                )
            )
        return {
            "region_id": region.region_id,
            "kind": region.kind,
            "docling_ref": region.docling_ref,
            "provenance_index": region.provenance_index,
            "page": region.page,
            "bbox": list(region.bbox) if region.bbox is not None else None,
            "bbox_coord_origin": "TOPLEFT" if region.bbox is not None else None,
            "container_bbox": (
                list(region.container_bbox)
                if region.container_bbox is not None
                else None
            ),
            "charspan": list(region.charspan),
            "candidate_text": region.candidate_text,
            "localization_method": region.localization_method,
            "status": status,
            "glyph_count": len(glyphs),
            "glyph_sequence_indices": [glyph["sequence_index"] for glyph in glyphs],
            "source_glyph_text": "".join(glyph["unicode"] for glyph in glyphs),
            "boundary_glyph_sequence_indices": [
                glyph["sequence_index"] for glyph in boundary
            ],
            "multiple_region_glyph_sequence_indices": [
                glyph["sequence_index"] for glyph in multiple
            ],
            "reasons": reasons,
            "trace_exclusions": trace_exclusions,
        }

    def finalize(
        self,
        pdf_report: dict[str, Any],
        on_progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        pages = {page["page"]: page for page in pdf_report["pages"]}
        normalized_regions, geometry_transforms = self._normalize_regions(pages)
        self._reset_assignments(normalized_regions)
        regions, inline_assignments = localize_inline_regions(
            self.document, normalized_regions, self._glyphs
        )
        self._assigned.update(inline_assignments)
        self._multiple = assignment_conflicts(self._assigned)
        total = len(regions)
        if on_progress:
            on_progress(progress_event("docling_alignment", 0, total))
        results = []
        for completed, region in enumerate(regions, start=1):
            results.append(self._region_result(region, pages))
            if on_progress:
                on_progress(progress_event("docling_alignment", completed, total))
        assigned = _glyph_keys(results, "glyph_sequence_indices", "traced")
        associated = _glyph_keys(results, "glyph_sequence_indices")
        multiple = _glyph_keys(results, "multiple_region_glyph_sequence_indices")
        boundary = _glyph_keys(results, "boundary_glyph_sequence_indices")
        unassigned = unassigned_glyphs(self._glyphs, associated)
        unassigned_indicators = [
            {
                key: glyph[key]
                for key in ("page", "sequence_index", "glyph_name", "unicode", "bbox")
            }
            | {"indicator": "unicode_math_symbol"}
            for glyph in unassigned
            if is_math_indicator(glyph["unicode"])
        ]
        pdf_regions = indicator_regions(unassigned)
        source_regions, evaluation_metrics = evaluate_source_regions(
            self.document,
            self._glyphs,
            pdf_report,
            associated,
            on_progress,
        )
        return {
            "schema_version": "1.0",
            "capability_profile": "docling-formula-bbox-v1",
            "page_size_tolerance_points": PAGE_SIZE_TOLERANCE_POINTS,
            "minimum_glyph_overlap_ratio": MIN_GLYPH_OVERLAP_RATIO,
            "page_geometry_transforms": geometry_transforms,
            "coverage": alignment_coverage(
                regions=regions,
                results=results,
                glyphs=self._glyphs,
                assigned=assigned,
                unassigned=unassigned,
                multiple=multiple,
                boundary=boundary,
                unassigned_indicators=unassigned_indicators,
                indicator_region_count=len(pdf_regions),
                source_regions=source_regions,
            ),
            "regions": results,
            "evaluation": evaluation_metrics,
            "unassigned_glyphs": unassigned_index(unassigned),
            "pdf_math_indicators_unassigned": unassigned_indicators,
            "pdf_math_indicator_regions": pdf_regions,
            "pdf_source_math_regions": source_regions,
        }
