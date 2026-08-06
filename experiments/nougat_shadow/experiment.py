from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import fitz

from experiments.nougat_shadow.artifacts import read_json_bytes, sha256
from experiments.nougat_shadow.evaluation import evaluate


def shadow_targets(
    corrections: dict[str, Any], report: dict[str, Any]
) -> list[dict[str, Any]]:
    source_regions = {
        region["region_id"]: region
        for region in report["alignment"]["pdf_source_math_regions"]
    }
    targets = []
    for record in corrections["records"]:
        if record["kind"] == "formula_insertion":
            continue
        proposals = record.get("proposals", [])
        if not any("vision_proposal" in proposal for proposal in proposals):
            continue
        proofs = []
        for proof in record["source_proofs"]:
            region = source_regions[proof["region_id"]]
            proofs.append(
                {
                    "region_id": proof["region_id"],
                    "bbox": region["bbox"],
                    "candidate_charspan": proof["candidate_charspan"],
                    "candidate_text": proof["candidate_text"],
                    "tokens": proof["tokens"],
                    "signature": proof["signature"],
                }
            )
        targets.append(
            {
                "target_id": record["target_id"],
                "kind": record["kind"],
                "page": record["page"],
                "before": record["before"],
                "candidate_format": source_regions[record["region_id"]].get(
                    "candidate_format"
                ),
                "baseline_status": record["status"],
                "baseline_reason": record.get("reason"),
                "proofs": proofs,
            }
        )
    return targets


def _load_inputs(
    pdf_path: Path, corrections_path: Path, report_path: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    pdf_content = pdf_path.read_bytes()
    corrections_content = read_json_bytes(corrections_path)
    report_content = read_json_bytes(report_path)
    corrections = json.loads(corrections_content)
    report = json.loads(report_content)
    pdf_sha256 = sha256(pdf_content)
    if not (
        pdf_sha256 == report["pdf"]["sha256"] == report["contract"]["source_sha256"]
    ):
        raise ValueError("le PDF ne correspond pas aux preuves du rapport")
    corrections_identity = report["correction"]["artifacts"]["corrections"]
    if not (
        len(corrections_content) == corrections_identity["bytes"]
        and sha256(corrections_content) == corrections_identity["sha256"]
    ):
        raise ValueError("les corrections ne correspondent pas au rapport")
    fingerprints = {
        "pdf_sha256": pdf_sha256,
        "corrections_sha256": sha256(corrections_content),
        "report_sha256": sha256(report_content),
    }
    return corrections, report, fingerprints


def prepare(
    pdf_path: Path,
    corrections_path: Path,
    report_path: Path,
    output_dir: Path,
    *,
    dpi: int,
) -> dict[str, Any]:
    corrections, report, fingerprints = _load_inputs(
        pdf_path, corrections_path, report_path
    )
    targets = shadow_targets(corrections, report)
    page_numbers = sorted({target["page"] for target in targets})
    pages_dir = output_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    pages = []
    with fitz.open(pdf_path) as document:
        for page_number in page_numbers:
            image = (
                document[page_number - 1]
                .get_pixmap(dpi=dpi, alpha=False)
                .tobytes("png")
            )
            relative_path = Path("pages") / f"page-{page_number:03d}.png"
            (output_dir / relative_path).write_bytes(image)
            pages.append(
                {
                    "page": page_number,
                    "image": relative_path.as_posix(),
                    "image_sha256": sha256(image),
                }
            )
    manifest = {
        "mode": "shadow",
        "dpi": dpi,
        **fingerprints,
        "targets": targets,
        "pages": pages,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--pdf", type=Path, required=True)
    prepare_parser.add_argument("--corrections", type=Path, required=True)
    prepare_parser.add_argument("--report", type=Path, required=True)
    prepare_parser.add_argument("--output", type=Path, required=True)
    prepare_parser.add_argument("--dpi", type=int, default=200)
    evaluate_parser = commands.add_parser("evaluate")
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
        summary = {"pages": len(result["pages"]), "targets": len(result["targets"])}
    else:
        result = evaluate(args.manifest, args.predictions, args.output)
        summary = result["summary"]
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
