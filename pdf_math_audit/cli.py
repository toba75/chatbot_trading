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
from pdf_math_audit.correction import CorrectionConfig, correct_document
from pdf_math_audit.development import (
    DEVELOPMENT_ORIGINS,
    development_origin_counts,
    pdf_supplement_records,
    recipe_from_operations,
    recipe_sha256,
)
from pdf_math_audit.derived_document import derive_document_and_page_html
from pdf_math_audit.html_integrity import audit_page_html


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
    parser.add_argument("--correction-endpoint")
    parser.add_argument("--correction-model")
    parser.add_argument("--correction-dpi", type=int)
    parser.add_argument("--correction-padding-points", type=float)
    parser.add_argument("--correction-timeout-seconds", type=int)
    parser.add_argument("--correction-max-response-bytes", type=int)
    parser.add_argument("--correction-records", type=Path)
    parser.add_argument("--correction-evidence", type=Path)
    parser.add_argument("--derived-docling-document", type=Path)
    parser.add_argument("--derived-html", type=Path)
    parser.add_argument("--derived-markdown", type=Path)
    parser.add_argument("--native-page-html", type=Path)
    parser.add_argument("--correction-checkpoint-records", type=Path)
    parser.add_argument("--correction-checkpoint-evidence", type=Path)
    args = parser.parse_args()
    correction_names = (
        "correction_endpoint",
        "correction_model",
        "correction_dpi",
        "correction_padding_points",
        "correction_timeout_seconds",
        "correction_max_response_bytes",
        "correction_records",
        "correction_evidence",
        "derived_docling_document",
        "derived_html",
        "derived_markdown",
        "native_page_html",
    )
    correction_values = [getattr(args, name) for name in correction_names]
    if any(value is not None for value in correction_values) and not all(
        value is not None for value in correction_values
    ):
        parser.error("la configuration de correction doit être fournie intégralement")
    correction_enabled = all(value is not None for value in correction_values)
    checkpoints = (
        args.correction_checkpoint_records,
        args.correction_checkpoint_evidence,
    )
    if any(path is not None for path in checkpoints) and not all(
        path is not None for path in checkpoints
    ):
        parser.error("les deux chemins de reprise de correction sont requis ensemble")
    if correction_enabled and (
        args.correction_dpi <= 0
        or args.correction_padding_points < 0
        or args.correction_timeout_seconds <= 0
        or args.correction_max_response_bytes <= 0
    ):
        parser.error("les dimensions de correction sont invalides")
    output_paths = {
        "report": args.report,
        "evidence": args.evidence,
    }
    if correction_enabled:
        output_paths.update(
            {
                name.replace("_", "-"): getattr(args, name)
                for name in correction_names[6:]
            }
        )
        if all(path is not None for path in checkpoints):
            output_paths.update(
                {
                    "correction-checkpoint-records": args.correction_checkpoint_records,
                    "correction-checkpoint-evidence": args.correction_checkpoint_evidence,
                }
            )
    _require_distinct_paths(
        parser,
        {
            "pdf": args.pdf,
            "docling-document": args.docling_document,
            **output_paths,
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
    empty_recipe = recipe_from_operations([])
    empty_recipe_sha256 = recipe_sha256(empty_recipe)
    if correction_enabled:
        correction = correct_document(
            args.pdf,
            document,
            report["alignment"]["pdf_source_math_regions"],
            CorrectionConfig(
                endpoint=args.correction_endpoint,
                model=args.correction_model,
                dpi=args.correction_dpi,
                padding_points=args.correction_padding_points,
                timeout_seconds=args.correction_timeout_seconds,
                max_response_bytes=args.correction_max_response_bytes,
            ),
            on_progress=_emit,
            checkpoint_records=args.correction_checkpoint_records,
            checkpoint_evidence=args.correction_checkpoint_evidence,
            native_document_sha256=docling_sha256,
        )
        args.correction_records.write_bytes(correction.records)
        args.correction_evidence.write_bytes(correction.evidence)
        _native_document, native_page_html = derive_document_and_page_html(
            document,
            [],
            args.pdf,
            native_document_sha256=docling_sha256,
            recipe_sha256_value=empty_recipe_sha256,
        )
        args.native_page_html.write_bytes(native_page_html)
        report["native_page_html"] = {
            "bytes": args.native_page_html.stat().st_size,
            "sha256": file_sha256(args.native_page_html),
        }
        report["html_integrity"] = {
            "artifact": "native_page_html",
            **audit_page_html(
                document,
                native_page_html,
                args.pdf,
                report["alignment"]["pdf_source_math_regions"],
            ),
        }
        correction_artifacts = {
            "corrections": args.correction_records,
            "correction_evidence": args.correction_evidence,
        }
        if correction.document is not None:
            args.derived_docling_document.write_bytes(correction.document)
            args.derived_html.write_bytes(correction.html)
            args.derived_markdown.write_bytes(correction.markdown)
            derived_document = DoclingDocument.model_validate_json(correction.document)
            accepted_corrections = [
                record
                for record in json.loads(correction.records)["records"]
                if record["status"] == "accepted"
            ]
            report["html_integrity"] = {
                "artifact": "derived_html",
                **audit_page_html(
                    derived_document,
                    correction.html,
                    args.pdf,
                    report["alignment"]["pdf_source_math_regions"],
                    accepted_corrections,
                ),
            }
            correction_artifacts.update(
                {
                    "derived_docling_document": args.derived_docling_document,
                    "derived_html": args.derived_html,
                    "derived_markdown": args.derived_markdown,
                }
            )
        report["correction"] = correction.summary | {
            "artifacts": {
                name: {
                    "bytes": path.stat().st_size,
                    "sha256": file_sha256(path),
                }
                for name, path in correction_artifacts.items()
            }
        }
        correction_payload = json.loads(correction.records)
        development_recipe = correction_payload["recipe"]
        development_operations = development_recipe["operations"]
        operation_origin_counts = {
            origin: sum(
                operation.get("operation") == origin
                for operation in development_operations
            )
            for origin in DEVELOPMENT_ORIGINS
            if origin != "transcription"
        }
        operation_origin_counts["transcription"] = 0
        report["development"] = {
            "native_document_sha256": docling_sha256,
            "recipe_schema_version": development_recipe["schema_version"],
            "recipe_sha256": recipe_sha256(development_recipe),
            "operations": len(development_operations),
            "origin_counts": development_origin_counts(document, development_operations),
            "operation_origin_counts": operation_origin_counts,
        }
    else:
        report["correction"] = {
            "status": "not_requested",
            "regions": 0,
            "targets": 0,
            "accepted": 0,
            "accepted_regions": 0,
            "rejected": 0,
            "failed": 0,
            "artifacts": {},
        }
        supplements = pdf_supplement_records(
            report["alignment"]["pdf_source_math_regions"]
        )
        supplement_recipe = recipe_from_operations(supplements)
        operation_origin_counts = {
            origin: (len(supplements) if origin == "pdf_supplement" else 0)
            for origin in DEVELOPMENT_ORIGINS
        }
        report["development"] = {
            "native_document_sha256": docling_sha256,
            "recipe_schema_version": supplement_recipe["schema_version"],
            "recipe_sha256": recipe_sha256(supplement_recipe),
            "operations": len(supplements),
            "origin_counts": development_origin_counts(document, supplements),
            "operation_origin_counts": operation_origin_counts,
        }
    report["evidence"] = {
        "bytes": len(evidence_bytes),
        "content_encoding": "gzip",
        "format": "ndjson",
        "glyphs": glyph_count,
        "sha256": hashlib.sha256(evidence_bytes).hexdigest(),
    }
    report_bytes = (
        json.dumps(
            report,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
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
