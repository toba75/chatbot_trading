from __future__ import annotations

import re

from docling_core.types.doc import DoclingDocument, ImageRefMode
from lxml import etree, html as lxml_html


_PAGE = re.compile(r"<div class=(['\"])page\1>")
_MATHML = re.compile(r"<math\b[^>]*>.*?</math>", re.DOTALL)
_TEX_ANNOTATION = re.compile(
    r"<annotation\b[^>]*>(.*?)</annotation\s*>", re.DOTALL | re.IGNORECASE
)
_XML_ENTITY = re.compile(r"&(?:(amp|lt|gt|quot|apos)|#([0-9]+)|#x([0-9a-fA-F]+));")
_XML_ENTITY_VALUE = {
    "amp": "&",
    "lt": "<",
    "gt": ">",
    "quot": '"',
    "apos": "'",
}
_NAVIGATION_STYLE = """
<style>
body > table > tbody > tr > td:first-child { display: none; }
body > table > tbody > tr > td:last-child { width: 100%; }
.page { scroll-margin-top: 1rem; }
.blank-page { color: #666; }
</style>
"""


def _decode_xml_entity(match: re.Match[str]) -> str:
    if name := match.group(1):
        return _XML_ENTITY_VALUE[name]
    return chr(int(match.group(2) or match.group(3), 10 if match.group(2) else 16))


def _position_display_limits(math: etree._Element) -> None:
    if math.get("display") != "block":
        return

    presentation = list(math)[0]
    index = 0
    while index < len(presentation):
        node = presentation[index]
        if (
            node.tag == "mi"
            and node.text == r"\arg"
            and index + 1 < len(presentation)
        ):
            limit = presentation[index + 1]
            if (
                limit.tag == "msub"
                and len(limit) == 2
                and limit[0].tag == "mo"
                and limit[0].text in {"max", "min"}
            ):
                operator = lxml_html.Element("mrow")
                argument = lxml_html.Element("mi", mathvariant="normal")
                argument.text = "arg"
                spacing = lxml_html.Element("mspace", width="0.167em")
                extremum = lxml_html.Element("mo")
                extremum.text = limit[0].text
                operator.extend((argument, spacing, extremum))
                condition = limit[1]
                limit.remove(condition)
                under = lxml_html.Element("munder")
                under.extend((operator, condition))
                presentation.remove(node)
                presentation.replace(limit, under)
                index += 1
                continue
        if (
            node.tag == "msub"
            and len(node) == 2
            and node[0].tag == "mo"
            and node[0].text in {"max", "min"}
        ):
            node.tag = "munder"
        index += 1


def _tighten_adjacent_bars(element: etree._Element) -> None:
    for child in element:
        _tighten_adjacent_bars(child)

    if element.tag != "mrow":
        return

    def is_bar(node: etree._Element) -> bool:
        return node.tag == "mo" and node.text == "|"

    children = list(element)
    for left, right in zip(children, children[1:]):
        scripted_bar = (
            right[0]
            if right.tag in {"msub", "msup", "msubsup"}
            and len(right)
            and is_bar(right[0])
            else None
        )
        right_bar = right if is_bar(right) else scripted_bar
        if is_bar(left) and right_bar is not None:
            for bar in (left, right_bar):
                bar.set("lspace", "0em")
                bar.set("rspace", "0em")


def _wrap_tex_annotations(html: str) -> str:
    def wrap(match: re.Match[str]) -> str:
        fragment = match.group(0)
        if not _TEX_ANNOTATION.search(fragment):
            return fragment

        try:
            math = lxml_html.fragment_fromstring(fragment)
        except (etree.ParserError, ValueError) as error:
            raise ValueError("Le MathML Docling annoté n'est pas analysable") from error

        children = list(math)
        annotations = [child for child in children if child.tag == "annotation"]
        tex = _TEX_ANNOTATION.findall(fragment)
        if (
            len(children) != 2
            or annotations != [children[1]]
            or children[0].tag != "mrow"
            or children[1].get("encoding") != "TeX"
            or len(tex) != 1
            or not tex[0].strip()
        ):
            raise ValueError("Structure d'annotation TeX Docling non supportée")

        annotation_text = _XML_ENTITY.sub(_decode_xml_entity, tex[0])
        _position_display_limits(math)
        _tighten_adjacent_bars(children[0])

        annotation = children[1]
        annotation.clear()
        annotation.set("encoding", "TeX")
        annotation.text = annotation_text
        semantics = lxml_html.Element("semantics")
        for child in children:
            math.remove(child)
            semantics.append(child)
        math.append(semantics)
        return lxml_html.tostring(math, encoding="unicode", method="html")

    return _MATHML.sub(wrap, html)


def render_page_anchored_html(document: DoclingDocument) -> bytes:
    """Sérialise la vue native en conservant une ancre exacte par page."""
    page_numbers = sorted(document.pages)
    view = document.model_copy(deep=True)
    for page in view.pages.values():
        page.image = None

    html = view.export_to_html(split_page_view=True, image_mode=ImageRefMode.EMBEDDED)
    provenance_pages = {
        provenance.page_no
        for item, _level in document.iterate_items()
        for provenance in getattr(item, "prov", [])
        if provenance.page_no in document.pages
    }
    content_pages = sorted(
        {
            item.prov[0].page_no
            for item, _level in document.iterate_items()
            if getattr(item, "prov", [])
            and item.prov[0].page_no in document.pages
        }
    )
    if len(_PAGE.findall(html)) != len(content_pages):
        raise ValueError(
            "Le nombre de pages HTML ne correspond pas aux provenances Docling."
        )
    page_index = 0

    def blank_page(page_number: int) -> str:
        message = (
            "Contenu rattaché à une autre section HTML"
            if page_number in provenance_pages
            else "Page sans contenu Docling"
        )
        return (
            f"<div class='page blank-page' id='page-{page_number}' "
            f"aria-label='Page {page_number} — {message}'><p>{message}</p></div>\n"
        )

    def anchor(match: re.Match[str]) -> str:
        nonlocal page_index
        page_number = content_pages[page_index]
        blanks = []
        while page_numbers[page_index] < page_number:
            blanks.append(blank_page(page_numbers[page_index]))
            page_index += 1
        quote = match.group(1)
        page_index += 1
        blanks.append(
            f"<div class={quote}page{quote} id={quote}page-{page_number}{quote}>"
        )
        return "".join(blanks)

    anchored = _PAGE.sub(anchor, _wrap_tex_annotations(html))
    trailing = "".join(blank_page(number) for number in page_numbers[page_index:])
    anchored = anchored.replace("</body>", f"{trailing}</body>", 1)
    return anchored.replace("</head>", f"{_NAVIGATION_STYLE}</head>", 1).encode(
        "utf-8"
    )
