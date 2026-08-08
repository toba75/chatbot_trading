from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any

from docling_core.types.doc import (
    BaseMeta,
    BoundingBox,
    ContentLayer,
    CoordOrigin,
    DocItemLabel,
    DoclingDocument,
    ProvenanceItem,
)

from pdf_math_audit.correction_targets import TEXT_REF


DEVELOPMENT_RECIPE_SCHEMA_VERSION = 1
DEVELOPMENT_ORIGINS = ("transcription", "correction", "pdf_supplement")
_META_ORIGIN = "rag__development_origin"


def operation_kind(operation: dict[str, Any]) -> str | None:
    """Retourne le nom stable d'une opération de la recette."""
    value = operation.get("kind") or operation.get("operation")
    return value if isinstance(value, str) else None


def item_development_origin(item: Any) -> str:
    """Retourne l'origine publiée d'un item Docling."""
    metadata = getattr(getattr(item, "meta", None), "model_extra", None) or {}
    if _META_ORIGIN not in metadata:
        return "transcription"
    origin = metadata.get(_META_ORIGIN)
    if origin not in DEVELOPMENT_ORIGINS:
        raise ValueError(f"Origine de développement invalide : {origin!r}")
    return origin


def set_item_development_origin(item: Any, origin: str) -> None:
    if origin not in DEVELOPMENT_ORIGINS:
        raise ValueError(f"Origine de développement inconnue : {origin}")
    metadata = item.meta.model_dump(exclude_none=True) if item.meta else {}
    metadata[_META_ORIGIN] = origin
    item.meta = BaseMeta(**metadata)


def strip_item_development_origins(document: DoclingDocument) -> None:
    """Retire les métadonnées de développement d'une copie d'export Markdown."""
    for item, _level in document.iterate_items():
        if item.meta is None:
            continue
        metadata = item.meta.model_dump(exclude_none=True)
        if _META_ORIGIN not in metadata:
            continue
        metadata.pop(_META_ORIGIN)
        item.meta = BaseMeta(**metadata) if metadata else None


def development_origin_counts(
    document: DoclingDocument, operations: list[dict[str, Any]]
) -> dict[str, int]:
    developed, _created = develop_document(document, operations)
    counts = {origin: 0 for origin in DEVELOPMENT_ORIGINS}
    for item, _level in developed.iterate_items():
        if item.content_layer != ContentLayer.BODY or not hasattr(item, "text"):
            continue
        counts[item_development_origin(item)] += 1
    return counts


def recipe_from_operations(operations: list[dict[str, Any]]) -> dict[str, Any]:
    """Construit la recette sérialisable à partir des opérations appliquées."""
    return {
        "schema_version": DEVELOPMENT_RECIPE_SCHEMA_VERSION,
        "operations": copy.deepcopy(operations),
    }


def recipe_sha256(recipe: dict[str, Any]) -> str:
    """Empreinte canonique de la recette, indépendante de sa mise en forme."""
    if recipe.get("schema_version") != DEVELOPMENT_RECIPE_SCHEMA_VERSION:
        raise ValueError("Version de recette de développement inconnue")
    operations = recipe.get("operations")
    if not isinstance(operations, list) or not all(
        isinstance(operation, dict) for operation in operations
    ):
        raise ValueError("Opérations de recette invalides")
    normalized_recipe = {
        "schema_version": recipe["schema_version"],
        "operations": [
            {
                key: copy.deepcopy(value)
                for key, value in operation.items()
                if key not in {"derived_docling_ref", "derived_charspan"}
            }
            for operation in operations
        ],
    }
    payload = json.dumps(
        normalized_recipe,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def pdf_supplement_records(
    regions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Transforme les régions PDF sans conteneur Docling en opérations.

    La conversion ne fabrique pas de contenu à partir d'un drapeau. Elle
    recopie uniquement le texte glyphique et les preuves déjà produits par le
    pipeline. Une région sélectionnée mais incomplète échoue explicitement.
    """
    selected = [
        region
        for region in regions
        if (region.get("candidate_link_reason") or {}).get("code")
        == "docling_text_container_missing"
    ]
    selected.sort(
        key=lambda region: (
            region.get("page", 0),
            (region.get("bbox") or [0.0, 0.0, 0.0, 0.0])[1],
            (region.get("bbox") or [0.0, 0.0, 0.0, 0.0])[0],
            region.get("region_id", ""),
        )
    )
    records: list[dict[str, Any]] = []
    seen_region_ids: set[str] = set()
    for region in selected:
        region_id = region.get("region_id")
        text = region.get("source_glyph_text")
        page = region.get("page")
        bbox = region.get("bbox")
        canonical_tokens = region.get("source_canonical_tokens")
        raw_tokens = region.get("source_tokens")
        if not isinstance(region_id, str) or not region_id:
            raise ValueError("Un supplément PDF n'a pas d'identifiant de région")
        if region_id in seen_region_ids:
            raise ValueError(f"Région de supplément dupliquée : {region_id}")
        if not isinstance(text, str) or not text:
            raise ValueError(f"Texte glyphique absent pour le supplément {region_id}")
        if not isinstance(page, int) or page <= 0:
            raise ValueError(f"Page invalide pour le supplément {region_id}")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError(f"Boîte PDF invalide pour le supplément {region_id}")
        try:
            numeric_bbox = [float(value) for value in bbox]
        except (TypeError, ValueError) as error:
            raise ValueError(f"Boîte PDF non numérique pour le supplément {region_id}") from error
        if (
            not all(math.isfinite(value) for value in numeric_bbox)
            or numeric_bbox[0] >= numeric_bbox[2]
            or numeric_bbox[1] >= numeric_bbox[3]
        ):
            raise ValueError(f"Boîte PDF dégénérée pour le supplément {region_id}")
        if canonical_tokens is not None and not isinstance(canonical_tokens, list):
            raise ValueError(f"Jetons canoniques invalides pour le supplément {region_id}")
        if raw_tokens is not None and not isinstance(raw_tokens, list):
            raise ValueError(f"Jetons bruts invalides pour le supplément {region_id}")
        if canonical_tokens:
            tokens = canonical_tokens
            token_basis = "source_canonical_tokens"
        elif raw_tokens:
            tokens = raw_tokens
            token_basis = "source_tokens"
        else:
            raise ValueError(f"Jetons PDF absents pour le supplément {region_id}")

        seen_region_ids.add(region_id)
        records.append(
            {
                "operation": "pdf_supplement",
                "kind": "pdf_supplement",
                "origin": "pdf_supplement",
                "status": "accepted",
                "target_id": region_id,
                "region_id": region_id,
                "page": page,
                "bbox": numeric_bbox,
                "before": "",
                "after": text,
                "source_text": text,
                "source_tokens": copy.deepcopy(tokens),
                "source_token_basis": token_basis,
                "source_signature": copy.deepcopy(
                    region.get("source_relation_signature") or []
                ),
                "source_proof": {
                    "region_id": region_id,
                    "page": page,
                    "bbox": numeric_bbox,
                    "source_glyph_text": text,
                    "source_canonical_tokens": copy.deepcopy(canonical_tokens),
                    "source_tokens_raw": copy.deepcopy(raw_tokens),
                    "source_token_basis": token_basis,
                    "source_tokens": copy.deepcopy(tokens),
                    "verdict": region.get("verdict"),
                    "semantic_status": region.get("semantic_status"),
                    "candidate_link_reason": copy.deepcopy(
                        region.get("candidate_link_reason")
                    ),
                },
            }
        )
    return records


def _validate_correction(operation: dict[str, Any]) -> tuple[int, int, int, str]:
    reference = operation.get("docling_ref")
    match = TEXT_REF.fullmatch(str(reference or ""))
    if match is None:
        raise ValueError("Référence Docling invalide après validation")
    charspan = operation.get("charspan")
    after = operation.get("after")
    if (
        not isinstance(charspan, list)
        or len(charspan) != 2
        or not all(isinstance(value, int) for value in charspan)
    ):
        raise ValueError("Charspan de correction invalide")
    if not isinstance(after, str):
        raise ValueError("Texte de correction invalide")
    return int(match.group(1)), charspan[0], charspan[1], after


def _apply_corrections(
    document: DoclingDocument,
    operations: list[dict[str, Any]],
) -> None:
    by_text: dict[int, list[dict[str, Any]]] = {}
    for operation in operations:
        kind = operation_kind(operation)
        if kind == "pdf_supplement":
            continue
        if kind == "formula_insertion":
            raise ValueError("Une formule sans ancrage Docling ne peut pas être publiée")
        index, start, end, _after = _validate_correction(operation)
        by_text.setdefault(index, []).append(operation)

    for index, records in by_text.items():
        if index < 0 or index >= len(document.texts):
            raise ValueError("Référence Docling hors document")
        node = document.texts[index]
        spans = sorted((record["charspan"] for record in records), key=lambda span: span[0])
        if any(left[1] > right[0] for left, right in zip(spans, spans[1:])):
            raise ValueError("Charspans de correction qui se chevauchent")
        for record in sorted(records, key=lambda item: item["charspan"][0], reverse=True):
            start, end = record["charspan"]
            if not (0 <= start < end <= len(node.text)):
                raise ValueError("Charspan de correction invalide")
            before = record.get("before")
            if before is not None and (
                not isinstance(before, str) or node.text[start:end] != before
            ):
                raise ValueError("Texte natif inattendu avant une correction")
            if node.label == DocItemLabel.FORMULA and [start, end] != [0, len(node.text)]:
                raise ValueError(
                    "Une formule Docling ne peut être remplacée que dans son intégralité"
                )
            node.text = node.text[:start] + record["after"] + node.text[end:]
        set_item_development_origin(node, "correction")


def _body_child_geometry(document: DoclingDocument, ref: Any) -> tuple[int, float, float] | None:
    node = ref.resolve(document)
    geometries = [
        (int(provenance.page_no), float(provenance.bbox.t), float(provenance.bbox.l))
        for provenance in getattr(node, "prov", [])
    ]
    pending = list(getattr(node, "children", []))
    while pending:
        child = pending.pop(0).resolve(document)
        geometries.extend(
            (int(provenance.page_no), float(provenance.bbox.t), float(provenance.bbox.l))
            for provenance in getattr(child, "prov", [])
        )
        pending.extend(getattr(child, "children", []))
    return min(geometries) if geometries else None


def _append_supplements(
    document: DoclingDocument,
    supplements: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], Any]]:
    created: list[tuple[dict[str, Any], Any]] = []
    for record in supplements:
        page = record["page"]
        if page not in document.pages:
            raise ValueError(f"Page absente pour le supplément {record['region_id']}")
        left, top, right, bottom = record["bbox"]
        item = document.add_formula(
            text=record["after"],
            orig=record["after"],
            prov=ProvenanceItem(
                page_no=page,
                bbox=BoundingBox(
                    l=left,
                    t=top,
                    r=right,
                    b=bottom,
                    coord_origin=CoordOrigin.TOPLEFT,
                ),
                charspan=(0, len(record["after"])),
            ),
        )
        set_item_development_origin(item, "pdf_supplement")
        created.append((record, item))

    if created:
        supplement_refs = list(document.body.children[-len(created) :])
        native_children = list(document.body.children[: -len(created)])
        document.body.children[:] = native_children
        for (record, item), supplement_reference in zip(
            created, supplement_refs, strict=True
        ):
            geometry = _body_child_geometry(document, supplement_reference)
            if geometry is None:
                raise ValueError(
                    f"Supplément sans géométrie après création : {record['region_id']}"
                )
            insertion = len(document.body.children)
            for index, existing_reference in enumerate(document.body.children):
                existing = _body_child_geometry(document, existing_reference)
                if existing is not None and existing > geometry:
                    insertion = index
                    break
            document.body.children.insert(insertion, supplement_reference)
    return created


def develop_document(
    document: DoclingDocument,
    operations: list[dict[str, Any]],
) -> tuple[DoclingDocument, list[tuple[dict[str, Any], Any]]]:
    """Applique une recette à une copie du document natif."""
    if not isinstance(operations, list):
        raise ValueError("La recette de développement doit être une liste")
    if not all(isinstance(operation, dict) for operation in operations):
        raise ValueError("Chaque opération de développement doit être un objet")
    for operation in operations:
        declared = operation.get("operation")
        if declared is not None and declared not in {"correction", "pdf_supplement"}:
            raise ValueError(f"Opération de développement inconnue : {declared}")
        kind = operation.get("kind")
        if declared == "correction" and kind == "pdf_supplement":
            raise ValueError("Opération de développement incohérente")
        if declared == "pdf_supplement" and kind not in {None, "pdf_supplement"}:
            raise ValueError("Opération de développement incohérente")
    derived = document.model_copy(deep=True)
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
    _apply_corrections(derived, corrections)
    created = _append_supplements(derived, supplements)
    return DoclingDocument.model_validate(derived.model_dump()), created
