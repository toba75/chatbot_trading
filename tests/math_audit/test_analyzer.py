import hashlib
from pathlib import Path

import fitz

from pdf_math_audit.analyzer import analyze_pdf


REFERENCE_PDF = (
    Path(__file__).parents[2]
    / "experiments"
    / "math_pipeline_comparison"
    / "source-pages-7-10.pdf"
)


def test_analyse_generiquement_la_trace_structurelle_du_pdf_de_reference() -> None:
    progress = []
    evidence = []

    report = analyze_pdf(
        REFERENCE_PDF,
        on_progress=progress.append,
        on_evidence=lambda page, glyph: evidence.append((page, glyph)),
    )

    assert report["schema_version"] == "1.0"
    assert report["analyzer_version"] == "0.4.0"
    assert report["capability_profile"] == "type1-cff-v1"
    assert report["pdf"] == {
        "filename": REFERENCE_PDF.name,
        "bytes": REFERENCE_PDF.stat().st_size,
        "sha256": hashlib.sha256(REFERENCE_PDF.read_bytes()).hexdigest(),
        "pages": 2,
    }
    assert [page["status"] for page in report["pages"]] == ["traced", "traced"]
    assert report["coverage"]["pages_traced"] == 2
    assert report["coverage"]["pages_unsupported"] == 0
    assert report["coverage"]["source_codes"] == 4_088
    assert report["coverage"]["gid_matches"] == 4_088
    assert report["coverage"]["rawdict_assignments"] == 4_088
    assert (
        sum(conflict["occurrences"] for conflict in report["to_unicode_conflicts"])
        == 21
    )
    assert all("glyphs" not in page for page in report["pages"])
    assert len(evidence) == 4_088
    assert {page for page, _glyph in evidence} == {1, 2}
    assert all("rendered" in glyph and "rawdict" in glyph for _page, glyph in evidence)
    assert "proofs" not in report
    assert progress == [
        {
            "type": "progress",
            "phase": "source_analysis",
            "completed_units": 0,
            "total_units": 2,
        },
        {
            "type": "progress",
            "phase": "source_analysis",
            "completed_units": 1,
            "total_units": 2,
        },
        {
            "type": "progress",
            "phase": "source_analysis",
            "completed_units": 2,
            "total_units": 2,
        },
    ]


def test_signale_une_capacite_absente_sans_moteur_alternatif(tmp_path: Path) -> None:
    pdf_path = tmp_path / "font-not-embedded.pdf"
    with fitz.open() as document:
        page = document.new_page()
        page.insert_text((72, 72), "x + 1")
        document.save(pdf_path)

    report = analyze_pdf(pdf_path)

    assert report["coverage"]["pages_traced"] == 0
    assert report["coverage"]["pages_unsupported"] == 1
    assert report["pages"][0]["status"] == "unsupported"
    assert report["pages"][0]["fonts"] == {}
    assert report["pages"][0]["reasons"] == [
        {
            "code": "embedded_type1c_font_required",
            "message": "/helv: FontDescriptor absent",
        }
    ]
    assert "glyphs" not in report["pages"][0]


def test_une_page_vide_est_tracee_sans_inventer_de_glyphe(tmp_path: Path) -> None:
    pdf_path = tmp_path / "blank.pdf"
    with fitz.open() as document:
        document.new_page()
        document.save(pdf_path)

    report = analyze_pdf(pdf_path)

    assert report["pages"][0]["status"] == "traced"
    assert "glyphs" not in report["pages"][0]
    assert report["coverage"]["source_codes"] == 0
