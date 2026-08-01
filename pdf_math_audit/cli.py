import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from docling_core.types.doc import DoclingDocument

from pdf_math_audit.alignment import DoclingAlignment
from pdf_math_audit.analyzer import analyze_pdf
from pdf_math_audit.contract import (
    ANALYZER_VERSION,
    CAPABILITY_PROFILE,
    CONTRACT_VERSION,
    file_sha256,
    require_fingerprint,
    sha256_argument,
)


def _emit(event: dict[str, Any]) -> None:
    print(json.dumps(event, ensure_ascii=False, separators=(",", ":")), flush=True)


def _require_distinct_paths(
    parser: argparse.ArgumentParser, paths: dict[str, Path]
) -> None:
    entries = list(paths.items())
    for index, (left_name, left) in enumerate(entries):
        for right_name, right in entries[index + 1 :]:
            same_path = left.resolve() == right.resolve()
            same_file = left.exists() and right.exists() and left.samefile(right)
            if same_path or same_file:
                parser.error(f"{left_name} et {right_name} doivent être distincts")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Analyse la traçabilité structurelle d'un PDF."
    )
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--docling-document", type=Path, required=True)
    parser.add_argument("--source-sha256", type=sha256_argument, required=True)
    parser.add_argument(
        "--docling-document-sha256", type=sha256_argument, required=True
    )
    parser.add_argument("--contract-version", choices=[CONTRACT_VERSION], required=True)
    parser.add_argument(
        "--capability-profile", choices=[CAPABILITY_PROFILE], required=True
    )
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    _require_distinct_paths(
        parser,
        {
            "pdf": args.pdf,
            "docling-document": args.docling_document,
            "report": args.report,
            "evidence": args.evidence,
        },
    )

    source_sha256 = file_sha256(args.pdf)
    require_fingerprint(
        parser,
        label="le PDF source",
        actual=source_sha256,
        announced=args.source_sha256,
    )
    docling_bytes = args.docling_document.read_bytes()
    docling_sha256 = hashlib.sha256(docling_bytes).hexdigest()
    require_fingerprint(
        parser,
        label="le DoclingDocument",
        actual=docling_sha256,
        announced=args.docling_document_sha256,
    )
    document = DoclingDocument.model_validate_json(docling_bytes)
    alignment = DoclingAlignment(document)
    glyph_count = 0
    with args.evidence.open("wb") as evidence_file:
        with gzip.GzipFile(
            filename="", fileobj=evidence_file, mode="wb", mtime=0
        ) as evidence:

            def write_evidence(page: int, glyph: dict[str, Any]) -> None:
                nonlocal glyph_count
                alignment.observe_glyph(page, glyph)
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
    report["docling_document"] = {
        "filename": args.docling_document.name,
        "bytes": len(docling_bytes),
        "sha256": docling_sha256,
        "schema_name": document.schema_name,
        "version": document.version,
    }
    report["contract"] = {
        "version": args.contract_version,
        "analyzer_version": ANALYZER_VERSION,
        "capability_profile": args.capability_profile,
        "source_sha256": source_sha256,
        "docling_document_sha256": docling_sha256,
    }
    report["alignment"] = alignment.finalize(report, on_progress=_emit)
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


if __name__ == "__main__":
    raise SystemExit(main())
