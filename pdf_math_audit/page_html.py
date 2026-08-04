from __future__ import annotations

import re

from docling_core.types.doc import DoclingDocument, ImageRefMode
from latex2mathml.converter import convert
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


def _is_escaped(text: str, index: int) -> bool:
    backslashes = 0
    index -= 1
    while index >= 0 and text[index] == "\\":
        backslashes += 1
        index -= 1
    return backslashes % 2 == 1


def _literal_mtext(text: str) -> str:
    result: list[str] = []
    for index, character in enumerate(text):
        if character in {"$", "&"} and _is_escaped(text, index):
            result.pop()
        result.append(character)
    return "".join(result)


def _plain_mtext_escaped_ampersands(text: str) -> int:
    inside_math = False
    escaped = 0
    for index, character in enumerate(text):
        if character == "$" and not _is_escaped(text, index):
            inside_math = not inside_math
        elif character == "&" and not inside_math and _is_escaped(text, index):
            escaped += 1
    return escaped


def _protect_literal_ampersands(latex: str) -> tuple[str, str, int]:
    sentinel = "\ue000"
    while sentinel in latex:
        sentinel = chr(ord(sentinel) + 1)
        if ord(sentinel) > 0xF8FF:
            raise ValueError("Aucune sentinelle MathML privée disponible")

    result: list[str] = []
    count = 0
    for index, character in enumerate(latex):
        if character == "&" and _is_escaped(latex, index):
            result.pop()
            result.append(sentinel)
            count += 1
        else:
            result.append(character)
    return "".join(result), sentinel, count


def _restore_literal_ampersands(
    element: etree._Element, sentinel: str, expected: int
) -> int:
    restored = 0
    for node in element.iter():
        if sentinel in (node.tail or ""):
            raise ValueError("Esperluette littérale reléguée hors d'un nœud MathML")
        occurrences = (node.text or "").count(sentinel)
        if not occurrences:
            continue
        node.text = (node.text or "").replace(sentinel, "&")
        node.set("data-docling-literal-ampersand", "")
        restored += occurrences
    if restored != expected:
        raise ValueError("Esperluettes littérales du LaTeX imbriqué perdues")
    return restored


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


def _render_nested_inline_math(element: etree._Element) -> int:
    """Rend le LaTeX explicite inclus par Docling dans un nœud ``mtext``."""
    restored_ampersands = 0
    for text_node in list(element.iter("mtext")):
        text = text_node.text or ""
        delimiters = [
            index
            for index, character in enumerate(text)
            if character == "$" and not _is_escaped(text, index)
        ]
        if len(delimiters) % 2:
            raise ValueError("Délimiteurs LaTeX imbriqués non appariés")
        if not delimiters:
            text_node.text = _literal_mtext(text)
            continue

        parent = text_node.getparent()
        if parent is None:
            raise ValueError("Fragment LaTeX imbriqué sans parent MathML")

        replacement = lxml_html.Element("mrow")
        position = 0
        for start, end in zip(delimiters[::2], delimiters[1::2], strict=True):
            if prefix := _literal_mtext(text[position:start]):
                prefix_node = lxml_html.Element("mtext", **text_node.attrib)
                prefix_node.text = prefix
                replacement.append(prefix_node)

            nested_latex = text[start + 1 : end]
            protected, sentinel, expected = _protect_literal_ampersands(nested_latex)
            try:
                nested = lxml_html.fragment_fromstring(convert(protected))
            except (etree.ParserError, ValueError) as error:
                raise ValueError("Le LaTeX imbriqué Docling n'est pas analysable") from error
            restored_ampersands += _restore_literal_ampersands(
                nested[0], sentinel, expected
            )
            replacement.append(nested[0])
            position = end + 1

        if suffix := _literal_mtext(text[position:]):
            suffix_node = lxml_html.Element("mtext", **text_node.attrib)
            suffix_node.text = suffix
            replacement.append(suffix_node)
        replacement.tail = text_node.tail
        parent.replace(text_node, replacement)
    return restored_ampersands


def _remove_latex_alignment_markers(
    element: etree._Element,
    annotation_text: str,
    escaped_in_mtext: int,
    restored_nested: int,
) -> None:
    markers = element.xpath(".//mi[text()='&']")
    tagged_nested = element.xpath(".//*[@data-docling-literal-ampersand]")
    proven_nested = [
        node for node in tagged_nested if node.tag == "mi" and node.text == "&"
    ]
    escaped = sum(
        character == "&" and _is_escaped(annotation_text, index)
        for index, character in enumerate(annotation_text)
    )
    escaped_in_identifiers = escaped - escaped_in_mtext - restored_nested
    if escaped_in_identifiers < 0:
        raise ValueError("Esperluettes MathML incohérentes")
    if escaped_in_identifiers:
        unclassified = [marker for marker in markers if marker not in proven_nested]
        if len(unclassified) != escaped_in_identifiers:
            raise ValueError("Esperluettes MathML littérales et d'alignement ambiguës")
    else:
        for marker in markers:
            if marker in proven_nested:
                continue
            parent = marker.getparent()
            if parent is None:
                raise ValueError("Marqueur d'alignement sans parent MathML")
            parent.remove(marker)
    for node in tagged_nested:
        node.attrib.pop("data-docling-literal-ampersand")


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
        escaped_in_mtext = sum(
            _plain_mtext_escaped_ampersands(text)
            for node in children[0].iter("mtext")
            for text in [node.text or ""]
        )
        restored_nested = _render_nested_inline_math(children[0])
        _remove_latex_alignment_markers(
            children[0], annotation_text, escaped_in_mtext, restored_nested
        )
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
