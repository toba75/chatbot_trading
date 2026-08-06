from __future__ import annotations

import html as html_module
import re
from pathlib import Path
from typing import Any

from docling_core.types.doc import (
    DocItemLabel,
    DoclingDocument,
)

from pdf_math_audit.correction_targets import TEXT_REF
from pdf_math_audit.inline_math import (
    carries_inline_math,
    inline_math_spans,
    is_unambiguous_inline_math,
)
from pdf_math_audit.mathml_candidate import publishable_mathml
from pdf_math_audit.page_html import annotate_mathml, render_page_anchored_html


_MATH_MARKER = "OSTMATHCORRECTION{index:08d}END"
_INLINE_MATH_MARKER = "OSTDOCLINGMATH{index:08d}END"
_MATHML = re.compile(r"<math\b[^>]*>.*?</math>", re.DOTALL)


def _unique_marker(serialized_document: str, template: str, index: int) -> str:
    marker = template.format(index=index)
    while marker in serialized_document:
        marker += "X"
    return marker


def _mark_inline_math(
    document: DoclingDocument,
) -> list[tuple[str, int, str, str]]:
    marked: list[tuple[str, int, str, str]] = []
    serialized_document = document.model_dump_json()
    for node_index, node in enumerate(document.texts):
        if not carries_inline_math(node):
            continue

        parts: list[str] = []
        cursor = 0
        for start, end, raw_latex in inline_math_spans(node.text):
            latex = html_module.unescape(raw_latex)
            if not is_unambiguous_inline_math(latex):
                continue
            # Une conversion non prouvée laisse le fragment intact : l'audit
            # d'intégrité le compte alors comme une formule attendue et manquante
            # plutôt que de publier un contenu altéré.
            converted = publishable_mathml(latex)
            if converted is None:
                continue

            marker = _unique_marker(
                serialized_document, _INLINE_MATH_MARKER, len(marked)
            )
            mathml = converted.replace(
                "<math ", '<math data-docling-kind="inline-math" ', 1
            )
            original = node.text[start:end]
            marked.append((marker, node_index, original, mathml))
            parts.extend((node.text[cursor:start], marker))
            cursor = end
        if parts:
            parts.append(node.text[cursor:])
            node.text = "".join(parts)
    return marked


def _materialize_markers(
    document: DoclingDocument, replacements: dict[str, str]
) -> dict[str, tuple[str, tuple[int, int]]]:
    loci: dict[str, tuple[str, tuple[int, int]]] = {}
    for node in document.texts:
        occurrences = []
        for marker, replacement in replacements.items():
            count = node.text.count(marker)
            if count > 1:
                raise ValueError("Un marqueur mathématique n'est pas unique")
            if count == 1:
                occurrences.append((node.text.index(marker), marker, replacement))
        if not occurrences:
            continue

        parts = []
        cursor = 0
        final_length = 0
        for start, marker, replacement in sorted(occurrences):
            prefix = node.text[cursor:start]
            parts.extend((prefix, replacement))
            final_length += len(prefix)
            loci[marker] = (
                node.self_ref,
                (final_length, final_length + len(replacement)),
            )
            final_length += len(replacement)
            cursor = start + len(marker)
        parts.append(node.text[cursor:])
        node.text = "".join(parts)
        if node.orig in replacements:
            node.orig = replacements[node.orig]

    if loci.keys() != replacements.keys():
        raise ValueError("Un marqueur mathématique est absent du document dérivé")
    return loci


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
    document: DoclingDocument,
    accepted: list[dict[str, Any]],
    pdf_path: Path | None = None,
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
    html = render_page_anchored_html(derived, pdf_path).decode("utf-8")
    replacements = {
        marker: record["final_after"]
        for marker, record in zip(markers, marked_records, strict=True)
    }
    replacements.update(
        {marker: source for marker, _index, source, _mathml in inline_math}
    )
    loci = _materialize_markers(derived, replacements)
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
        derived_ref, derived_span = loci[marker]
        if derived_ref != node.self_ref:
            raise ValueError("Référence Docling dérivée incohérente")
        source_record["derived_docling_ref"] = derived_ref
        source_record["derived_charspan"] = list(derived_span)
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
            replacement_mathml = annotate_mathml(
                record["mathml"], node.self_ref, derived_span
            )
            source_record["mathml"] = replacement_mathml
            html = html.replace(candidates[0], replacement_mathml, 1)
        else:
            if html.count(marker) != 1:
                raise ValueError(
                    "La correction n'est pas localisable dans l'HTML dérivé"
                )
            replacement_mathml = annotate_mathml(
                record["mathml"], node.self_ref, derived_span
            )
            source_record["mathml"] = replacement_mathml
            html = html.replace(marker, replacement_mathml, 1)

    for marker, node_index, _source, mathml in inline_math:
        if html.count(marker) != 1:
            raise ValueError(
                "Le fragment LaTeX inline n'est pas localisable dans l'HTML"
            )
        node = derived.texts[node_index]
        derived_ref, derived_span = loci[marker]
        if derived_ref != node.self_ref:
            raise ValueError("Référence Docling inline dérivée incohérente")
        html = html.replace(
            marker,
            annotate_mathml(mathml, node.self_ref, derived_span),
            1,
        )

    return DoclingDocument.model_validate(derived.model_dump()), html.encode("utf-8")
