import gzip
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import fitz
import pytest


def test_cli_ecrit_le_rapport_et_publie_la_progression(tmp_path: Path) -> None:
    pdf_path = tmp_path / "unsupported.pdf"
    report_path = tmp_path / "report.json"
    evidence_path = tmp_path / "evidence.ndjson.gz"
    with fitz.open() as document:
        page = document.new_page()
        page.insert_text((72, 72), "test")
        document.save(pdf_path)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pdf_math_audit",
            str(pdf_path),
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
    ]
    assert events[-1] == {
        "type": "result",
        "report_path": str(report_path.resolve()),
        "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
    }
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["pages"][0]["status"] == "unsupported"
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
        ("same-output", "same-output"),
    ],
)
def test_cli_refuse_toute_collision_entre_entree_et_sorties(
    tmp_path: Path, report_name: str, evidence_name: str
) -> None:
    pdf_path = tmp_path / "source.pdf"
    with fitz.open() as document:
        document.new_page()
        document.save(pdf_path)
    original = pdf_path.read_bytes()
    report_path = tmp_path / report_name
    evidence_path = tmp_path / evidence_name

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pdf_math_audit",
            str(pdf_path),
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
    assert pdf_path.read_bytes() == original
    for output in {report_path, evidence_path} - {pdf_path}:
        assert not output.exists()
