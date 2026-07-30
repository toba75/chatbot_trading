import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from pdf_math_audit.analyzer import analyze_pdf


def _emit(event: dict[str, Any]) -> None:
    print(json.dumps(event, ensure_ascii=False, separators=(",", ":")), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyse la traçabilité structurelle d'un PDF."
    )
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    glyph_count = 0
    with args.evidence.open("wb") as evidence_file:
        with gzip.GzipFile(
            filename="", fileobj=evidence_file, mode="wb", mtime=0
        ) as evidence:

            def write_evidence(page: int, glyph: dict[str, Any]) -> None:
                nonlocal glyph_count
                record = {"page": page, **glyph}
                evidence.write(
                    (
                        json.dumps(
                            record,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                        + "\n"
                    ).encode("utf-8")
                )
                glyph_count += 1

            report = analyze_pdf(
                args.pdf,
                on_progress=_emit,
                on_evidence=write_evidence,
            )

    evidence_bytes = args.evidence.read_bytes()
    report["evidence"] = {
        "bytes": len(evidence_bytes),
        "content_encoding": "gzip",
        "format": "ndjson",
        "glyphs": glyph_count,
        "sha256": hashlib.sha256(evidence_bytes).hexdigest(),
    }
    report_bytes = (
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()
    args.report.write_bytes(report_bytes)
    _emit(
        {
            "type": "result",
            "report_path": str(args.report.resolve()),
            "report_sha256": hashlib.sha256(report_bytes).hexdigest(),
        }
    )
    return 0
