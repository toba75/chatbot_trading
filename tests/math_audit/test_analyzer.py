import hashlib
from pathlib import Path

import fitz
from pypdf import PdfReader, PdfWriter

from pdf_math_audit.analyzer import analyze_pdf
from pdf_math_audit.fonts import agl_unicode
from pdf_math_audit.pdf_indicators import glyph_reference
from pdf_math_audit.source_math_regions import source_math_regions


REFERENCE_PDF = (
    Path(__file__).parents[2]
    / "experiments"
    / "math_pipeline_comparison"
    / "source-pages-7-10.pdf"
)
FULL_REFERENCE_PDF = (
    Path(__file__).parents[2]
    / "experiments"
    / "math_pipeline_comparison"
    / "source-full.pdf"
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
    assert report["analyzer_version"] == "0.6.2"
    assert report["capability_profile"] == (
        "type1c-winansi-type0-truetype-scaled-page-v4"
    )
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


def test_complete_agl_pour_les_symboles_tex_du_pdf_de_reference() -> None:
    assert agl_unicode("bardbl") == "‖"
    assert agl_unicode("element") == "∈"
    assert agl_unicode("minus") == "−"
    assert agl_unicode("productdisplay") == "∏"
    assert agl_unicode("producttext") == "∏"
    assert agl_unicode("radicalBig") == "√"
    assert agl_unicode("summationdisplay") == "∑"
    assert agl_unicode("summationtext") == "∑"


def test_complete_agl_pour_les_symboles_tex_standards_du_livre() -> None:
    expected = {
        "braceleftBigg": "{",
        "bracketleftBig": "[",
        "bracketleftbig": "[",
        "bracketleftbigg": "[",
        "bracketrightBig": "]",
        "bracketrightbig": "]",
        "bracketrightbigg": "]",
        "epsilon1": "ϵ",
        "integraldisplay": "∫",
        "integraltext": "∫",
        "latticetop": "⊤",
        "lessmuch": "≪",
        "mapsto": "↦",
        "parenleftBig": "(",
        "parenleftBigg": "(",
        "parenleftbig": "(",
        "parenleftbigg": "(",
        "parenrightBig": ")",
        "parenrightBigg": ")",
        "parenrightbig": ")",
        "parenrightbigg": ")",
        "prime": "′",
        "radicalbig": "√",
        "radicalbigg": "√",
        "radicalbt": "√",
        "radicaltp": "√",
        "radicalvertex": "√",
    }

    assert {name: agl_unicode(name) for name in expected} == expected


def test_trace_les_glyphes_tex_de_la_page_41(tmp_path: Path) -> None:
    reader = PdfReader(FULL_REFERENCE_PDF)
    writer = PdfWriter()
    writer.add_page(reader.pages[40])
    pdf_path = tmp_path / "page-41.pdf"
    with pdf_path.open("wb") as destination:
        writer.write(destination)

    evidence = []
    report = analyze_pdf(
        pdf_path,
        on_evidence=lambda page, glyph: evidence.append(glyph_reference(page, glyph)),
    )

    assert report["pages"][0]["status"] == "traced"
    assert len(evidence) == 2_199
    assert any(glyph["glyph_name"] == "prime" for glyph in evidence)
    assert all(glyph["cff_gid"] == glyph["rendered_gid"] for glyph in evidence)


def test_lit_le_gid_de_la_cmap_truetype_symbolique_de_la_page_5(
    tmp_path: Path,
) -> None:
    reader = PdfReader(FULL_REFERENCE_PDF)
    writer = PdfWriter()
    writer.add_page(reader.pages[4])
    pdf_path = tmp_path / "page-5.pdf"
    with pdf_path.open("wb") as destination:
        writer.write(destination)
    evidence = []

    report = analyze_pdf(
        pdf_path,
        on_evidence=lambda page, glyph: evidence.append(glyph_reference(page, glyph)),
    )

    symbolic = [glyph for glyph in evidence if glyph["font_resource"] == "/TT2"]
    assert report["pages"][0]["status"] == "traced_with_exclusions"
    assert symbolic
    assert symbolic[0]["code"] == 33
    assert symbolic[0]["glyph_name"] == "glyph00001"
    assert all(glyph["cff_gid"] == glyph["rendered_gid"] for glyph in symbolic)


def test_trace_toutes_les_pages_auparavant_hors_capacite(tmp_path: Path) -> None:
    page_numbers = [
        1, 2, 5, 14, 18, 19, 20, 21, 23, 27, 32, 37, 39, 41, 42, 43,
        51, 70, 72, 77, 84, 86, 88, 90, 92, 103, 118, 120, 121, 122,
        124, 125, 126, 128, 130, 133, 135, 137, 138, 143, 147,
    ]
    reader = PdfReader(FULL_REFERENCE_PDF)
    pdf_path = tmp_path / "formerly-unsupported-page.pdf"
    statuses = {}

    for page_number in page_numbers:
        writer = PdfWriter()
        writer.add_page(reader.pages[page_number - 1])
        with pdf_path.open("wb") as destination:
            writer.write(destination)
        statuses[page_number] = analyze_pdf(pdf_path)["pages"][0]["status"]

    assert set(statuses.values()) <= {"traced", "traced_with_exclusions"}


def test_trace_les_polices_type0_identity_h_de_la_page_mixte(
    tmp_path: Path,
) -> None:
    reader = PdfReader(FULL_REFERENCE_PDF)
    writer = PdfWriter()
    writer.add_page(reader.pages[10])
    pdf_path = tmp_path / "mixed-fonts.pdf"
    with pdf_path.open("wb") as destination:
        writer.write(destination)
    evidence = []

    report = analyze_pdf(
        pdf_path,
        on_evidence=lambda page, glyph: evidence.append(glyph_reference(page, glyph)),
    )

    page = report["pages"][0]
    assert page["status"] == "traced"
    assert report["coverage"]["pages_partially_traced"] == 0
    assert report["coverage"]["pages_unsupported"] == 0
    assert len(evidence) == 1_290
    assert {
        resource: page["fonts"][resource]["subtype"]
        for resource in ("/G1", "/G2", "/G3", "/G4", "/G5")
    } == {resource: "/Type0" for resource in ("/G1", "/G2", "/G3", "/G4", "/G5")}
    assert all(
        page["fonts"][resource]["encoding"]
        == {
            "base": "/Identity-H",
            "code_bytes": 2,
        }
        for resource in ("/G1", "/G2", "/G3", "/G4", "/G5")
    )

    regions = source_math_regions(
        evidence, {1: page["fonts"]}, {1: page["horizontal_rules"]}
    )
    assert any(region["source_glyph_text"] == "√∑Dj=1(w(j))2" for region in regions)
    minus = next(
        glyph
        for glyph in evidence
        if glyph["glyph_name"] == "minus"
        and glyph["rendered_font"].startswith("LMMathSymbols")
    )
    assert minus["unicode"] == "−"
    assert minus["source_unicode"] == "−"
    assert minus["source_unicode_method"] == "agl"
    assert minus["agl_unicode"] == "−"
    assert minus["to_unicode"] == "≠"
    assert minus["rendered_unicode"] == "≠"
    type0 = next(
        glyph for glyph in evidence if glyph["source_unicode_method"] == "to_unicode"
    )
    assert type0["font_resource"] in {"/G1", "/G2", "/G3", "/G4", "/G5"}
    assert type0["source_unicode"] == type0["unicode"]
    assert type0["agl_unicode"] is None
    fraction = next(
        region for region in regions if region["source_glyph_text"] == "2‖w‖"
    )
    assert fraction["structural_rules"]["fraction"]["seqno"] == 179


def test_trace_le_texte_hors_des_formulaires_vectoriels_de_la_page_16(
    tmp_path: Path,
) -> None:
    reader = PdfReader(FULL_REFERENCE_PDF)
    writer = PdfWriter()
    writer.add_page(reader.pages[15])
    pdf_path = tmp_path / "page-16.pdf"
    with pdf_path.open("wb") as destination:
        writer.write(destination)
    evidence = []

    report = analyze_pdf(
        pdf_path,
        on_evidence=lambda page, glyph: evidence.append(glyph_reference(page, glyph)),
    )

    page = report["pages"][0]
    assert page["status"] == "traced_with_exclusions"
    assert report["coverage"]["pages_traced_with_exclusions"] == 1
    assert len(evidence) == 1_206
    assert [region["resource"] for region in page["opaque_regions"]] == [
        "/X9",
        "/X10",
    ]
    assert [region["bbox"] for region in page["opaque_regions"]] == [
        [70.0, 214.14202880859375, 271.0, 373.14202880859375],
        [272.0, 214.14202880859375, 472.0, 373.14202880859375],
    ]
    regions = source_math_regions(
        evidence, {1: page["fonts"]}, {1: page["horizontal_rules"]}
    )
    assert len(regions) == 24
    assert any(region["source_glyph_text"] == "x(k)i,j" for region in regions)
