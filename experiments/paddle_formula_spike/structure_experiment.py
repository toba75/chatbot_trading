from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import fitz

from experiments.paddle_formula_spike.experiment import load_json


def insertion_regions(
    corrections: dict[str, Any], report: dict[str, Any]
) -> tuple[list[int], list[dict[str, Any]], list[dict[str, Any]]]:
    insertion_ids = {
        proof["region_id"]
        for target in corrections["records"]
        if target["kind"] == "formula_insertion"
        for proof in target["source_proofs"]
    }
    source_regions = report["alignment"]["pdf_source_math_regions"]
    available_ids = {region["region_id"] for region in source_regions}
    missing_ids = insertion_ids - available_ids
    if missing_ids:
        missing = ", ".join(sorted(missing_ids))
        raise ValueError(f"Missing insertion source regions in report: {missing}")
    insertions = [
        region for region in source_regions if region["region_id"] in insertion_ids
    ]
    pages = sorted({region["page"] for region in insertions})
    controls = [region for region in source_regions if region["page"] in pages]
    return pages, insertions, controls


def prepare(
    pdf_path: Path,
    corrections_path: Path,
    report_path: Path,
    output_dir: Path,
    *,
    dpi: int,
) -> dict[str, Any]:
    corrections = load_json(corrections_path)
    report = load_json(report_path)
    pages, insertions, controls = insertion_regions(corrections, report)
    pages_dir = output_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    scale = dpi / 72.0
    rendered_pages = []
    with fitz.open(pdf_path) as document:
        for page_number in pages:
            pixmap = document[page_number - 1].get_pixmap(
                matrix=fitz.Matrix(scale, scale), alpha=False
            )
            filename = f"page-{page_number:03d}.png"
            pixmap.save(pages_dir / filename)
            rendered_pages.append(
                {
                    "page": page_number,
                    "image": f"pages/{filename}",
                    "width": pixmap.width,
                    "height": pixmap.height,
                }
            )
    manifest = {
        "corpus": "document-19-qualification-51-formula-insertions",
        "dpi": dpi,
        "scale": scale,
        "pages": rendered_pages,
        "insertions": [compact_region(region) for region in insertions],
        "source_controls": [compact_region(region) for region in controls],
    }
    (output_dir / "structure-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def compact_region(region: dict[str, Any]) -> dict[str, Any]:
    return {
        "region_id": region["region_id"],
        "page": region["page"],
        "bbox": region["bbox"],
        "docling_ref": region.get("docling_ref"),
        "source_tokens": region["source_canonical_tokens"],
        "source_signature": region["source_relation_signature"],
    }


def polygon_bbox(polygon: list[Any]) -> list[float]:
    points = polygon
    if points and not isinstance(points[0], (list, tuple)):
        points = list(zip(points[::2], points[1::2]))
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return [min(xs), min(ys), max(xs), max(ys)]


def contains_center(outer: list[float], inner: list[float]) -> bool:
    center_x = (inner[0] + inner[2]) / 2
    center_y = (inner[1] + inner[3]) / 2
    return outer[0] <= center_x <= outer[2] and outer[1] <= center_y <= outer[3]


def scaled_bbox(bbox: list[float], scale: float) -> list[float]:
    return [coordinate * scale for coordinate in bbox]


def formula_predictions(page_result: dict[str, Any]) -> list[dict[str, Any]]:
    predictions = []
    for formula in page_result.get("formula_res_list", []):
        polygon = formula.get("rec_polys", formula.get("dt_polys"))
        if polygon is None:
            raise ValueError("Coordonnées absentes du résultat de formule")
        predictions.append(
            {
                "formula_region_id": formula.get("formula_region_id"),
                "latex": formula.get("rec_formula"),
                "bbox": polygon_bbox(polygon),
            }
        )
    return predictions


def evaluate(
    manifest_path: Path, predictions_path: Path, output_path: Path
) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    predictions = load_json(predictions_path)
    pages = {page["page"]: page["result"] for page in predictions["pages"]}
    formulas = {
        page: formula_predictions(result) for page, result in pages.items()
    }
    insertions = []
    for region in manifest["insertions"]:
        bbox = scaled_bbox(region["bbox"], manifest["scale"])
        matches = [
            formula
            for formula in formulas[region["page"]]
            if contains_center(formula["bbox"], bbox)
        ]
        insertions.append(
            {
                **region,
                "rendered_bbox": bbox,
                "size_class": (
                    "inline_like"
                    if region["bbox"][3] - region["bbox"][1] <= 20
                    and region["bbox"][2] - region["bbox"][0] <= 120
                    else "display_like"
                ),
                "source_group": (
                    "picture"
                    if (region.get("docling_ref") or "").startswith("#/pictures/")
                    else "unanchored"
                ),
                "formula_matches": matches,
                "detected": bool(matches),
                "unique_detection": len(matches) == 1,
            }
        )

    unmatched_predictions = 0
    detected_controls = 0
    for page, page_formulas in formulas.items():
        controls = [
            scaled_bbox(region["bbox"], manifest["scale"])
            for region in manifest["source_controls"]
            if region["page"] == page
        ]
        detected_controls += sum(
            any(contains_center(formula["bbox"], control) for formula in page_formulas)
            for control in controls
        )
        unmatched_predictions += sum(
            not any(contains_center(formula["bbox"], control) for control in controls)
            for formula in page_formulas
        )
    by_class = Counter(record["size_class"] for record in insertions)
    detected_by_class = Counter(
        record["size_class"] for record in insertions if record["detected"]
    )
    by_source_group = Counter(record["source_group"] for record in insertions)
    detected_by_source_group = Counter(
        record["source_group"] for record in insertions if record["detected"]
    )
    matched_formulas = {
        (record["page"], formula["formula_region_id"])
        for record in insertions
        for formula in record["formula_matches"]
    }
    result = {
        "summary": {
            "pages": len(pages),
            "insertions": len(insertions),
            "formula_predictions": sum(len(items) for items in formulas.values()),
            "detected_insertions": sum(record["detected"] for record in insertions),
            "unique_insertions": sum(
                record["unique_detection"] for record in insertions
            ),
            "matched_formula_predictions": len(matched_formulas),
            "insertions_by_class": dict(by_class),
            "detected_by_class": dict(detected_by_class),
            "insertions_by_source_group": dict(by_source_group),
            "detected_by_source_group": dict(detected_by_source_group),
            "predictions_without_source_region_center": unmatched_predictions,
            "detected_source_controls": detected_controls,
            "model_load_seconds": predictions["model_load_seconds"],
            "inference_seconds": predictions["inference_seconds"],
        },
        "insertions": insertions,
        "pages": predictions["pages"],
    }
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--pdf", type=Path, required=True)
    prepare_parser.add_argument("--corrections", type=Path, required=True)
    prepare_parser.add_argument("--report", type=Path, required=True)
    prepare_parser.add_argument("--output", type=Path, required=True)
    prepare_parser.add_argument("--dpi", type=int, default=300)
    evaluate_parser = subparsers.add_parser("evaluate")
    evaluate_parser.add_argument("--manifest", type=Path, required=True)
    evaluate_parser.add_argument("--predictions", type=Path, required=True)
    evaluate_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(
            args.pdf,
            args.corrections,
            args.report,
            args.output,
            dpi=args.dpi,
        )
        print(f"{len(result['pages'])} pages préparées")
    else:
        result = evaluate(args.manifest, args.predictions, args.output)
        print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
