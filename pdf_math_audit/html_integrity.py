from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import fitz
from docling_core.types.doc import DocItemLabel, DoclingDocument
from lxml import html as lxml_html

from pdf_math_audit.html_region_links import audit_region_links
from pdf_math_audit.inline_math import (
    carries_inline_math,
    has_balanced_inline_math_delimiters,
    inline_math_spans,
)
from pdf_math_audit.source_formula_rendering import visual_delimiters_balanced


def _dollar_pairs(text: str) -> tuple[int, bool]:
    # L'inventaire attendu compte toute paire délimitée, sans reprendre le verdict
    # de convertibilité du générateur : un fragment que celui-ci renonce à publier
    # doit ressortir en anomalie, pas disparaître des deux côtés de la comparaison.
    pairs = sum(1 for _span in inline_math_spans(text))
    return pairs, has_balanced_inline_math_delimiters(text)


def _expected_content(
    document: DoclingDocument,
) -> tuple[dict[int, Counter[str]], list[dict[str, Any]]]:
    expected: dict[int, Counter[str]] = {
        page: Counter() for page in document.pages
    }
    issues: list[dict[str, Any]] = []
    for item, _level in document.iterate_items():
        provenances = getattr(item, "prov", [])
        if not provenances or provenances[0].page_no not in expected:
            continue
        page = provenances[0].page_no
        if item.label == DocItemLabel.FORMULA:
            expected[page]["math"] += 1
            if not visual_delimiters_balanced(item.text):
                issues.append(
                    {
                        "page": page,
                        "code": "formula_visual_delimiters_invalid",
                        "message": (
                            f"La formule {item.self_ref} contient des délimiteurs "
                            "visuels non appariés"
                        ),
                    }
                )
        elif item.label == DocItemLabel.PICTURE:
            expected[page]["images"] += 1
        elif carries_inline_math(item):
            pairs, valid = _dollar_pairs(getattr(item, "text", ""))
            expected[page]["math"] += pairs
            if not valid:
                issues.append(
                    {
                        "page": page,
                        "code": "inline_math_delimiters_invalid",
                        "message": "Le texte Docling contient un dollar non apparié",
                    }
                )
    return expected, issues


def _source_page_has_content(page: fitz.Page) -> bool:
    return bool(
        page.get_text().strip()
        or page.get_images(full=True)
        or page.get_drawings()
    )


def _html_page_has_content(node: Any) -> bool:
    if "blank-page" in set((node.get("class") or "").split()):
        return False
    return bool(
        node.text_content().strip()
        or node.xpath(".//math | .//img | .//svg | .//table | .//canvas")
    )


def audit_page_html(
    document: DoclingDocument,
    html: bytes,
    pdf_path: Path,
    regions: list[dict[str, Any]] | None = None,
    corrections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compare l'inventaire canonique, le PDF et le DOM page par page."""
    root = lxml_html.fromstring(html)
    page_nodes: dict[int, list[Any]] = {
        number: root.xpath(f"//*[@id='page-{number}']")
        for number in document.pages
    }
    expected, issues = _expected_content(document)
    anchors = [
        node.get("id")
        for node in root.xpath("//*[@id and starts-with(@id, 'page-')]")
    ]
    expected_anchors = [f"page-{number}" for number in sorted(document.pages)]
    if anchors != expected_anchors:
        issues.append(
            {
                "page": sorted(document.pages)[0],
                "code": "page_anchor_sequence_invalid",
                "message": "La séquence des ancres HTML ne correspond pas aux pages",
            }
        )
    pages: list[dict[str, Any]] = []

    with fitz.open(pdf_path) as source:
        for page_number in sorted(document.pages):
            nodes = page_nodes[page_number]
            if len(nodes) != 1:
                issue = {
                    "page": page_number,
                    "code": "page_anchor_count_invalid",
                    "message": f"{len(nodes)} ancre(s) HTML au lieu d'une",
                }
                issues.append(issue)
                pages.append(
                    {
                        "page": page_number,
                        "expected": dict(expected[page_number]),
                        "rendered": {},
                        "status": "failed",
                    }
                )
                continue

            node = nodes[0]
            formula_source_renders = len(
                node.xpath(".//img[@data-docling-formula-source]")
            )
            rendered = Counter(
                math=(
                    len(node.xpath(".//math[not(ancestor::math)]"))
                    + formula_source_renders
                ),
                images=len(node.xpath(".//img[not(@data-docling-formula-source)]")),
            )
            page_issues = []
            if formula_source_renders:
                page_issues.append(
                    {
                        "page": page_number,
                        "code": "formula_rendered_from_pdf_source",
                        "message": (
                            f"{formula_source_renders} formule(s) non sérialisable(s) "
                            "sont reproduites visuellement depuis le PDF source"
                        ),
                    }
                )
            raw_formula_fallbacks = len(
                node.xpath(".//pre[@data-docling-formula-fallback]")
            )
            if raw_formula_fallbacks:
                page_issues.append(
                    {
                        "page": page_number,
                        "code": "formula_rendering_fallback",
                        "message": (
                            f"{raw_formula_fallbacks} formule(s) Docling restent "
                            "exposées sous forme de LaTeX brut"
                        ),
                    }
                )
            for kind in ("math", "images"):
                if rendered[kind] < expected[page_number][kind]:
                    page_issues.append(
                        {
                            "page": page_number,
                            "code": f"{kind}_inventory_incomplete",
                            "message": (
                                f"{rendered[kind]} élément(s) HTML pour "
                                f"{expected[page_number][kind]} attendu(s)"
                            ),
                        }
                    )
                elif rendered[kind] > expected[page_number][kind]:
                    page_issues.append(
                        {
                            "page": page_number,
                            "code": f"{kind}_inventory_unexpected",
                            "message": (
                                f"{rendered[kind]} élément(s) HTML pour "
                                f"{expected[page_number][kind]} attendu(s)"
                            ),
                        }
                    )

            if (
                not _html_page_has_content(node)
                and page_number <= len(source)
                and _source_page_has_content(source.load_page(page_number - 1))
            ):
                page_issues.append(
                    {
                        "page": page_number,
                        "code": "source_content_missing",
                        "message": "Le PDF contient du contenu mais la page HTML est vide",
                    }
                )
            issues.extend(page_issues)
            pages.append(
                {
                    "page": page_number,
                    "expected": dict(expected[page_number]),
                    "rendered": dict(rendered),
                    "status": "failed" if page_issues else "passed",
                }
            )

    region_links = audit_region_links(
        root, document, regions or [], issues, corrections
    )
    failed_pages = {issue["page"] for issue in issues}
    for page in pages:
        page["status"] = "failed" if page["page"] in failed_pages else "passed"
    return {
        "status": "failed" if issues else "passed",
        "pages_total": len(document.pages),
        "pages_checked": len(pages),
        "issues": issues,
        "pages": pages,
        "region_links": region_links,
    }
