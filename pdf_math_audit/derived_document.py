from __future__ import annotations

import html as html_module
import re
from typing import Any

from docling_core.types.doc import (
    DocItemLabel,
    DoclingDocument,
)
from latex2mathml.converter import convert

from pdf_math_audit.correction_targets import TEXT_REF
from pdf_math_audit.page_html import render_page_anchored_html


_MATH_MARKER = "OSTMATHCORRECTION{index:08d}END"
_INLINE_MATH_MARKER = "OSTDOCLINGMATH{index:08d}END"
_INLINE_MATH = re.compile(r"\$([^$\r\n]+)\$")
_MATHML = re.compile(r"<math\b[^>]*>.*?</math>", re.DOTALL)
_INLINE_RELATION = re.compile(r"\A\S+\s*[<>=]\s*\S+\Z")
_INLINE_SYNTAX = re.compile(r"[+*/^_{}()\[\]\\]")


def _unique_marker(serialized_document: str, template: str, index: int) -> str:
    marker = template.format(index=index)
    while marker in serialized_document:
        marker += "X"
    return marker


def _is_unambiguous_inline_math(latex: str) -> bool:
    stripped = latex.strip()
    return (
        not any(character.isspace() for character in stripped)
        or stripped.startswith(("\\", "{"))
        or bool(_INLINE_RELATION.fullmatch(stripped))
        or bool(_INLINE_SYNTAX.search(stripped))
    )


def _mark_inline_math(
    document: DoclingDocument,
) -> list[tuple[str, int, str, str]]:
    marked: list[tuple[str, int, str, str]] = []
    serialized_document = document.model_dump_json()
    for node_index, node in enumerate(document.texts):
        if node.label == DocItemLabel.FORMULA:
            continue

        def mark(match: re.Match[str]) -> str:
            latex = html_module.unescape(match.group(1))
            if not _is_unambiguous_inline_math(latex):
                return match.group(0)

            marker = _unique_marker(
                serialized_document, _INLINE_MATH_MARKER, len(marked)
            )
            mathml = convert(latex).replace(
                "<math ", '<math data-docling-kind="inline-math" ', 1
            )
            marked.append((marker, node_index, match.group(0), mathml))
            return marker

        node.text = _INLINE_MATH.sub(mark, node.text)
    return marked


def derive_document(
    document: DoclingDocument, accepted: list[dict[str, Any]]
) -> DoclingDocument:
    derived = document.model_copy(deep=True)
    by_text: dict[int, list[dict[str, Any]]] = {}
    for record in accepted:
        if record.get("kind") == "formula_insertion":
            raise ValueError("Une formule sans ancrage Docling ne peut pas être publiée")
        match = TEXT_REF.fullmatch(record["docling_ref"])
        if match is None:
            raise ValueError("Référence Docling invalide après validation")
        by_text.setdefault(int(match.group(1)), []).append(record)
    for index, records in by_text.items():
        node = derived.texts[index]
        for record in sorted(
            records, key=lambda item: item["charspan"][0], reverse=True
        ):
            start, end = record["charspan"]
            if not (0 <= start < end <= len(node.text)):
                raise ValueError("Charspan de correction invalide")
            if node.label == DocItemLabel.FORMULA and [start, end] != [
                0,
                len(node.text),
            ]:
                raise ValueError(
                    "Une formule Docling ne peut être remplacée que dans son intégralité"
                )
            node.text = node.text[:start] + record["after"] + node.text[end:]
    return DoclingDocument.model_validate(derived.model_dump())


def derive_document_and_page_html(
    document: DoclingDocument, accepted: list[dict[str, Any]]
) -> tuple[DoclingDocument, bytes]:
    """Produit une seule copie dérivée et son HTML paginé en MathML."""
    marked_records = []
    markers = []
    serialized_document = document.model_dump_json()
    for index, record in enumerate(accepted):
        marker = _unique_marker(serialized_document, _MATH_MARKER, index)
        markers.append(marker)
        marked_records.append(
            record | {"after": marker, "final_after": record["after"]}
        )

    derived = derive_document(document, marked_records)
    inline_math = _mark_inline_math(derived)
    html = render_page_anchored_html(derived).decode("utf-8")
    for marker, record, source_record in zip(
        markers, marked_records, accepted, strict=True
    ):
        reference = record.get("derived_docling_ref") or record.get("docling_ref")
        if record.get("derived_docling_ref"):
            source_record["derived_docling_ref"] = reference
        match = TEXT_REF.fullmatch(str(reference or ""))
        if match is None:
            raise ValueError("Référence Docling invalide après validation")
        node = derived.texts[int(match.group(1))]
        if node.label == DocItemLabel.FORMULA:
            candidates = [
                math
                for math in _MATHML.findall(html)
                if f'<annotation encoding="TeX">{marker}</annotation>' in math
            ]
            if len(candidates) != 1:
                raise ValueError(
                    "La formule corrigée n'est pas localisable dans l'HTML dérivé"
                )
            html = html.replace(candidates[0], record["mathml"], 1)
            replacement = record["final_after"]
        else:
            if html.count(marker) != 1:
                raise ValueError(
                    "La correction n'est pas localisable dans l'HTML dérivé"
                )
            html = html.replace(marker, record["mathml"], 1)
            replacement = record["final_after"]

        if node.text.count(marker) != 1:
            raise ValueError(
                "La correction n'est pas localisable dans le document dérivé"
            )
        node.text = node.text.replace(marker, replacement, 1)
        if node.orig == marker:
            node.orig = replacement

    for marker, node_index, source, mathml in inline_math:
        if html.count(marker) != 1:
            raise ValueError(
                "Le fragment LaTeX inline n'est pas localisable dans l'HTML"
            )
        html = html.replace(marker, mathml, 1)
        node = derived.texts[node_index]
        if node.text.count(marker) != 1:
            raise ValueError(
                "Le fragment LaTeX inline n'est pas localisable dans le document"
            )
        node.text = node.text.replace(marker, source, 1)

    return DoclingDocument.model_validate(derived.model_dump()), html.encode("utf-8")
