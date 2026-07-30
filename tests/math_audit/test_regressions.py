import hashlib
from pathlib import Path

import fitz
import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from pdf_math_audit.analyzer import analyze_pdf
from pdf_math_audit.fonts import parse_to_unicode
from pdf_math_audit.limitations import AnalysisLimitation


REFERENCE_PDF = (
    Path(__file__).parents[2]
    / "experiments"
    / "math_pipeline_comparison"
    / "source-pages-7-10.pdf"
)


def test_identite_pdf_reste_celle_des_octets_analyses(tmp_path: Path) -> None:
    pdf_path = tmp_path / "source.pdf"
    replacement_path = tmp_path / "replacement.pdf"
    with fitz.open() as document:
        document.new_page(width=100, height=100)
        document.save(pdf_path)
    with fitz.open() as document:
        document.new_page(width=200, height=200)
        document.save(replacement_path)
    original = pdf_path.read_bytes()

    def replace_after_analysis(event: dict[str, object]) -> None:
        if event["completed_units"] == 1:
            pdf_path.write_bytes(replacement_path.read_bytes())

    report = analyze_pdf(pdf_path, on_progress=replace_after_analysis)

    assert report["pages"][0]["box"] == [0.0, 0.0, 100.0, 100.0]
    assert report["pdf"]["bytes"] == len(original)
    assert report["pdf"]["sha256"] == hashlib.sha256(original).hexdigest()


def test_page_vectorielle_sans_glyphe_est_hors_capacite(tmp_path: Path) -> None:
    pdf_path = tmp_path / "vector-only.pdf"
    with fitz.open() as document:
        page = document.new_page()
        page.draw_line((72, 72), (144, 144))
        document.save(pdf_path)

    report = analyze_pdf(pdf_path)

    assert report["pages"][0]["status"] == "unsupported"
    assert report["pages"][0]["reasons"] == [
        {
            "code": "page_content_unsupported",
            "message": "Contenu de page sans texte supporté",
        }
    ]


def test_to_unicode_accepte_une_cmap_valide_sur_une_ligne() -> None:
    cmap = DecodedStreamObject()
    cmap.set_data(b"1 beginbfchar <21> <2212> endbfchar")
    font = DictionaryObject({NameObject("/ToUnicode"): cmap})

    assert parse_to_unicode(font) == {0x21: "−"}


def test_to_unicode_refuse_une_destination_hexadecimale_invalide() -> None:
    cmap = DecodedStreamObject()
    cmap.set_data(b"1 beginbfchar <21> <ZZZZ> endbfchar")
    font = DictionaryObject({NameObject("/ToUnicode"): cmap})

    with pytest.raises(AnalysisLimitation) as error:
        parse_to_unicode(font)

    assert error.value.status == "unsupported"
    assert error.value.code == "to_unicode_cmap_invalid"


@pytest.mark.parametrize(
    ("cmap_data", "reason_code"),
    [
        (
            b"2 beginbfchar <21> <2212> endbfchar",
            "to_unicode_cmap_invalid",
        ),
        (
            b"2 beginbfchar <21> <2212> <22> endbfchar",
            "to_unicode_cmap_invalid",
        ),
        (
            b"1 beginbfchar <0100> <0041> endbfchar "
            b"1 beginbfchar <21> <2212> endbfchar",
            "to_unicode_cmap_unsupported",
        ),
    ],
)
def test_to_unicode_refuse_une_structure_non_prouvee(
    cmap_data: bytes, reason_code: str
) -> None:
    cmap = DecodedStreamObject()
    cmap.set_data(cmap_data)
    font = DictionaryObject({NameObject("/ToUnicode"): cmap})

    with pytest.raises(AnalysisLimitation) as error:
        parse_to_unicode(font)

    assert error.value.status == "unsupported"
    assert error.value.code == reason_code


def test_xobject_declare_mais_inutilise_ne_change_pas_la_capacite(
    tmp_path: Path,
) -> None:
    reader = PdfReader(REFERENCE_PDF)
    resources = reader.pages[0]["/Resources"].get_object()
    resources[NameObject("/XObject")] = DictionaryObject()
    pdf_path = tmp_path / "unused-xobject.pdf"
    writer = PdfWriter()
    writer.append_pages_from_reader(reader)
    with pdf_path.open("wb") as destination:
        writer.write(destination)

    report = analyze_pdf(pdf_path)

    assert [page["status"] for page in report["pages"]] == ["traced", "traced"]


def test_image_inline_melee_au_texte_est_hors_capacite(tmp_path: Path) -> None:
    reader = PdfReader(REFERENCE_PDF)
    page = reader.pages[0]
    content = DecodedStreamObject()
    content.set_data(
        page.get_contents().get_data()
        + b"\nq BI /W 1 /H 1 /BPC 8 /CS /DeviceGray ID \x00 EI Q\n"
    )
    page[NameObject("/Contents")] = content
    pdf_path = tmp_path / "inline-image.pdf"
    writer = PdfWriter()
    writer.append_pages_from_reader(reader)
    with pdf_path.open("wb") as destination:
        writer.write(destination)

    report = analyze_pdf(pdf_path)

    assert report["pages"][0]["status"] == "unsupported"
    assert report["pages"][0]["reasons"] == [
        {
            "code": "page_content_unsupported",
            "message": "Opérateurs non supportés: INLINE IMAGE",
        }
    ]
