from __future__ import annotations

import hashlib
import json
import platform
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Any, Callable

import fitz
import fontTools
import pypdf
from pypdf import PdfReader

from pdf_math_audit.contract import ANALYZER_VERSION
from pdf_math_audit.events import ProgressCallback, progress_event
from pdf_math_audit.fonts import codepoints
from pdf_math_audit.limitations import (
    AnalysisLimitation,
    require_supported,
    require_unambiguous,
)
from pdf_math_audit.trace import PageTrace, number_list, trace_page


EvidenceCallback = Callable[[int, dict[str, Any]], None]
COVERAGE_KEYS = (
    "source_codes",
    "encoding_named",
    "cff_charstrings",
    "agl_mapped",
    "trace_glyphs",
    "gid_matches",
    "rawdict_assignments",
    "trace_unicode_matches",
    "trace_unicode_mismatches",
    "to_unicode_present",
    "to_unicode_matches",
    "to_unicode_conflicts",
    "to_unicode_absent",
)


def _trace_report(page_number: int, trace: PageTrace) -> dict[str, Any]:
    conflicts: dict[tuple[str, int, str, str], dict[str, Any]] = {}
    to_unicode_present = 0
    to_unicode_matches = 0
    for glyph in trace.glyphs:
        font = trace.fonts[glyph["font_resource"]]
        declared = font.to_unicode.get(glyph["code"])
        glyph["to_unicode"] = declared
        glyph["to_unicode_codepoints"] = codepoints(declared)
        if declared is None:
            continue
        to_unicode_present += 1
        if declared == glyph["agl_unicode"]:
            to_unicode_matches += 1
            continue
        key = (glyph["font_resource"], glyph["code"], declared, glyph["agl_unicode"])
        conflict = conflicts.setdefault(
            key,
            {
                "page": page_number,
                "font_resource": glyph["font_resource"],
                "code": glyph["code"],
                "code_hex": glyph["code_hex"],
                "glyph_name": glyph["glyph_name"],
                "to_unicode": declared,
                "to_unicode_codepoints": codepoints(declared),
                "agl_unicode": glyph["agl_unicode"],
                "agl_codepoints": glyph["agl_codepoints"],
                "occurrences": 0,
                "operation_indices": [],
            },
        )
        conflict["occurrences"] += 1
        if glyph["operation_index"] not in conflict["operation_indices"]:
            conflict["operation_indices"].append(glyph["operation_index"])

    total = len(trace.glyphs)
    coverage = {
        "source_codes": total,
        "encoding_named": total,
        "cff_charstrings": total,
        "agl_mapped": total,
        "trace_glyphs": trace.layout["trace_characters"],
        "gid_matches": total,
        "rawdict_assignments": total,
        "trace_unicode_matches": trace.layout["trace_unicode_matches"],
        "trace_unicode_mismatches": trace.layout["trace_unicode_mismatches"],
        "to_unicode_present": to_unicode_present,
        "to_unicode_matches": to_unicode_matches,
        "to_unicode_conflicts": to_unicode_present - to_unicode_matches,
        "to_unicode_absent": total - to_unicode_present,
    }
    sequence = [
        [
            glyph["font_resource"],
            glyph["code"],
            glyph["glyph_name"],
            glyph["cff_gid"],
            glyph["rendered"]["gid"],
            glyph["rendered"]["origin"],
            glyph["rawdict"]["block"],
            glyph["rawdict"]["line"],
        ]
        for glyph in trace.glyphs
    ]
    return {
        "status": "traced",
        "coverage": coverage,
        "sequence_sha256": hashlib.sha256(
            json.dumps(sequence, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest(),
        "layout": trace.layout,
        "operation_counts": [
            {"operator": operator, "count": count}
            for operator, count in sorted(trace.operation_counts.items())
        ],
        "font_usage": dict(
            sorted(Counter(glyph["font_resource"] for glyph in trace.glyphs).items())
        ),
        "fonts": {name: font.public for name, font in trace.fonts.items()},
        "to_unicode_conflicts": list(conflicts.values()),
        "glyphs": trace.glyphs,
    }


def _page_report(
    page_number: int,
    source_page: Any,
    rendered_page: fitz.Page,
    reader: PdfReader,
) -> dict[str, Any]:
    base = {
        "page": page_number,
        "box": number_list(rendered_page.rect),
        "rotation": rendered_page.rotation,
        "fonts": {},
    }
    try:
        require_supported(
            rendered_page.rotation == 0,
            "page_rotation_unsupported",
            f"Page {page_number}: rotation non supportée",
        )
        return base | _trace_report(
            page_number, trace_page(source_page, rendered_page, reader)
        )
    except AnalysisLimitation as limitation:
        return base | {"status": limitation.status, "reasons": [limitation.as_dict()]}


def analyze_pdf(
    pdf_path: Path,
    on_progress: ProgressCallback | None = None,
    on_evidence: EvidenceCallback | None = None,
) -> dict[str, Any]:
    path = Path(pdf_path).resolve()
    source_bytes = path.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    with fitz.open(stream=source_bytes, filetype="pdf") as rendered_document:
        reader = PdfReader(BytesIO(source_bytes))
        total_pages = len(reader.pages)
        require_unambiguous(
            len(rendered_document) == total_pages,
            "pdf_page_count_mismatch",
            f"pypdf={total_pages}, MuPDF={len(rendered_document)}",
        )
        if on_progress:
            on_progress(progress_event("source_analysis", 0, total_pages))
        pages = []
        for index, source_page in enumerate(reader.pages):
            page = _page_report(
                index + 1, source_page, rendered_document.load_page(index), reader
            )
            for glyph in page.pop("glyphs", []):
                if on_evidence:
                    on_evidence(page["page"], glyph)
            pages.append(page)
            if on_progress:
                on_progress(progress_event("source_analysis", index + 1, total_pages))

    traced_pages = [page for page in pages if page["status"] == "traced"]
    conflicts = [
        conflict for page in traced_pages for conflict in page["to_unicode_conflicts"]
    ]
    coverage = {
        "pages_total": len(pages),
        "pages_traced": len(traced_pages),
        "pages_unsupported": sum(page["status"] == "unsupported" for page in pages),
        "pages_ambiguous": sum(page["status"] == "ambiguous" for page in pages),
    }
    coverage.update(
        {
            key: sum(page["coverage"][key] for page in traced_pages)
            for key in COVERAGE_KEYS
        }
    )
    return {
        "schema_version": "1.0",
        "analyzer_version": ANALYZER_VERSION,
        "capability_profile": "type1-cff-v1",
        "status": "completed",
        "runtime": {
            "python": platform.python_version(),
            "pymupdf": fitz.version[0],
            "pypdf": pypdf.__version__,
            "fonttools": fontTools.__version__,
        },
        "pdf": {
            "filename": path.name,
            "bytes": len(source_bytes),
            "sha256": source_sha256,
            "pages": len(pages),
        },
        "coverage": coverage,
        "pages": pages,
        "to_unicode_conflicts": conflicts,
    }
