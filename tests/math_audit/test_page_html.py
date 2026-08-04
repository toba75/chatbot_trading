from pathlib import Path
import re

import pytest

from docling_core.types.doc import DoclingDocument, PageItem, Size
from latex2mathml.converter import convert
from lxml import html as lxml_html

from pdf_math_audit.page_html import _wrap_tex_annotations, render_page_anchored_html


ROOT = Path(__file__).parents[2]
DOCUMENT = ROOT / "experiments/math_pipeline_comparison/docling-subset-document.json"


def test_produit_une_ancre_exacte_par_page_sans_modifier_le_document() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    original_images = {
        number: page.image for number, page in document.pages.items()
    }

    html = render_page_anchored_html(document).decode("utf-8")

    assert [html.count(f"id='page-{number}'") for number in document.pages] == [
        1
    ] * len(document.pages)
    assert "body > table > tbody > tr > td:first-child { display: none; }" in html
    assert {number: page.image for number, page in document.pages.items()} == original_images


def test_conserve_les_images_de_contenu_sans_dupliquer_les_images_de_page() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())

    html = render_page_anchored_html(document).decode("utf-8")

    assert html.count("<div class='page'") == len(document.pages)
    assert "no page-image found" in html
    assert html.count("data:image/") < len(document.pages)


def test_ajoute_une_ancre_aux_pages_sans_contenu() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    document.pages[3] = PageItem(page_no=3, size=Size(width=612, height=792))

    html = render_page_anchored_html(document).decode("utf-8")

    assert "id='page-3'" in html
    assert "class='page blank-page'" in html
    assert "Page sans contenu Docling" in html


def test_une_provenance_secondaire_ne_cree_pas_une_fausse_page_html() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())
    document.pages[3] = PageItem(page_no=3, size=Size(width=612, height=792))
    secondary = document.texts[0].prov[0].model_copy(update={"page_no": 3})
    document.texts[0].prov.append(secondary)

    html = render_page_anchored_html(document).decode("utf-8")

    assert html.count("id='page-3'") == 1
    assert "class='page blank-page' id='page-3'" in html
    assert "Contenu rattaché à une autre section HTML" in html
    assert "Page sans contenu Docling" not in html


def test_conserve_le_tex_dans_une_semantique_mathml_non_visible() -> None:
    document = DoclingDocument.model_validate_json(DOCUMENT.read_bytes())

    html = render_page_anchored_html(document).decode("utf-8")
    formulas = re.findall(r"<math\b[^>]*>.*?</math>", html, re.DOTALL)

    assert len(formulas) == 3
    assert all("><semantics>" in formula for formula in formulas)
    assert all('<annotation encoding="TeX">' in formula for formula in formulas)
    assert all("</annotation></semantics></math>" in formula for formula in formulas)


def test_rend_le_latex_inline_explicitement_delimite_dans_un_texte_mathml() -> None:
    latex = r"\begin{cases} 0 & \text{if $z<0$} \\ z & \text{otherwise} \end{cases}"
    source = convert(latex).replace(
        "</math>", f'<annotation encoding="TeX">{latex}</annotation></math>'
    )

    html = _wrap_tex_annotations(source)
    math = lxml_html.fragment_fromstring(html)

    visible = "".join(math.xpath("./semantics/*[1]")[0].itertext())
    assert "$" not in visible
    assert "&" not in visible
    assert "z<0" in visible
    assert math.xpath("string(./semantics/annotation)") == latex


def test_ne_prend_pas_un_dollar_echappe_pour_un_delimiteur_math() -> None:
    latex = r"\text{cost \$5 and $x$}"
    source = convert(latex).replace(
        "</math>", f'<annotation encoding="TeX">{latex}</annotation></math>'
    )

    html = _wrap_tex_annotations(source)
    math = lxml_html.fragment_fromstring(html)

    visible = "".join(math.xpath("./semantics/*[1]")[0].itertext())
    assert visible.replace("\N{NO-BREAK SPACE}", " ") == "cost $5 and x"
    assert math.xpath("string(./semantics/annotation)") == latex


def test_conserve_une_esperluette_litterale() -> None:
    latex = r"A \& B"
    source = convert(latex).replace(
        "</math>", f'<annotation encoding="TeX">{latex}</annotation></math>'
    )

    html = _wrap_tex_annotations(source)
    math = lxml_html.fragment_fromstring(html)

    assert "".join(math.xpath("./semantics/*[1]")[0].itertext()) == "A&B"
    assert math.xpath("string(./semantics/annotation)") == latex


def test_refuse_les_esperluettes_litterales_et_d_alignement_ambigues() -> None:
    source = (
        '<math xmlns="http://www.w3.org/1998/Math/MathML">'
        '<mrow><mi>A</mi><mi>&amp;</mi><mi>B</mi><mi>&amp;</mi><mi>C</mi></mrow>'
        '<annotation encoding="TeX">A \\&amp; B &amp; C</annotation></math>'
    )

    with pytest.raises(ValueError, match="littérales et d'alignement ambiguës"):
        _wrap_tex_annotations(source)


def test_distingue_l_alignement_d_une_esperluette_litterale_dans_du_texte() -> None:
    latex = r"\begin{aligned} a & \text{A \& B} \end{aligned}"
    source = convert(latex).replace(
        "</math>", f'<annotation encoding="TeX">{latex}</annotation></math>'
    )

    html = _wrap_tex_annotations(source)
    math = lxml_html.fragment_fromstring(html)
    visible = "".join(math.xpath("./semantics/*[1]")[0].itertext())

    assert visible.count("&") == 1
    assert "\\" not in visible
    assert math.xpath("string(./semantics/annotation)") == latex


@pytest.mark.parametrize(
    "latex",
    [
        r"\text{see $A \& B$}",
        r"\begin{aligned} x & \text{see $A \& B$} \end{aligned}",
    ],
)
def test_conserve_une_esperluette_litterale_dans_un_fragment_math(
    latex: str,
) -> None:
    source = convert(latex).replace(
        "</math>", f'<annotation encoding="TeX">{latex}</annotation></math>'
    )

    html = _wrap_tex_annotations(source)
    math = lxml_html.fragment_fromstring(html)
    visible = "".join(math.xpath("./semantics/*[1]")[0].itertext())

    assert visible.count("&") == 1
    assert "\\" not in visible
    assert not math.xpath(".//*[@data-docling-literal-ampersand]")
    assert math.xpath("string(./semantics/annotation)") == latex


def test_distingue_alignement_et_esperluette_dans_un_fragment_imbrique() -> None:
    nested = r"\begin{aligned} a & \text{A \& B} \end{aligned}"
    latex = rf"\text{{outer ${nested}$}}"
    encoded = latex.replace("&", "&amp;")
    source = (
        '<math xmlns="http://www.w3.org/1998/Math/MathML"><mrow>'
        f"<mtext>outer ${nested.replace('&', '&amp;')}$</mtext></mrow>"
        f'<annotation encoding="TeX">{encoded}</annotation></math>'
    )

    html = _wrap_tex_annotations(source)
    math = lxml_html.fragment_fromstring(html)
    visible = "".join(math.xpath("./semantics/*[1]")[0].itertext())

    assert visible.count("&") == 1
    assert "\\" not in visible
    assert not math.xpath(".//*[@data-docling-literal-ampersand]")
    assert math.xpath("string(./semantics/annotation)") == latex


def test_refuse_une_annotation_tex_de_structure_inattendue() -> None:
    malformed = (
        '<math xmlns="http://www.w3.org/1998/Math/MathML">'
        '<mi>x</mi><annotation encoding="TeX">x</annotation></math>'
    )

    with pytest.raises(ValueError, match="Structure d'annotation TeX"):
        _wrap_tex_annotations(malformed)


@pytest.mark.parametrize(
    "annotation",
    [
        '<annotation encoding="TeX">x & y < z</annotation>',
        "<annotation encoding='TeX' >x &amp; y &lt; z</annotation>",
        '<ANNOTATION encoding="TeX">x &amp; y &lt; z</ANNOTATION>',
        '<annotation encoding="TeX">x &#38; y &#x3c; z</annotation>',
    ],
)
def test_normalise_les_caracteres_html_du_tex_sans_perte(annotation: str) -> None:
    source = (
        '<math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>x</mi></mrow>'
        f"{annotation}</math>"
    )

    html = _wrap_tex_annotations(source)

    assert "<semantics>" in html
    assert '<annotation encoding="TeX">x &amp; y &lt; z</annotation>' in html


def test_ne_decode_pas_une_esperluette_tex_comme_une_entite_html() -> None:
    source = (
        '<math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>x</mi></mrow>'
        '<annotation encoding="TeX">\\begin{array}a&not b&copy; c\\end{array}'
        "</annotation></math>"
    )

    html = _wrap_tex_annotations(source)

    assert r"\begin{array}a&amp;not b&amp;copy; c\end{array}" in html
    assert "¬" not in html
    assert "©" not in html


@pytest.mark.parametrize(
    ("latex", "operator"),
    [
        (r"\max _ { a \in \mathcal { A } } f ( a )", "max"),
        (r"\arg \max _ { a \in \mathcal { A } } f ( a )", "arg max"),
        (r"\min _ { a \in \mathcal { A } } f ( a )", "min"),
        (r"\arg \min _ { a \in \mathcal { A } } f ( a )", "arg min"),
    ],
)
def test_centre_la_condition_des_operateurs_de_limite_en_bloc(
    latex: str, operator: str
) -> None:
    source = convert(latex).replace(
        'display="inline"', 'display="block"'
    ).replace(
        "</math>", f'<annotation encoding="TeX">{latex}</annotation></math>'
    )

    html = _wrap_tex_annotations(source)
    math = lxml_html.fragment_fromstring(html)

    under = math.xpath("./semantics/mrow/munder")
    assert len(under) == 1
    assert "".join(under[0][0].itertext()) == operator.replace(" ", "")
    assert len(under[0][0].xpath(".//mspace")) == int(operator.startswith("arg "))
    assert "".join(under[0][1].itertext()) == "a∈A"
    assert "\\arg" not in "".join(math.xpath("./semantics/mrow")[0].itertext())
    assert math.xpath("string(./semantics/annotation)") == latex


def test_ne_deplace_pas_un_operateur_imbrique_dans_un_indice() -> None:
    latex = r"x _ { \max _ { a \in A } f ( a ) }"
    source = convert(latex).replace(
        'display="inline"', 'display="block"'
    ).replace(
        "</math>", f'<annotation encoding="TeX">{latex}</annotation></math>'
    )

    html = _wrap_tex_annotations(source)
    math = lxml_html.fragment_fromstring(html)

    assert not math.xpath(".//munder")
    assert len(math.xpath(".//msub")) == 2


def test_rapproche_les_doubles_barres_de_norme_sans_perdre_leur_exposant() -> None:
    latex = r"\min \frac { 1 } { 2 } | | w | | ^ { 2 }"
    source = convert(latex).replace(
        'display="inline"', 'display="block"'
    ).replace(
        "</math>", f'<annotation encoding="TeX">{latex}</annotation></math>'
    )

    html = _wrap_tex_annotations(source)
    math = lxml_html.fragment_fromstring(html)

    bars = math.xpath("./semantics/mrow/mo[text()='|'] | ./semantics/mrow/msup/mo[text()='|']")
    assert len(bars) == 4
    assert all(bar.get("lspace") == "0em" for bar in bars)
    assert all(bar.get("rspace") == "0em" for bar in bars)
    assert math.xpath("string(./semantics/annotation)") == latex


def test_conserve_les_barres_simples_de_valeur_absolue() -> None:
    latex = r"| x |"
    source = convert(latex).replace(
        "</math>", f'<annotation encoding="TeX">{latex}</annotation></math>'
    )

    html = _wrap_tex_annotations(source)
    math = lxml_html.fragment_fromstring(html)

    assert len(math.xpath("./semantics/mrow/mo[text()='|']")) == 2
    assert not math.xpath("./semantics/mrow/mo[@lspace or @rspace]")


def test_ne_fusionne_pas_deux_valeurs_absolues_adjacentes() -> None:
    latex = r"| x | | y |"
    source = convert(latex).replace(
        "</math>", f'<annotation encoding="TeX">{latex}</annotation></math>'
    )

    html = _wrap_tex_annotations(source)
    math = lxml_html.fragment_fromstring(html)

    assert len(math.xpath("./semantics/mrow/mo[text()='|']")) == 4
    assert not math.xpath("./semantics/mrow/mo[text()='‖']")
    assert math.xpath("string(./semantics/annotation)") == latex


def test_ne_fusionne_pas_les_arguments_d_un_indice() -> None:
    latex = r"| _ |"
    source = convert(latex).replace(
        "</math>", f'<annotation encoding="TeX">{latex}</annotation></math>'
    )

    html = _wrap_tex_annotations(source)
    math = lxml_html.fragment_fromstring(html)

    subscript = math.xpath("./semantics/mrow/msub")
    assert len(subscript) == 1
    assert len(subscript[0]) == 2
    assert [node.text for node in subscript[0]] == ["|", "|"]
