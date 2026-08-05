from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from docling_core.types.doc import DoclingDocument
from lxml import html as lxml_html

from experiments.paddle_formula_spike.experiment import load_json
from pdf_math_audit.correction_targets import TEXT_REF
from pdf_math_audit.derived_document import derive_document_and_page_html


def accepted_source_record(record: dict[str, Any]) -> dict[str, Any]:
    region = record["source_region"]
    return {
        "target_id": record["target_id"],
        "kind": "replacement",
        "region_ids": [record["region_id"]],
        "region_id": record["region_id"],
        "page": record["page"],
        "docling_ref": region["docling_ref"],
        "charspan": region["candidate_charspan"],
        "before": record["candidate_text"],
        "source_tokens": record["source_tokens"],
        "source_signature": record["source_signature"],
        "status": "accepted",
        "proposal": record["paddle_latex"],
        "proposal_tokens": record["paddle_tokens"],
        "proposal_signature": record["paddle_signature"],
        "after": record["after"],
        "mathml": record["mathml"],
    }


def audit_html(
    corrections_path: Path,
    document_path: Path,
    output_path: Path,
    *,
    source_results_path: Path | None = None,
    html_path: Path | None = None,
) -> dict[str, Any]:
    corrections = load_json(corrections_path)
    accepted = [record for record in corrections["records"] if record["status"] == "accepted"]
    additional = []
    if source_results_path is not None:
        additional = [
            accepted_source_record(record)
            for record in load_json(source_results_path)["records"]
            if record["applicable"]
        ]
        accepted.extend(additional)
    local = [record for record in accepted if record["kind"] == "replacement"]
    document = DoclingDocument.model_validate_json(document_path.read_bytes())
    proof_mismatch = [
        record["target_id"]
        for record in local
        if record.get("proposal_tokens") != record.get("source_tokens")
        or record.get("proposal_signature") != record.get("source_signature")
    ]
    source_locus_mismatch = []
    for record in local:
        match = TEXT_REF.fullmatch(str(record.get("docling_ref", "")))
        span = record.get("charspan")
        if (
            match is None
            or not isinstance(span, list)
            or document.texts[int(match.group(1))].text[span[0] : span[1]]
            != record.get("before")
        ):
            source_locus_mismatch.append(record["target_id"])
    _derived, html_bytes = derive_document_and_page_html(document, accepted)
    if html_path is not None:
        html_path.write_bytes(html_bytes)
    root = lxml_html.fromstring(html_bytes)
    missing = []
    wrong_page = []
    for record in local:
        matches = root.xpath(f"//*[@data-correction-id='{record['target_id']}']")
        if len(matches) != 1:
            missing.append(record["target_id"])
            continue
        pages = matches[0].xpath("ancestor::div[starts-with(@id, 'page-')][1]/@id")
        if pages != [f"page-{record['page']}"]:
            wrong_page.append(record["target_id"])
    page_85 = [record for record in local if record["page"] == 85]
    dollar_contexts = []
    for text_node in root.xpath("//text()[contains(., '$')]"):
        parent = text_node.getparent()
        if parent is None or parent.xpath(
            "ancestor-or-self::math | ancestor-or-self::style | ancestor-or-self::script"
        ):
            continue
        context = " ".join(str(text_node).split())
        if context and context not in dollar_contexts:
            dollar_contexts.append(context)
    result = {
        "accepted_local": len(local),
        "additional_local": len(additional),
        "proof_mismatch": proof_mismatch,
        "source_locus_mismatch": source_locus_mismatch,
        "localized_once": len(local) - len(missing),
        "missing_or_duplicated": missing,
        "wrong_page": wrong_page,
        "page_85": {
            "accepted_local": len(page_85),
            "localized_once": sum(
                len(root.xpath(f"//*[@data-correction-id='{record['target_id']}']")) == 1
                for record in page_85
            ),
            "targets": [record["target_id"] for record in page_85],
        },
        "visible_dollar_contexts": dollar_contexts,
    }
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result
