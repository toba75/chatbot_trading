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
from pdf_math_audit.development import (
    develop_document,
    operation_kind,
    strip_item_development_origins,
)
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
    document: DoclingDocument, operations: list[dict[str, Any]]
) -> DoclingDocument:
    derived, _supplements = develop_document(document, operations)
    return derived


def derive_document_and_page_html(
    document: DoclingDocument,
    operations: list[dict[str, Any]],
    pdf_path: Path | None = None,
    *,
    native_document_sha256: str | None = None,
    recipe_sha256_value: str | None = None,
) -> tuple[DoclingDocument, bytes]:
    """Produit une seule copie dérivée et son HTML paginé en MathML."""
    corrections = [
        operation
        for operation in operations
        if operation_kind(operation) != "pdf_supplement"
    ]
    supplements = [
        operation
        for operation in operations
        if operation_kind(operation) == "pdf_supplement"
    ]
    marked_records: list[dict[str, Any]] = []
    markers: list[str] = []
    serialized_document = document.model_dump_json()
    for index, record in enumerate(corrections):
        marker = _unique_marker(serialized_document, _MATH_MARKER, index)
        markers.append(marker)
        marked_records.append(
            record | {"after": marker, "final_after": record["after"]}
        )

    derived, created_supplements = develop_document(
        document, [*marked_records, *supplements]
    )
    for record, item in created_supplements:
        record["derived_docling_ref"] = item.self_ref
        record["derived_charspan"] = [0, len(item.text)]
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
        markers, marked_records, corrections, strict=True
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

    html = _mark_supplements_in_html(html, supplements)
    html = _add_development_metadata(
        html, native_document_sha256, recipe_sha256_value
    )
    return DoclingDocument.model_validate(derived.model_dump()), html.encode("utf-8")


def render_developed_markdown(
    document: DoclingDocument,
    operations: list[dict[str, Any]],
    *,
    native_document_sha256: str | None = None,
    recipe_sha256_value: str | None = None,
) -> bytes:
    """Sérialise le même document développé avec les suppléments démarqués."""
    supplements = [
        operation
        for operation in operations
        if operation_kind(operation) == "pdf_supplement"
    ]
    view = document.model_copy(deep=True)
    markers: list[tuple[str, dict[str, Any]]] = []
    for index, operation in enumerate(supplements):
        reference = operation.get("derived_docling_ref")
        item = next(
            (item for item, _level in view.iterate_items() if item.self_ref == reference),
            None,
        )
        if item is None:
            raise ValueError(
                f"Supplément absent du document développé : {operation.get('region_id')}"
            )
        marker = f"OSTPDFSUPPLEMENT{index:08d}END"
        item.text = marker
        markers.append((marker, operation))

    strip_item_development_origins(view)
    markdown = view.export_to_markdown()
    for marker, operation in markers:
        rendered = f"$${marker}$$"
        replacement = (
            f"> **Supplément PDF dérivé** — région `{operation['region_id']}`, "
            f"page {operation['page']}.\n>\n> $${operation['after']}$$"
        )
        if markdown.count(rendered) != 1:
            raise ValueError(
                f"Supplément absent du Markdown développé : {operation['region_id']}"
            )
        markdown = markdown.replace(rendered, replacement, 1)

    return _add_development_metadata(
        markdown, native_document_sha256, recipe_sha256_value, markdown=True
    ).encode("utf-8")


def _mark_supplements_in_html(
    html: str, supplements: list[dict[str, Any]]
) -> str:
    by_ref = {
        record.get("derived_docling_ref"): record
        for record in supplements
        if record.get("derived_docling_ref")
    }
    if not by_ref:
        return html

    pattern = re.compile(
        r"(?P<fragment><math\b(?P<math_attrs>[^>]*data-docling-ref=\"(?P<math_ref>[^\"]+)\"[^>]*)>.*?</math>|"
        r"<img\b(?P<img_attrs>[^>]*data-docling-ref=\"(?P<img_ref>[^\"]+)\"[^>]*)>)",
        re.DOTALL,
    )
    seen: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        fragment = match.group("fragment")
        reference = match.group("math_ref") or match.group("img_ref")
        record = by_ref.get(reference)
        if record is None:
            return fragment
        if 'data-origin="' not in fragment:
            fragment = re.sub(
                r"<(?P<tag>math|img)\b",
                r'<\g<tag> data-origin="pdf_supplement"',
                fragment,
                count=1,
            )
        seen.add(reference)
        label = (
            "Supplément PDF dérivé — contenu absent de la transcription — "
            f"région {html_module.escape(str(record['region_id']), quote=True)}, "
            f"page {record['page']}"
        )
        return (
            '<span class="pdf-supplement" data-origin="pdf_supplement" '
            f'data-supplement-id="{html_module.escape(str(record["region_id"]), quote=True)}" '
            f'aria-label="{html_module.escape(label, quote=True)}">'
            f'<span class="pdf-supplement-label">{html_module.escape(label)}</span>'
            f"{fragment}</span>"
        )

    rendered = pattern.sub(replace, html)
    if seen != set(by_ref):
        missing = ", ".join(sorted(set(by_ref) - seen))
        raise ValueError(f"Supplément non localisable dans l'HTML : {missing}")
    return rendered


def _add_development_metadata(
    content: str,
    native_document_sha256: str | None,
    recipe_sha256_value: str | None,
    *,
    markdown: bool = False,
) -> str:
    if native_document_sha256 is None or recipe_sha256_value is None:
        return content
    metadata = []
    if native_document_sha256 is not None:
        metadata.append(f"native_document_sha256: {native_document_sha256}")
    if recipe_sha256_value is not None:
        metadata.append(f"recipe_sha256: {recipe_sha256_value}")
    if markdown:
        prefix = "".join(f"<!-- {line} -->\n" for line in metadata)
        return prefix + content
    tags = "".join(
        f'<meta name="{key}" content="{value}">'
        for key, value in (
            ("development-native-document-sha256", native_document_sha256),
            ("development-recipe-sha256", recipe_sha256_value),
        )
        if value is not None
    )
    if "</head>" not in content:
        raise ValueError("HTML développé sans élément head pour ses empreintes")
    return content.replace("</head>", f"{tags}</head>", 1)
