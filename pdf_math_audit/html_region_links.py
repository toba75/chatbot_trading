from __future__ import annotations

from typing import Any

from docling_core.types.doc import DocItemLabel, DoclingDocument


def audit_region_links(
    root: Any,
    document: DoclingDocument,
    regions: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    corrections: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Recoupe l'identité région, Docling et DOM de chaque preuve liée."""
    text_by_ref = {item.self_ref: item for item in document.texts}
    correction_by_region = {
        region_id: record
        for record in corrections or []
        if record.get("status") == "accepted"
        for region_id in record.get("region_ids", [])
    }
    links = []
    for region in regions:
        if (
            region.get("candidate_link_status") != "linked"
            or region.get("verdict") == "non_verifiable"
        ):
            continue
        correction = correction_by_region.get(region.get("region_id"))
        if correction is not None:
            link = _audit_corrected_link(
                root, text_by_ref, region, correction, issues
            )
            if link is not None:
                links.append(link)
            continue
        ref = region.get("docling_ref")
        charspan = region.get("candidate_charspan")
        candidate_text = region.get("candidate_text")
        item = text_by_ref.get(ref) if isinstance(ref, str) else None
        derived_charspan = _mapped_candidate_span(ref, charspan, corrections or [])
        valid_span = (
            isinstance(derived_charspan, list)
            and len(derived_charspan) == 2
            and all(isinstance(bound, int) for bound in derived_charspan)
            and item is not None
            and 0 <= derived_charspan[0] < derived_charspan[1] <= len(item.text)
        )
        if (
            not isinstance(ref, str)
            or not valid_span
            or not isinstance(candidate_text, str)
            or item.text[derived_charspan[0] : derived_charspan[1]] != candidate_text
        ):
            issues.append(_identity_issue(region))
            continue
        dom_charspan = (
            [0, len(item.text)]
            if item.label == DocItemLabel.FORMULA
            else derived_charspan
        )
        locus = f"{dom_charspan[0]}:{dom_charspan[1]}"
        selector = (
            f"math[@data-docling-ref='{ref}']"
            f"[@data-docling-charspan='{locus}']"
        )
        all_nodes = root.xpath(f"//{selector}")
        page_nodes = root.xpath(f"//*[@id='page-{region['page']}']//{selector}")
        status = _link_status(all_nodes, page_nodes)
        links.append(
            {
                "region_id": region["region_id"],
                "page": region["page"],
                "docling_ref": ref,
                "candidate_charspan": charspan,
                "dom_charspan": dom_charspan,
                "dom_selector": selector,
                "matches": len(all_nodes),
                "status": status,
            }
        )
        if status != "matched":
            _append_status_issue(region, status, len(all_nodes), issues)
    return links


def _mapped_candidate_span(
    ref: Any,
    charspan: Any,
    corrections: list[dict[str, Any]],
) -> list[int] | None:
    if (
        not isinstance(ref, str)
        or not isinstance(charspan, list)
        or len(charspan) != 2
        or not all(isinstance(bound, int) for bound in charspan)
    ):
        return None
    start, end = charspan
    shift = 0
    relevant = sorted(
        (
            record
            for record in corrections
            if record.get("status") == "accepted"
            and record.get("docling_ref") == ref
        ),
        key=lambda record: record["charspan"][0],
    )
    for record in relevant:
        correction_start, correction_end = record["charspan"]
        if correction_end <= start:
            shift += len(record["after"]) - (correction_end - correction_start)
        elif correction_start < end:
            return None
    return [start + shift, end + shift]


def _audit_corrected_link(
    root: Any,
    text_by_ref: dict[str, Any],
    region: dict[str, Any],
    correction: dict[str, Any],
    issues: list[dict[str, Any]],
) -> dict[str, Any] | None:
    ref = correction.get("derived_docling_ref") or correction.get("docling_ref")
    charspan = correction.get("derived_charspan")
    target_id = correction.get("target_id")
    after = correction.get("after")
    item = text_by_ref.get(ref) if isinstance(ref, str) else None
    proof = next(
        (
            value
            for value in correction.get("source_proofs", [])
            if value.get("region_id") == region.get("region_id")
        ),
        None,
    )
    valid_span = (
        isinstance(charspan, list)
        and len(charspan) == 2
        and all(isinstance(bound, int) for bound in charspan)
        and item is not None
        and 0 <= charspan[0] < charspan[1] <= len(item.text)
    )
    valid_proof = (
        isinstance(proof, dict)
        and proof.get("candidate_charspan") == region.get("candidate_charspan")
        and proof.get("candidate_text") == region.get("candidate_text")
    )
    if (
        not isinstance(ref, str)
        or not isinstance(target_id, str)
        or not isinstance(after, str)
        or not valid_span
        or item.text[charspan[0] : charspan[1]] != after
        or not valid_proof
    ):
        issues.append(_identity_issue(region))
        return None

    locus = f"{charspan[0]}:{charspan[1]}"
    selector = (
        f"math[@data-correction-id='{target_id}']"
        f"[@data-docling-ref='{ref}']"
        f"[@data-docling-charspan='{locus}']"
    )
    all_nodes = root.xpath(f"//{selector}")
    page_nodes = root.xpath(f"//*[@id='page-{region['page']}']//{selector}")
    status = _link_status(all_nodes, page_nodes)
    link = {
        "region_id": region["region_id"],
        "page": region["page"],
        "docling_ref": ref,
        "candidate_charspan": region["candidate_charspan"],
        "dom_charspan": charspan,
        "dom_selector": selector,
        "matches": len(all_nodes),
        "status": status,
    }
    if status != "matched":
        _append_status_issue(region, status, len(all_nodes), issues)
    return link


def _identity_issue(region: dict[str, Any]) -> dict[str, Any]:
    return {
        "page": region["page"],
        "code": "linked_math_identity_missing",
        "message": (
            f"La région {region['region_id']} est liée sans identité "
            "Docling et charspan complets"
        ),
    }


def _link_status(all_nodes: list[Any], page_nodes: list[Any]) -> str:
    if len(all_nodes) == 1 and len(page_nodes) == 1:
        return "matched"
    if len(all_nodes) == 1:
        return "wrong_page"
    if not all_nodes:
        return "missing"
    return "duplicated"


def _append_status_issue(
    region: dict[str, Any],
    status: str,
    matches: int,
    issues: list[dict[str, Any]],
) -> None:
    code = {
        "missing": "linked_math_missing",
        "wrong_page": "linked_math_page_mismatch",
        "duplicated": "linked_math_duplicated",
    }[status]
    issues.append(
        {
            "page": region["page"],
            "code": code,
            "message": (
                f"La région {region['region_id']} possède {matches} "
                "nœud(s) MathML correspondant(s) dans le DOM"
            ),
        }
    )
