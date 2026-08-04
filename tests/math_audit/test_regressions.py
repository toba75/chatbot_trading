import hashlib
from pathlib import Path

import fitz
import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    FloatObject,
    NameObject,
)

from pdf_math_audit.analyzer import analyze_pdf
from pdf_math_audit.fonts import parse_to_unicode
from pdf_math_audit.limitations import AnalysisLimitation
from pdf_math_audit.trace import _font_resource_key


REFERENCE_PDF = (
    Path(__file__).parents[2]
    / "experiments"
    / "math_pipeline_comparison"
    / "source-pages-7-10.pdf"
)


def _pdf_with_form_xobject(
    tmp_path: Path, form_data: bytes, invocation: bytes
) -> Path:
    reader = PdfReader(REFERENCE_PDF)
    page = reader.pages[0]
    form = DecodedStreamObject()
    form.set_data(form_data)
    form_resources = DictionaryObject()
    if fonts := page["/Resources"].get("/Font"):
        form_resources[NameObject("/Font")] = fonts
    form.update(
        {
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Form"),
            NameObject("/BBox"): ArrayObject(map(FloatObject, [0, 0, 10, 10])),
            NameObject("/Resources"): form_resources,
        }
    )
    resources = page["/Resources"]
    xobjects = resources.get("/XObject") or DictionaryObject()
    resources[NameObject("/XObject")] = xobjects
    xobjects[NameObject("/XTest")] = form
    content = DecodedStreamObject()
    content.set_data(page.get_contents().get_data() + invocation)
    page[NameObject("/Contents")] = content
    output = tmp_path / "form-xobject.pdf"
    writer = PdfWriter()
    writer.add_page(page)
    with output.open("wb") as destination:
        writer.write(destination)
    return output


def test_conserve_la_boite_transformee_d_un_formulaire_vectoriel(
    tmp_path: Path,
) -> None:
    pdf_path = _pdf_with_form_xobject(
        tmp_path,
        b"0 0 m 10 10 l S",
        b"\nq 2 0 0 3 10 20 cm /XTest Do Q\n",
    )

    report = analyze_pdf(pdf_path)

    page = report["pages"][0]
    assert page["status"] == "traced_with_exclusions"
    assert page["opaque_regions"][0]["bbox"] == pytest.approx(
        [10.0, 616.1420288085938, 30.0, 646.1420288085938]
    )


def test_trace_le_texte_embarque_dans_un_formulaire(tmp_path: Path) -> None:
    pdf_path = _pdf_with_form_xobject(
        tmp_path,
        b"BT /Ty3 5 Tf 1 0 0 1 1 5 Tm (T) Tj ET",
        b"\n/XTest Do\n",
    )

    report = analyze_pdf(pdf_path)

    page = report["pages"][0]
    assert page["status"] == "traced_with_exclusions"
    assert page["opaque_regions"][-1]["resource"] == "/XTest"
    assert page["opaque_regions"][-1]["text_traced"] is True


def test_distingue_deux_polices_de_meme_nom_local_apres_une_limitation() -> None:
    first_xrefs = {}

    assert _font_resource_key("/F1", 10, first_xrefs) == "/F1"
    assert _font_resource_key("/F1", 20, first_xrefs) == "/F1@20"


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
        (
            b"1 beginbfrange <22> <21> <0041> endbfrange",
            "to_unicode_cmap_invalid",
        ),
        (
            b"1 begincodespacerange <0000> <FFFF> endcodespacerange "
            b"1 beginbfchar <21> <2212> endbfchar",
            "to_unicode_cmap_unsupported",
        ),
        (
            b"/Adobe-Identity-UCS usecmap 1 beginbfchar <21> <2212> endbfchar",
            "to_unicode_cmap_unsupported",
        ),
        (
            b"1 beginbfchar <21> <41> endbfchar",
            "to_unicode_cmap_invalid",
        ),
        (
            b"1 beginbfchar <21> <D800> endbfchar",
            "to_unicode_cmap_invalid",
        ),
        (
            b"1 beginbfchar <21> <DC00> endbfchar",
            "to_unicode_cmap_invalid",
        ),
        (
            b"1 beginbfrange <21> <22> <D7FF> endbfrange",
            "to_unicode_cmap_invalid",
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
