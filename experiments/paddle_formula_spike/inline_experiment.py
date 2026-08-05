from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import fitz

from experiments.paddle_formula_spike.experiment import (
    assess_prediction,
    load_json,
)
from experiments.paddle_formula_spike.inline_html_audit import audit_html
from pdf_math_audit.correction_application import (
    candidate_scope_reason,
    apply_target,
)
from pdf_math_audit.correction_targets import render_crop
from pdf_math_audit.source_latex import proven_source_latex


def local_records(
    corrections: dict[str, Any], report: dict[str, Any]
) -> list[dict[str, Any]]:
    source_regions = {
        region["region_id"]: region
        for region in report["alignment"]["pdf_source_math_regions"]
    }
    records = []
    for correction in corrections["records"]:
        if correction["kind"] != "replacement" or correction["status"] == "accepted":
            continue
        region = source_regions[correction["region_id"]]
        records.append(
            {
                "region_id": region["region_id"],
                "target_id": correction["target_id"],
                "page": region["page"],
                "bbox": region["bbox"],
                "candidate_text": region["candidate_text"],
                "candidate_format": region["candidate_format"],
                "source_tokens": region["source_canonical_tokens"],
                "source_signature": region["source_relation_signature"],
                "q51_reason": correction.get("reason"),
                "source_region": region,
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
    records = local_records(load_json(corrections_path), load_json(report_path))
    crops_dir = output_dir / "inline-crops"
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
            record["image"] = f"inline-crops/{filename}"
            record["rendered_bbox"] = rendered_bbox
    manifest = {
        "corpus": "document-19-qualification-51-rejected-local-replacements",
        "dpi": dpi,
        "padding_points": 0.0,
        "regions": len(records),
        "records": records,
    }
    (output_dir / "inline-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def _assess_application(record: dict[str, Any], latex: str) -> dict[str, Any]:
    prediction = assess_prediction(record, latex)
    target = {
        "target_id": record["target_id"],
        "kind": "replacement",
        "candidate_text": record["candidate_text"],
        "candidate_format": record["candidate_format"],
        "regions": [record["source_region"]],
    }
    reason = candidate_scope_reason(target)
    if reason is not None or not prediction["paddle_exact"]:
        return prediction | {"applicable": False, "reason": reason or "region_not_exact"}
    try:
        after, mathml = apply_target(target, [latex])
    except ValueError as error:
        return prediction | {"applicable": False, "reason": str(error)}
    return prediction | {"applicable": True, "after": after, "mathml": mathml}


def evaluate(
    manifest_path: Path, predictions_path: Path, output_path: Path
) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    predictions = load_json(predictions_path)
    predicted = {item["region_id"]: item for item in predictions["results"]}
    records = [
        _assess_application(record, predicted[record["region_id"]]["rec_formula"])
        for record in manifest["records"]
    ]
    reasons: dict[str, int] = defaultdict(int)
    for record in records:
        if not record["applicable"]:
            reasons[record["reason"]] += 1
    result = {
        "summary": {
            "model": predictions["model"],
            "device": predictions["device"],
            "regions": len(records),
            "exact": sum(record["paddle_exact"] for record in records),
            "applicable": sum(record["applicable"] for record in records),
            "rejections": dict(sorted(reasons.items())),
            "model_load_seconds": predictions["model_load_seconds"],
            "inference_seconds": predictions["inference_seconds"],
        },
        "records": records,
    }
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def evaluate_source(manifest_path: Path, output_path: Path) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    records = []
    reasons: dict[str, int] = defaultdict(int)
    for record in manifest["records"]:
        latex, reason = proven_source_latex(record["source_region"])
        if latex is None:
            assessed = record | {"applicable": False, "reason": reason}
        else:
            assessed = _assess_application(record, latex)
        records.append(assessed)
        if not assessed["applicable"]:
            reasons[assessed["reason"]] += 1
    result = {
        "summary": {
            "engine": "deterministic_source",
            "regions": len(records),
            "applicable": sum(record["applicable"] for record in records),
            "rejections": dict(sorted(reasons.items())),
        },
        "records": records,
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
    source_parser = subparsers.add_parser("evaluate-source")
    source_parser.add_argument("--manifest", type=Path, required=True)
    source_parser.add_argument("--output", type=Path, required=True)
    audit_parser = subparsers.add_parser("audit-html")
    audit_parser.add_argument("--corrections", type=Path, required=True)
    audit_parser.add_argument("--document", type=Path, required=True)
    audit_parser.add_argument("--source-results", type=Path)
    audit_parser.add_argument("--html", type=Path)
    audit_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.pdf, args.corrections, args.report, args.output, dpi=args.dpi)
        display = {
            "corpus": result["corpus"],
            "dpi": result["dpi"],
            "regions": result["regions"],
        }
    elif args.command == "evaluate":
        result = evaluate(args.manifest, args.predictions, args.output)
        display = result["summary"]
    elif args.command == "evaluate-source":
        result = evaluate_source(args.manifest, args.output)
        display = result["summary"]
    else:
        result = audit_html(
            args.corrections,
            args.document,
            args.output,
            source_results_path=args.source_results,
            html_path=args.html,
        )
        display = result
    print(json.dumps(display, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
