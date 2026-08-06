import gzip
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import fitz
import pytest
from docling_core.types.doc import DoclingDocument, PageItem, Size


def _write_docling_document(path: Path, width: float, height: float) -> bytes:
    content = (
        DoclingDocument(
            name="cli-test",
            pages={
                1: PageItem(page_no=1, size=Size(width=width, height=height)),
            },
        )
        .model_dump_json()
        .encode()
    )
    path.write_bytes(content)
    return content


def _contract_arguments(pdf_path: Path, docling_bytes: bytes) -> list[str]:
    return [
        "--source-sha256",
        hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
        "--docling-document-sha256",
        hashlib.sha256(docling_bytes).hexdigest(),
        "--contract-version",
        "2.1",
        "--capability-profile",
        "pdf-docling-semantic-correction-v3",
    ]


def test_cli_ecrit_le_rapport_et_publie_la_progression(tmp_path: Path) -> None:
    pdf_path = tmp_path / "unsupported.pdf"
    docling_path = tmp_path / "docling.json"
    report_path = tmp_path / "report.json"
    evidence_path = tmp_path / "evidence.ndjson.gz"
    with fitz.open() as document:
        page = document.new_page()
        page.insert_text((72, 72), "test")
        page_size = (page.rect.width, page.rect.height)
        document.save(pdf_path)
    docling_bytes = _write_docling_document(docling_path, *page_size)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pdf_math_audit",
            str(pdf_path),
            "--docling-document",
            str(docling_path),
            *_contract_arguments(pdf_path, docling_bytes),
            "--report",
            str(report_path),
            "--evidence",
            str(evidence_path),
        ],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )

    events = [json.loads(line) for line in completed.stdout.splitlines()]
    assert events[:-1] == [
        {
            "type": "progress",
            "phase": "source_analysis",
            "completed_units": 0,
            "total_units": 1,
        },
        {
            "type": "progress",
            "phase": "source_analysis",
            "completed_units": 1,
            "total_units": 1,
        },
        {
            "type": "progress",
            "phase": "docling_alignment",
            "completed_units": 0,
            "total_units": 0,
        },
        {
            "type": "progress",
            "phase": "candidate_evaluation",
            "completed_units": 0,
            "total_units": 0,
        },
    ]
    assert events[-1] == {
        "type": "result",
        "report_path": str(report_path.resolve()),
        "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
    }
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report_path.read_bytes().count(b"\n") == 1
    assert report["pages"][0]["status"] == "unsupported"
    assert report["docling_document"] == {
        "filename": "docling.json",
        "bytes": len(docling_bytes),
        "sha256": hashlib.sha256(docling_bytes).hexdigest(),
        "schema_name": "DoclingDocument",
        "version": "1.10.0",
    }
    assert report["contract"] == {
        "version": "2.1",
        "analyzer_version": "0.8.0",
        "capability_profile": "pdf-docling-semantic-correction-v3",
        "source_sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
        "docling_document_sha256": hashlib.sha256(docling_bytes).hexdigest(),
    }
    assert report["alignment"]["coverage"]["regions_total"] == 0
    assert report["evidence"] == {
        "bytes": evidence_path.stat().st_size,
        "content_encoding": "gzip",
        "format": "ndjson",
        "glyphs": 0,
        "sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
    }
    with gzip.open(evidence_path, "rt", encoding="utf-8") as evidence:
        assert evidence.read() == ""


@pytest.mark.parametrize(
    ("report_name", "evidence_name"),
    [
        ("source.pdf", "evidence.ndjson.gz"),
        ("report.json", "source.pdf"),
        ("docling.json", "evidence.ndjson.gz"),
        ("report.json", "docling.json"),
        ("same-output", "same-output"),
    ],
)
def test_cli_refuse_toute_collision_entre_entree_et_sorties(
    tmp_path: Path, report_name: str, evidence_name: str
) -> None:
    pdf_path = tmp_path / "source.pdf"
    docling_path = tmp_path / "docling.json"
    with fitz.open() as document:
        document.new_page()
        document.save(pdf_path)
    docling_bytes = _write_docling_document(docling_path, 595, 842)
    original_pdf = pdf_path.read_bytes()
    original_docling = docling_path.read_bytes()
    report_path = tmp_path / report_name
    evidence_path = tmp_path / evidence_name

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pdf_math_audit",
            str(pdf_path),
            "--docling-document",
            str(docling_path),
            *_contract_arguments(pdf_path, docling_bytes),
            "--report",
            str(report_path),
            "--evidence",
            str(evidence_path),
        ],
        check=False,
        capture_output=True,
        encoding="utf-8",
    )

    assert completed.returncode == 2
    assert pdf_path.read_bytes() == original_pdf
    assert docling_path.read_bytes() == original_docling
    for output in {report_path, evidence_path} - {pdf_path, docling_path}:
        assert not output.exists()


@pytest.mark.parametrize("mismatched_input", ["source", "docling"])
def test_cli_refuse_une_empreinte_annoncee_incorrecte(
    tmp_path: Path, mismatched_input: str
) -> None:
    pdf_path = tmp_path / "source.pdf"
    docling_path = tmp_path / "docling.json"
    report_path = tmp_path / "report.json"
    evidence_path = tmp_path / "evidence.ndjson.gz"
    with fitz.open() as document:
        document.new_page()
        document.save(pdf_path)
    docling_bytes = _write_docling_document(docling_path, 595, 842)
    arguments = _contract_arguments(pdf_path, docling_bytes)
    hash_index = 1 if mismatched_input == "source" else 3
    arguments[hash_index] = "0" * 64

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pdf_math_audit",
            str(pdf_path),
            "--docling-document",
            str(docling_path),
            *arguments,
            "--report",
            str(report_path),
            "--evidence",
            str(evidence_path),
        ],
        check=False,
        capture_output=True,
        encoding="utf-8",
    )

    assert completed.returncode == 2
    assert "empreinte" in completed.stderr
    assert not report_path.exists()
    assert not evidence_path.exists()
