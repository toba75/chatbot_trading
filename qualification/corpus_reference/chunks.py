"""Contrat de l'index RAG : chunks de texte avec drapeaux de preuve par formule.

Un chunk est une suite d'items Docling du corps, joints par des sauts de ligne,
rompue au changement de page, à chaque titre de section et au-delà d'un budget
de caractères. Chaque formule — item FORMULA entier ou span inline ``$…$`` —
porte un drapeau dérivé du rapport de qualification et une provenance de
citation (page, boîte TOPLEFT) permettant de produire le crop source.

Sémantique des drapeaux, mesurée avant d'être fixée (voir
docs/rag/chunk-contract.md) :
- ``contradicted`` : au moins une région source liée contredit la formule ;
- ``proven`` : des régions conformes couvrent l'intégralité des caractères
  effectifs de la formule, sans aucune contradiction — la distribution réelle
  est bimodale (couverture 1,0 ou < 0,55), aucun seuil arbitraire n'est requis ;
- ``corroborated`` : réservé à l'accord d'un second modèle mesuré par l'étape 6
  du plan 004 ; jamais émis par cet exporteur ;
- ``unverified`` : tout le reste, détail des preuves partielles conservé.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from docling_core.types.doc import ContentLayer, DocItemLabel, DoclingDocument

from pdf_math_audit.development import (
    DEVELOPMENT_ORIGINS,
    develop_document,
    item_development_origin,
    operation_kind,
    pdf_supplement_records,
    recipe_from_operations,
    recipe_sha256,
)
from pdf_math_audit.inline_math import carries_inline_math, inline_math_spans
from qualification.corpus_reference.manifest import MANIFEST
from qualification.corpus_reference.coverage import WORK
from qualification.source_catalog.registry import (
    CATALOG,
    load_catalog,
    stable_projection,
    verify_catalog,
)

SCHEMA_VERSION = 2
FLAGS = ("proven", "corroborated", "unverified", "contradicted")
CHUNK_BUDGET_CHARACTERS = 1_800
_INEFFECTIVE_CHARACTERS = frozenset(" \t$")


def _top_left_bbox(
    item: Any, document: DoclingDocument
) -> tuple[int, list[float]] | None:
    """Page et boîte TOPLEFT de l'item, ou None : certains artefacts de
    conversion (marqueurs d'emplacement Kindle) sont des items du corps sans
    provenance — leur texte est conservé, leur citation se replie sur le chunk."""
    if not item.prov:
        return None
    provenance = item.prov[0]
    page = int(provenance.page_no)
    height = document.pages[page].size.height
    box = provenance.bbox.to_top_left_origin(height)
    return page, [box.l, box.t, box.r, box.b]


def _linked_sources(
    report: dict[str, Any], operations: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    sources: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    derived_refs = {
        operation.get("docling_ref"): operation.get("derived_docling_ref")
        for operation in operations
        if operation.get("operation") == "correction"
        and operation.get("docling_ref")
        and operation.get("derived_docling_ref")
    }
    for region in report["alignment"]["pdf_source_math_regions"]:
        if (
            region.get("candidate_link_status") == "linked"
            and region.get("docling_ref")
            and region.get("candidate_charspan")
        ):
            source = region
            derived_ref = derived_refs.get(region["docling_ref"])
            if derived_ref:
                source = region | {"docling_ref": derived_ref}
            sources[source["docling_ref"]].append(source)
    return sources


def _item_origin(item: Any, operations: list[dict[str, Any]]) -> str:
    for operation in operations:
        reference = operation.get("derived_docling_ref") or operation.get("docling_ref")
        if reference != item.self_ref:
            continue
        if operation.get("operation") == "correction":
            return "correction"
        if operation_kind(operation) == "pdf_supplement":
            return "pdf_supplement"
    return item_development_origin(item)


def _body_items(document: DoclingDocument) -> list[Any]:
    return [
        item
        for item, _level in document.iterate_items()
        if item.content_layer == ContentLayer.BODY and hasattr(item, "text")
    ]


def _region_boxes(report: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    boxes: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for region in report["alignment"]["regions"]:
        if region.get("charspan") and region.get("bbox"):
            boxes[region["docling_ref"]].append(region)
    return boxes


def _overlaps(span: tuple[int, int], other: list[int]) -> bool:
    return other[1] > span[0] and other[0] < span[1]


def _flag(
    sources: list[dict[str, Any]], span: tuple[int, int], text: str
) -> tuple[str, dict[str, Any]]:
    """Le drapeau suit le champ ``verdict`` du pipeline, seule autorité : une
    région ``missing`` porte le verdict ``contradicted`` (la transcription a
    perdu des jetons prouvés) et doit contredire, pas rester non vérifiée."""
    overlapping = [s for s in sources if _overlaps(span, s["candidate_charspan"])]
    statuses = collections.Counter(s.get("verdict") for s in overlapping)
    matching = [
        s for s in overlapping if s.get("verdict") == "conformant_within_scope"
    ]
    effective = [
        position
        for position in range(span[0], span[1])
        if text[position - span[0]] not in _INEFFECTIVE_CHARACTERS
    ]
    covered: set[int] = set()
    for source in matching:
        start, end = source["candidate_charspan"]
        covered.update(range(max(start, span[0]), min(end, span[1])))
    coverage = (
        sum(1 for position in effective if position in covered) / len(effective)
        if effective
        else None
    )
    evidence = {
        "conformant": statuses.get("conformant_within_scope", 0),
        "contradicted": statuses.get("contradicted", 0),
        "other": len(overlapping)
        - statuses.get("conformant_within_scope", 0)
        - statuses.get("contradicted", 0),
        "coverage": coverage,
    }
    if statuses.get("contradicted"):
        return "contradicted", evidence
    if matching and coverage == 1.0:
        return "proven", evidence
    return "unverified", evidence


def _formula_provenance(
    item: Any,
    document: DoclingDocument,
    item_span: tuple[int, int],
    boxes: dict[str, list[dict[str, Any]]],
    fallback: dict[str, Any],
) -> dict[str, Any]:
    """Boîte de citation, du plus précis au plus large, précision déclarée.

    Une région Docling n'est retenue que si son span CONTIENT la formule : les
    appariements naïfs de dollars du rapport peuvent produire des régions à
    cheval sur de la prose, et un simple chevauchement citerait la mauvaise
    boîte. À défaut, la boîte de l'item ; à défaut, celle du chunk.
    """
    for region in boxes.get(item.self_ref, ()):
        if (
            region["charspan"][0] <= item_span[0]
            and region["charspan"][1] >= item_span[1]
        ):
            return {
                "page": region["page"],
                "bbox": region["bbox"],
                "precision": "region",
            }
    located = _top_left_bbox(item, document)
    if located is not None:
        page, bbox = located
        return {"page": page, "bbox": bbox, "precision": "item"}
    return {
        "page": fallback["page"],
        "bbox": fallback["bbox"],
        "precision": "chunk",
    }


def _item_formulas(
    item: Any,
    document: DoclingDocument,
    offset: int,
    origin: str,
    sources: dict[str, list[dict[str, Any]]],
    boxes: dict[str, list[dict[str, Any]]],
    fallback: dict[str, Any],
) -> list[dict[str, Any]]:
    if item.label == DocItemLabel.FORMULA:
        spans = [(0, len(item.text), item.text, "display")]
    elif carries_inline_math(item):
        spans = [
            (start, end, item.text[start:end], "inline")
            for start, end, _latex in inline_math_spans(item.text)
        ]
    else:
        return []
    formulas = []
    for start, end, text, kind in spans:
        flag, evidence = _flag(sources.get(item.self_ref, []), (start, end), text)
        formulas.append(
            {
                "kind": kind,
                "charspan": [offset + start, offset + end],
                "docling_ref": item.self_ref,
                "item_charspan": [start, end],
                "origin": origin,
                "flag": flag,
                "evidence": evidence,
                "provenance": _formula_provenance(
                    item, document, (start, end), boxes, fallback
                ),
            }
        )
    return formulas


def validate_chunk(chunk: dict[str, Any]) -> None:
    """Refuse un chunk dont le contenu ou la preuve est incomplet."""
    items = chunk.get("items")
    if chunk.get("text") and (not isinstance(items, list) or not items):
        raise ValueError(f"Contenu sans origine dans {chunk['chunk_id']}")
    for item in items or []:
        if not isinstance(item, dict):
            raise ValueError(f"Item sans origine valide dans {chunk['chunk_id']}")
        if item.get("origin") not in DEVELOPMENT_ORIGINS:
            raise ValueError(
                f"Item sans origine valide dans {chunk['chunk_id']} : "
                f"{item.get('origin')!r}"
            )
    for formula in chunk["formulas"]:
        if formula.get("origin") not in DEVELOPMENT_ORIGINS:
            raise ValueError(
                f"Formule sans origine valide dans {chunk['chunk_id']} : "
                f"{formula.get('origin')!r}"
            )
        if formula.get("flag") not in FLAGS:
            raise ValueError(
                f"Formule sans drapeau valide dans {chunk['chunk_id']} : "
                f"{formula.get('flag')!r}"
            )
        provenance = formula.get("provenance") or {}
        if not provenance.get("page") or not provenance.get("bbox"):
            raise ValueError(
                f"Formule sans provenance de citation dans {chunk['chunk_id']}"
            )
    source = chunk.get("source")
    if source is not None and (
        not isinstance(source.get("source_sha256"), str)
        or source.get("source_catalog_schema_version") != 1
    ):
        raise ValueError(f"Projection de source invalide dans {chunk['chunk_id']}")


def build_chunks(
    document: DoclingDocument,
    report: dict[str, Any],
    entry: dict[str, Any],
    source_projection: dict[str, Any] | None = None,
    development_operations: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    if source_projection is not None and source_projection.get("source_sha256") != entry["sha256"]:
        raise ValueError("La projection de source ne correspond pas au manifeste")
    operations = development_operations or []
    sources = _linked_sources(report, operations)
    boxes = _region_boxes(report)
    chunks: list[dict[str, Any]] = []
    unlocatable: list[str] = []
    current: list[tuple[Any, tuple[int, list[float]] | None]] = []

    def close() -> None:
        if not current:
            return
        texts = [item.text for item, _located in current]
        offsets = []
        cursor = 0
        for text in texts:
            offsets.append(cursor)
            cursor += len(text) + 1
        located = [loc for _item, loc in current if loc is not None]
        if not located:
            # Une suite d'items entièrement dépourvue de localisation (artefacts
            # de conversion) n'est pas citable : elle est écartée mais consignée
            # dans l'en-tête de l'export — observable, jamais silencieuse.
            unlocatable.extend(item.self_ref for item, _loc in current)
            current.clear()
            return
        page = located[0][0]
        union = [
            min(bbox[0] for _page, bbox in located),
            min(bbox[1] for _page, bbox in located),
            max(bbox[2] for _page, bbox in located),
            max(bbox[3] for _page, bbox in located),
        ]
        chunk = {
            "type": "chunk",
            "chunk_id": f"{entry['sha256'][:12]}:{len(chunks):05d}",
            "text": "\n".join(texts),
            "provenance": {"page": page, "bbox": union},
            "items": [
                {
                    "docling_ref": item.self_ref,
                    "label": str(item.label.value),
                    "charspan": [offset, offset + len(item.text)],
                    "origin": _item_origin(item, operations),
                }
                for (item, _located), offset in zip(current, offsets)
            ],
        }
        if source_projection is not None:
            chunk["source"] = source_projection
        chunk["formulas"] = [
            formula
            for (item, _located), offset in zip(current, offsets)
            for formula in _item_formulas(
                item,
                document,
                offset,
                _item_origin(item, operations),
                sources,
                boxes,
                chunk["provenance"],
            )
        ]
        validate_chunk(chunk)
        chunks.append(chunk)
        current.clear()

    for item in _body_items(document):
        if item.content_layer != ContentLayer.BODY:
            continue
        if not carries_inline_math(item) and item.label not in (
            DocItemLabel.FORMULA,
            DocItemLabel.CODE,
        ):
            continue
        if not item.text:
            continue
        located = _top_left_bbox(item, document)
        chunk_page = next(
            (loc[0] for _item, loc in current if loc is not None), None
        )
        length = sum(len(i.text) + 1 for i, _loc in current)
        if current and (
            (located is not None and chunk_page is not None and located[0] != chunk_page)
            or item.label == DocItemLabel.SECTION_HEADER
            or length + len(item.text) > CHUNK_BUDGET_CHARACTERS
        ):
            close()
        current.append((item, located))
    close()
    return chunks, unlocatable


def _development_operations(
    directory: Path, report: dict[str, Any]
) -> list[dict[str, Any]]:
    regions = report["alignment"]["pdf_source_math_regions"]
    supplements = pdf_supplement_records(regions)
    correction_path = directory / "corrections.json"
    if not correction_path.exists():
        correction = report.get("correction") or {}
        if correction.get("accepted", 0) or correction.get("status") in {
            "corrected",
            "failed",
        }:
            raise FileNotFoundError(
                "corrections.json absent alors que le rapport annonce une correction"
            )
        return supplements

    payload = json.loads(correction_path.read_text(encoding="utf-8"))
    records = payload.get("records")
    if not isinstance(records, list) or not all(
        isinstance(record, dict) for record in records
    ):
        raise ValueError("corrections.json sans liste de records valide")
    accepted = [record for record in records if record.get("status") == "accepted"]
    announced_accepted = (report.get("correction") or {}).get("accepted")
    if announced_accepted is not None and announced_accepted != len(accepted):
        raise ValueError("Le nombre de corrections acceptées diverge du rapport")
    payload_accepted = (payload.get("summary") or {}).get("accepted")
    if payload_accepted is not None and payload_accepted != len(accepted):
        raise ValueError("Le nombre de corrections acceptées diverge de corrections.json")
    recipe = payload.get("recipe")
    if recipe is not None:
        if not isinstance(recipe, dict) or recipe.get("schema_version") != 1:
            raise ValueError("Version de recette de développement inconnue")
        recipe_operations = recipe.get("operations")
        if not isinstance(recipe_operations, list) or not all(
            isinstance(operation, dict) for operation in recipe_operations
        ):
            raise ValueError("Recette de développement sans liste d'opérations")
        expected_ids = [record["region_id"] for record in supplements]
        actual_ids = [
            operation.get("region_id")
            for operation in recipe_operations
            if operation_kind(operation) == "pdf_supplement"
        ]
        if actual_ids != expected_ids or len(actual_ids) != len(set(actual_ids)):
            raise ValueError(
                "La recette de développement ne couvre pas exactement les "
                "suppléments du rapport"
            )
        expected_correction_ids = [record["target_id"] for record in accepted]
        actual_correction_ids = [
            operation.get("target_id")
            for operation in recipe_operations
            if operation.get("operation") == "correction"
        ]
        if actual_correction_ids != expected_correction_ids:
            raise ValueError(
                "La recette de développement ne couvre pas exactement les "
                "corrections acceptées"
            )
        if len(recipe_operations) != len(accepted) + len(supplements):
            raise ValueError("Le nombre d'opérations de la recette est incohérent")
        return recipe_operations

    return [*accepted, *supplements]


def _development_artifacts(
    document: DoclingDocument,
    operations: list[dict[str, Any]],
) -> tuple[DoclingDocument, dict[str, Any], str]:
    recipe = recipe_from_operations(operations)
    recipe_digest = recipe_sha256(recipe)
    developed, supplements = develop_document(document, operations)
    for record, item in supplements:
        record["derived_docling_ref"] = item.self_ref
        record["derived_charspan"] = [0, len(item.text)]
    return developed, recipe, recipe_digest


def export_book(
    entry: dict[str, Any],
    work: Path,
    catalog_entry: dict[str, Any] | None = None,
) -> collections.Counter[str]:
    directory = work / entry["sha256"][:12]
    native_bytes = (directory / "docling-document.json").read_bytes()
    native_sha256 = hashlib.sha256(native_bytes).hexdigest()
    document = DoclingDocument.model_validate_json(native_bytes)
    report = json.loads((directory / "report.json").read_text(encoding="utf-8"))
    announced_native_sha256 = (
        report.get("docling_document", {}).get("sha256")
        or report.get("contract", {}).get("docling_document_sha256")
    )
    if announced_native_sha256 is not None and announced_native_sha256 != native_sha256:
        raise ValueError("L'empreinte du document natif diverge du rapport")
    operations = _development_operations(directory, report)
    developed, recipe, recipe_digest = _development_artifacts(document, operations)
    announced_recipe_sha256 = (report.get("development") or {}).get("recipe_sha256")
    if announced_recipe_sha256 is not None and announced_recipe_sha256 != recipe_digest:
        raise ValueError("L'empreinte de la recette diverge du rapport")
    source_projection = stable_projection(catalog_entry) if catalog_entry else None
    if source_projection and source_projection["source_sha256"] != entry["sha256"]:
        raise ValueError("Le registre de sources ne correspond pas au manifeste")
    chunks, unlocatable = build_chunks(
        developed, report, entry, source_projection, operations
    )
    origin_counts = collections.Counter(
        item["origin"] for chunk in chunks for item in chunk["items"]
    )
    header = {
        "type": "header",
        "schema_version": SCHEMA_VERSION,
        "contract": {
            "analyzer_version": report.get("analyzer_version"),
            "capability_profile": report.get("capability_profile"),
        },
        "document": {
            "name": entry["name"],
            "sha256": entry["sha256"],
            "native_document_sha256": native_sha256,
        },
        "native_document_sha256": native_sha256,
        "recipe_sha256": recipe_digest,
        "development": {
            "recipe_schema_version": recipe["schema_version"],
            "recipe_sha256": recipe_digest,
            "operations": len(operations),
            "origin_counts": {
                origin: origin_counts.get(origin, 0)
                for origin in DEVELOPMENT_ORIGINS
            },
        },
        "chunks": len(chunks),
        "unlocatable_items": unlocatable,
        "origin_counts": {
            origin: origin_counts.get(origin, 0) for origin in DEVELOPMENT_ORIGINS
        },
    }
    if source_projection is not None:
        header["source_catalog"] = {
            "schema_version": source_projection["source_catalog_schema_version"],
            "entry_sha256": source_projection["source_catalog_entry_sha256"],
        }
    with (directory / "chunks.jsonl").open("w", encoding="utf-8") as output:
        for record in [header, *chunks]:
            output.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    counts = collections.Counter(
        formula["flag"] for chunk in chunks for formula in chunk["formulas"]
    )
    counts.update({f"origin:{origin}": count for origin, count in origin_counts.items()})
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["export"])
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--work", type=Path, default=WORK)
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--books", type=int, default=5)
    arguments = parser.parse_args(argv)
    manifest = json.loads(arguments.manifest.read_text(encoding="utf-8"))
    catalog_by_sha: dict[str, dict[str, Any]] = {}
    # Les tests et les consommateurs peuvent fournir un manifeste isolé sans
    # réutiliser par accident le registre du corpus réel.
    if arguments.manifest.resolve() == MANIFEST.resolve():
        if not arguments.catalog.exists():
            raise FileNotFoundError(
                f"Registre de sources requis pour le corpus réel : {arguments.catalog}"
            )
        catalog = load_catalog(arguments.catalog)
        verify_catalog(catalog, manifest)
        catalog_by_sha = {entry["source_sha256"]: entry for entry in catalog["documents"]}

    qualified = [
        entry
        for entry in sorted(manifest["documents"], key=lambda e: e["pages"])
        if entry["included"]
        and (arguments.work / entry["sha256"][:12] / "report.json").exists()
    ]
    totals: collections.Counter[str] = collections.Counter()
    failures = 0
    for entry in qualified[: arguments.books]:
        try:
            counts = export_book(entry, arguments.work, catalog_by_sha.get(entry["sha256"]))
        except Exception as error:
            failures += 1
            print(f"{entry['name'][:56]:58} ÉCHEC {type(error).__name__}: {error}")
            continue
        totals.update(counts)
        print(f"{entry['name'][:56]:58} {dict(counts)}")
    print(f"total : {dict(totals)}" + (f" | {failures} livre(s) en échec" if failures else ""))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
