from __future__ import annotations

import argparse
import gzip
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import fitz

from pdf_math_audit.correction_targets import render_crop
from pdf_math_audit.correction_application import apply_target
from pdf_math_audit.mathml_candidate import candidate_analysis


def load_json(path: Path) -> dict[str, Any]:
    opener = gzip.open if path.suffix == ".gz" else Path.open
    with opener(path, "rt", encoding="utf-8") as source:
        return json.load(source)


def replacement_regions(
    corrections: dict[str, Any], report: dict[str, Any]
) -> list[dict[str, Any]]:
    source_regions = {
        region["region_id"]: region
        for region in report["alignment"]["pdf_source_math_regions"]
    }
    records = []
    for target in corrections["records"]:
        if target["kind"] != "formula_replacement":
            continue
        proposals = target.get("proposals", [])
        for index, proof in enumerate(target["source_proofs"]):
            region = source_regions[proof["region_id"]]
            previous = proposals[index] if index < len(proposals) else {}
            records.append(
                {
                    "region_id": proof["region_id"],
                    "target_id": target["target_id"],
                    "page": region["page"],
                    "bbox": region["bbox"],
                    "target_before": target["before"],
                    "candidate_charspan": proof["candidate_charspan"],
                    "candidate_text": proof["candidate_text"],
                    "source_tokens": proof["tokens"],
                    "source_signature": proof["signature"],
                    "gemma_latex": previous.get("vision_proposal"),
                    "gemma_exact": previous.get("vision_confirmation") == "exact",
                }
            )
    return records


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
    records = replacement_regions(corrections, report)
    crops_dir = output_dir / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)

    with fitz.open(pdf_path) as document:
        for record in records:
            image, rendered_bbox = render_crop(
                document[record["page"] - 1],
                record["bbox"],
                padding_points=0.0,
                dpi=dpi,
            )
            filename = record["region_id"].replace(":", "_") + ".png"
            (crops_dir / filename).write_bytes(image)
            record["image"] = f"crops/{filename}"
            record["rendered_bbox"] = rendered_bbox

    manifest = {
        "corpus": "document-19-qualification-51-formula-replacements",
        "dpi": dpi,
        "padding_points": 0.0,
        "targets": len({record["target_id"] for record in records}),
        "regions": len(records),
        "records": records,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def assess_prediction(record: dict[str, Any], latex: str) -> dict[str, Any]:
    tokens, signature, rejection = candidate_analysis(latex)
    exact = (
        rejection is None
        and tokens == record["source_tokens"]
        and signature == record["source_signature"]
    )
    return {
        **record,
        "paddle_latex": latex,
        "paddle_tokens": tokens,
        "paddle_signature": signature,
        "paddle_parse_rejection": rejection,
        "paddle_exact": exact,
    }


def assess_target(regions: list[dict[str, Any]]) -> dict[str, Any]:
    if not all(region["paddle_exact"] for region in regions):
        return {"applicable": False, "reason": "region_not_exact"}
    target = {
        "target_id": regions[0]["target_id"],
        "kind": "formula_replacement",
        "candidate_text": regions[0]["target_before"],
        "regions": [
            {
                "candidate_charspan": region["candidate_charspan"],
                "candidate_text": region["candidate_text"],
                "source_canonical_tokens": region["source_tokens"],
                "source_relation_signature": region["source_signature"],
            }
            for region in regions
        ],
    }
    try:
        after, mathml = apply_target(
            target, [region["paddle_latex"] for region in regions]
        )
    except ValueError as error:
        return {"applicable": False, "reason": str(error)}
    return {"applicable": True, "after": after, "mathml": mathml}


def evaluate(
    manifest_path: Path, predictions_path: Path, output_path: Path
) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    predictions = load_json(predictions_path)
    predicted_by_region = {
        prediction["region_id"]: prediction for prediction in predictions["results"]
    }
    assessed = []
    by_target: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in manifest["records"]:
        prediction = predicted_by_region[record["region_id"]]
        result = assess_prediction(record, prediction["rec_formula"])
        assessed.append(result)
        by_target[result["target_id"]].append(result)

    target_results = {
        target_id: assess_target(regions) for target_id, regions in by_target.items()
    }
    gemma_attempts = [record for record in assessed if record["gemma_latex"] is not None]
    target_exact = sum(all(region["paddle_exact"] for region in regions) for regions in by_target.values())
    summary = {
        "model": predictions["model"],
        "device": predictions["device"],
        "regions": len(assessed),
        "paddle_exact_regions": sum(record["paddle_exact"] for record in assessed),
        "gemma_attempted_regions": sum(
            record["gemma_latex"] is not None for record in assessed
        ),
        "gemma_exact_regions": sum(record["gemma_exact"] for record in assessed),
        "paddle_exact_on_gemma_attempts": sum(
            record["paddle_exact"] for record in gemma_attempts
        ),
        "paddle_only_exact_on_gemma_attempts": sum(
            record["paddle_exact"] and not record["gemma_exact"]
            for record in gemma_attempts
        ),
        "gemma_only_exact_on_gemma_attempts": sum(
            record["gemma_exact"] and not record["paddle_exact"]
            for record in gemma_attempts
        ),
        "targets": len(by_target),
        "paddle_exact_targets": target_exact,
        "paddle_applicable_targets": sum(
            result["applicable"] for result in target_results.values()
        ),
        "model_load_seconds": predictions["model_load_seconds"],
        "inference_seconds": predictions["inference_seconds"],
    }
    result = {
        "summary": summary,
        "targets": target_results,
        "records": assessed,
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
    prepare_parser.add_argument("--dpi", type=int, default=600)

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
        print(f"{result['regions']} régions préparées dans {args.output}")
    else:
        result = evaluate(args.manifest, args.predictions, args.output)
        print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
