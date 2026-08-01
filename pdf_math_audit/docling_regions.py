from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from docling_core.types.doc import DocItemLabel, DoclingDocument


@dataclass(frozen=True)
class Region:
    region_id: str
    kind: str
    docling_ref: str
    provenance_index: int | None
    page: int | None
    bbox: tuple[float, float, float, float] | None
    container_bbox: tuple[float, float, float, float] | None
    charspan: tuple[int, int]
    candidate_text: str
    reason: dict[str, str] | None = None
    localization_method: str | None = None


def _reason(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _provenance(
    document: DoclingDocument, item: Any, provenance_index: int
) -> tuple[int | None, tuple[float, float, float, float] | None, dict[str, str] | None]:
    provenance = item.prov[provenance_index]
    page = document.pages.get(provenance.page_no)
    if page is None:
        return (
            provenance.page_no,
            None,
            _reason(
                "docling_page_missing",
                f"La page Docling {provenance.page_no} n’existe pas",
            ),
        )
    bbox = provenance.bbox.to_top_left_origin(page.size.height)
    coordinates = tuple(float(value) for value in bbox.as_tuple())
    left, top, right, bottom = coordinates
    if not (
        page.size.width > 0
        and page.size.height > 0
        and 0 <= left < right <= page.size.width
        and 0 <= top < bottom <= page.size.height
    ):
        return (
            provenance.page_no,
            coordinates,
            _reason(
                "docling_bbox_outside_page",
                "La boîte Docling n’est pas contenue dans la page déclarée",
            ),
        )
    return provenance.page_no, coordinates, None


def _formula_regions(document: DoclingDocument) -> list[Region]:
    regions = []
    for item in document.texts:
        if item.label != DocItemLabel.FORMULA:
            continue
        if not item.prov:
            regions.append(
                Region(
                    region_id=f"{item.self_ref}:formula",
                    kind="formula",
                    docling_ref=item.self_ref,
                    provenance_index=None,
                    page=None,
                    bbox=None,
                    container_bbox=None,
                    charspan=(0, len(item.text)),
                    candidate_text=item.text,
                    reason=_reason(
                        "formula_provenance_missing",
                        "La formule Docling n’a aucune provenance",
                    ),
                )
            )
            continue
        for provenance_index, provenance in enumerate(item.prov):
            page, bbox, reason = _provenance(document, item, provenance_index)
            regions.append(
                Region(
                    region_id=f"{item.self_ref}:formula:{provenance_index}",
                    kind="formula",
                    docling_ref=item.self_ref,
                    provenance_index=provenance_index,
                    page=page,
                    bbox=bbox,
                    container_bbox=None,
                    charspan=provenance.charspan,
                    candidate_text=item.text[slice(*provenance.charspan)],
                    reason=reason,
                )
            )
    return regions


def _delimited_spans(
    text: str,
) -> tuple[list[tuple[tuple[int, int], dict[str, str] | None]], list[tuple[int, int]]]:
    delimiters = [
        (match.start(), match.end()) for match in re.finditer(r"(?<!\\)\$+", text)
    ]
    paired = []
    for index in range(0, len(delimiters) - 1, 2):
        opening = delimiters[index]
        closing = delimiters[index + 1]
        reason = None
        if opening[1] - opening[0] != 1 or closing[1] - closing[0] != 1:
            reason = _reason(
                "inline_math_delimiter_unsupported",
                "Seuls les délimiteurs mathématiques simples $…$ sont pris en charge",
            )
        paired.append(((opening[0], closing[1]), reason))
    unpaired = [(delimiters[-1][0], len(text))] if len(delimiters) % 2 else []
    return paired, unpaired


def _inline_region(
    document: DoclingDocument,
    item: Any,
    ordinal: int,
    charspan: tuple[int, int],
    delimiter_reason: dict[str, str] | None,
) -> Region:
    matching = [
        index
        for index, provenance in enumerate(item.prov)
        if provenance.charspan[0] <= charspan[0]
        and charspan[1] <= provenance.charspan[1]
    ]
    if len(matching) != 1:
        return Region(
            region_id=f"{item.self_ref}:inline:{ordinal}",
            kind="inline_math",
            docling_ref=item.self_ref,
            provenance_index=None,
            page=None,
            bbox=None,
            container_bbox=None,
            charspan=charspan,
            candidate_text=item.text[slice(*charspan)],
            reason=_reason(
                "inline_math_provenance_ambiguous",
                f"Le fragment inline correspond à {len(matching)} provenances",
            ),
        )
    provenance_index = matching[0]
    page, bbox, provenance_reason = _provenance(document, item, provenance_index)
    return Region(
        region_id=f"{item.self_ref}:inline:{ordinal}",
        kind="inline_math",
        docling_ref=item.self_ref,
        provenance_index=provenance_index,
        page=page,
        bbox=None,
        container_bbox=bbox,
        charspan=charspan,
        candidate_text=item.text[slice(*charspan)],
        reason=delimiter_reason
        or provenance_reason
        or _reason(
            "inline_math_bbox_unavailable",
            "La provenance couvre l’élément texte, pas le fragment inline",
        ),
    )


def _inline_regions(document: DoclingDocument) -> list[Region]:
    regions = []
    for item in document.texts:
        if item.label == DocItemLabel.FORMULA:
            continue
        pairs, unpaired = _delimited_spans(item.text)
        for ordinal, (charspan, delimiter_reason) in enumerate(pairs):
            regions.append(
                _inline_region(document, item, ordinal, charspan, delimiter_reason)
            )
        for delimiter in unpaired:
            regions.append(
                Region(
                    region_id=f"{item.self_ref}:inline:{len(pairs)}",
                    kind="inline_math",
                    docling_ref=item.self_ref,
                    provenance_index=None,
                    page=None,
                    bbox=None,
                    container_bbox=None,
                    charspan=delimiter,
                    candidate_text=item.text[slice(*delimiter)],
                    reason=_reason(
                        "inline_math_delimiter_unpaired",
                        "Le délimiteur mathématique inline n’est pas apparié",
                    ),
                )
            )
    return regions


def extract_regions(document: DoclingDocument) -> list[Region]:
    return _formula_regions(document) + _inline_regions(document)
