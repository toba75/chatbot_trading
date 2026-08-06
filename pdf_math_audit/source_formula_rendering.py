from __future__ import annotations

import re
from base64 import b64encode
from html import escape
from pathlib import Path

import fitz
from docling_core.types.doc import DocItemLabel, DoclingDocument


_MATHML = re.compile(r"<math\b[^>]*>.*?</math>", re.DOTALL)
_PRE = re.compile(r"<pre\b[^>]*>.*?</pre>", re.DOTALL)
_DOCLING_REF = re.compile(r'data-docling-ref="([^"]+)"')


def visual_delimiters_balanced(latex: str) -> bool:
    opening = {"(": ")", "[": "]"}
    stack: list[str] = []
    for character in latex:
        if character in opening:
            stack.append(opening[character])
        elif character in ")]":
            if not stack or stack.pop() != character:
                return False
    return not stack


def _source_formula_image(
    source: fitz.Document,
    document: DoclingDocument,
    ref: str,
) -> str:
    item = next(
        item
        for item, _level in document.iterate_items()
        if item.self_ref == ref and item.label == DocItemLabel.FORMULA
    )
    provenance = item.prov[0]
    page_number = provenance.page_no
    docling_size = document.pages[page_number].size
    bbox = provenance.bbox.to_top_left_origin(docling_size.height)
    page = source.load_page(page_number - 1)
    scale_x = page.rect.width / docling_size.width
    scale_y = page.rect.height / docling_size.height
    if abs(scale_x - scale_y) > max(scale_x, scale_y) * 0.01:
        raise ValueError(
            f"La provenance Docling {ref} ne possède pas une échelle PDF uniforme"
        )
    clip = fitz.Rect(
        bbox.l * scale_x,
        bbox.t * scale_y,
        bbox.r * scale_x,
        bbox.b * scale_y,
    )
    clip &= page.rect
    if clip.is_empty:
        raise ValueError(f"La provenance Docling {ref} est hors de la page PDF")
    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip, alpha=False)
    encoded = b64encode(pixmap.tobytes("png")).decode("ascii")
    return (
        '<img class="formula-source-render" '
        f'data-docling-ref="{escape(ref, quote=True)}" '
        f'data-docling-charspan="0:{len(item.text)}" '
        'data-docling-formula-source="" '
        'alt="Formule reproduite depuis le PDF source" '
        f'src="data:image/png;base64,{encoded}">'
    )


def replace_unrenderable_formulas_from_source(
    html: str,
    document: DoclingDocument,
    pdf_path: Path,
) -> str:
    formulas = {
        item.self_ref: item
        for item, _level in document.iterate_items()
        if item.label == DocItemLabel.FORMULA
    }

    def replace(fragment: re.Match[str]) -> str:
        match = _DOCLING_REF.search(fragment.group(0))
        if match is None or match.group(1) not in formulas:
            return fragment.group(0)
        item = formulas[match.group(1)]
        is_fallback = "data-docling-formula-fallback" in fragment.group(0)
        if not is_fallback and visual_delimiters_balanced(item.text):
            return fragment.group(0)
        return _source_formula_image(source, document, item.self_ref)

    with fitz.open(pdf_path) as source:
        replaced = _MATHML.sub(replace, html)
        return _PRE.sub(replace, replaced)
