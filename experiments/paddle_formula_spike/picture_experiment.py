from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import fitz

from experiments.paddle_formula_spike.experiment import assess_prediction, load_json
from experiments.paddle_formula_spike.structure_experiment import (
    formula_predictions,
    insertion_regions,
)


def picture_specs(
    docling: dict[str, Any], insertions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for region in insertions:
        ref = region.get("docling_ref") or ""
        if ref.startswith("#/pictures/"):
            grouped[ref].append(region)

    pictures = {picture["self_ref"]: picture for picture in docling["pictures"]}
    missing = set(grouped) - set(pictures)
    if missing:
        raise ValueError(f"Missing Docling pictures: {', '.join(sorted(missing))}")

    specs = []
    for ref, regions in sorted(grouped.items()):
        provenance = pictures[ref].get("prov", [])
        if len(provenance) != 1:
            raise ValueError(f"Expected one provenance entry for {ref}")
        page = provenance[0]["page_no"]
        if any(region["page"] != page for region in regions):
            raise ValueError(f"Page mismatch for {ref}")
        specs.append(
            {
                "picture_ref": ref,
                "page": page,
                "docling_bbox": provenance[0]["bbox"],
                "regions": regions,
            }
        )
    return specs


def pdf_bbox(
    bbox: dict[str, Any],
    *,
    docling_width: float,
    docling_height: float,
    pdf_width: float,
    pdf_height: float,
) -> list[float]:
    if bbox.get("coord_origin") != "TOPLEFT":
        raise ValueError("Only TOPLEFT Docling picture coordinates are supported")
    scale_x = pdf_width / docling_width
    scale_y = pdf_height / docling_height
    return [
        bbox["l"] * scale_x,
        bbox["t"] * scale_y,
        bbox["r"] * scale_x,
        bbox["b"] * scale_y,
    ]


def relative_bbox(
    source: list[float], crop: list[float], scale_x: float, scale_y: float
) -> list[float]:
    return [
        (source[0] - crop[0]) * scale_x,
        (source[1] - crop[1]) * scale_y,
        (source[2] - crop[0]) * scale_x,
        (source[3] - crop[1]) * scale_y,
    ]


def clamp_bbox(bbox: list[float], width: int, height: int) -> list[float]:
    return [
        min(max(bbox[0], 0.0), width),
        min(max(bbox[1], 0.0), height),
        min(max(bbox[2], 0.0), width),
        min(max(bbox[3], 0.0), height),
    ]


def compact_region(
    region: dict[str, Any], rendered_bbox: list[float]
) -> dict[str, Any]:
    return {
        "region_id": region["region_id"],
        "page": region["page"],
        "bbox": region["bbox"],
        "rendered_bbox": rendered_bbox,
        "source_tokens": region["source_canonical_tokens"],
        "source_signature": region["source_relation_signature"],
    }


def prepare(
    pdf_path: Path,
    docling_path: Path,
    corrections_path: Path,
    report_path: Path,
    output_dir: Path,
    *,
    dpi: int,
) -> dict[str, Any]:
    docling = load_json(docling_path)
    _, insertions, _ = insertion_regions(
        load_json(corrections_path), load_json(report_path)
    )
    specs = picture_specs(docling, insertions)
    pictures_dir = output_dir / "pictures"
    pictures_dir.mkdir(parents=True, exist_ok=True)
    matrix = fitz.Matrix(dpi / 72.0, dpi / 72.0)
    rendered = []

    with fitz.open(pdf_path) as pdf:
        for spec in specs:
            page = pdf[spec["page"] - 1]
            docling_page = docling["pages"][str(spec["page"])]
            size = docling_page["size"]
            crop = pdf_bbox(
                spec["docling_bbox"],
                docling_width=size["width"],
                docling_height=size["height"],
                pdf_width=page.rect.width,
                pdf_height=page.rect.height,
            )
            clip = fitz.Rect(crop) & page.rect
            pixmap = page.get_pixmap(matrix=matrix, clip=clip, alpha=False)
            index = int(spec["picture_ref"].rsplit("/", 1)[1])
            filename = f"picture-{index:03d}-page-{spec['page']:03d}.png"
            pixmap.save(pictures_dir / filename)
            scale_x = pixmap.width / clip.width
            scale_y = pixmap.height / clip.height
            rendered.append(
                {
                    "picture_ref": spec["picture_ref"],
                    "page": spec["page"],
                    "image": f"pictures/{filename}",
                    "pdf_bbox": list(clip),
                    "width": pixmap.width,
                    "height": pixmap.height,
                    "regions": [
                        compact_region(
                            region,
                            clamp_bbox(
                                relative_bbox(
                                    region["bbox"], list(clip), scale_x, scale_y
                                ),
                                pixmap.width,
                                pixmap.height,
                            ),
                        )
                        for region in spec["regions"]
                    ],
                }
            )

    manifest = {
        "corpus": "document-19-qualification-51-docling-pictures",
        "dpi": dpi,
        "pictures": rendered,
        "regions": sum(len(picture["regions"]) for picture in rendered),
    }
    path = output_dir / "picture-manifest.json"
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def contains_center(outer: list[float], inner: list[float]) -> bool:
    center_x = (inner[0] + inner[2]) / 2
    center_y = (inner[1] + inner[3]) / 2
    return outer[0] <= center_x <= outer[2] and outer[1] <= center_y <= outer[3]


def oriented_bbox(
    bbox: list[float], angle: int, width: int, height: int
) -> list[float]:
    x1, y1, x2, y2 = bbox
    if angle in (-1, 0):
        return bbox
    if angle == 90:
        return [y1, width - x2, y2, width - x1]
    if angle == 180:
        return [width - x2, height - y2, width - x1, height - y1]
    if angle == 270:
        return [height - y2, x1, height - y1, x2]
    raise ValueError(f"Unsupported orientation angle: {angle}")


def evaluate(
    manifest_path: Path, predictions_path: Path, output_path: Path
) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    predictions = load_json(predictions_path)
    predicted = {
        item["picture_ref"]: item["result"] for item in predictions["pictures"]
    }
    expected_refs = {item["picture_ref"] for item in manifest["pictures"]}
    if set(predicted) != expected_refs:
        raise ValueError("Picture predictions do not match the manifest")
    results = []
    picture_results = []
    for picture in manifest["pictures"]:
        picture_prediction = predicted[picture["picture_ref"]]
        formulas = formula_predictions(picture_prediction)
        angle = int(picture_prediction.get("doc_preprocessor_res", {}).get("angle", 0))
        detected = 0
        exact = 0
        for region in picture["regions"]:
            analyzed_bbox = oriented_bbox(
                region["rendered_bbox"], angle, picture["width"], picture["height"]
            )
            matches = [
                formula
                for formula in formulas
                if contains_center(formula["bbox"], analyzed_bbox)
            ]
            assessments = [
                assess_prediction(region, formula["latex"] or "") for formula in matches
            ]
            record = {
                **region,
                "picture_ref": picture["picture_ref"],
                "orientation": angle,
                "analyzed_bbox": analyzed_bbox,
                "formula_matches": matches,
                "detected": bool(matches),
                "exact": any(item["paddle_exact"] for item in assessments),
            }
            detected += record["detected"]
            exact += record["exact"]
            results.append(record)
        picture_results.append(
            {
                "picture_ref": picture["picture_ref"],
                "page": picture["page"],
                "orientation": angle,
                "regions": len(picture["regions"]),
                "formula_predictions": len(formulas),
                "detected_regions": detected,
                "exact_regions": exact,
            }
        )

    summary = {
        "pictures": len(picture_results),
        "regions": len(results),
        "formula_predictions": sum(
            item["formula_predictions"] for item in picture_results
        ),
        "detected_regions": sum(item["detected"] for item in results),
        "exact_regions": sum(item["exact"] for item in results),
        "detected_pages": dict(
            Counter(item["page"] for item in results if item["detected"])
        ),
        "model_load_seconds": predictions["model_load_seconds"],
        "inference_seconds": predictions["inference_seconds"],
    }
    result = {"summary": summary, "pictures": picture_results, "regions": results}
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result
