"""Contrat et persistance du registre de sources.

Le manifeste du corpus reste mécanique. Ce module conserve les revendications
dérivées dans un fichier voisin, relié à l'empreinte SHA-256 du PDF.
"""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from .constants import CATALOG, CATALOG_SCHEMA_VERSION
from .validation import CatalogValidationError, validate_catalog


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_skeleton(
    manifest: dict[str, Any],
    *,
    manifest_path: Path | None = None,
    work: Path | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Construit les entrées retenues sans inventer une identité bibliographique."""
    from .identity import lookup_for_entry

    observed_at = now or utc_now()
    entries = []
    for source in sorted(
        (entry for entry in manifest["documents"] if entry.get("included")),
        key=lambda entry: entry["name"].casefold(),
    ):
        lookup = lookup_for_entry(source, work)
        identifier_proofs = lookup.pop("identifier_proofs", {})
        entries.append(
            {
                "source_sha256": source["sha256"],
                "file_name": source["name"],
                "document_kind": lookup["document_kind"],
                "lookup": lookup,
                "bibliography": {
                    "title": None,
                    "authors": [],
                    "language": None,
                    "publisher": None,
                    "identifiers": lookup["identifiers"],
                    "provenance": [
                        item["proof"]
                        for values in identifier_proofs.values()
                        for item in values
                    ],
                },
                "temporality": {
                    "work_first_published": None,
                    "edition_published": None,
                    "content_revision": None,
                },
                "provider_observations": [],
                "resolution": {"status": "not_queried", "candidate_id": None, "proof": None},
                "editorial_review": {
                    "status": "not_assessable",
                    "reviewed_at": observed_at[:10],
                    "reason": "Enrichissement et revue éditoriale non exécutés.",
                },
                "commercial_observations": [],
            }
        )
    catalog = {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "manifest_sha256": _sha256_bytes(manifest_path) if manifest_path else None,
        "generated_at": observed_at,
        "documents": entries,
    }
    issues = validate_catalog(catalog, manifest)
    if issues:
        raise CatalogValidationError("; ".join(issues))
    return catalog


def load_catalog(path: Path = CATALOG) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_catalog(catalog: dict[str, Any], path: Path = CATALOG) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def verify_catalog(catalog: dict[str, Any], manifest: dict[str, Any]) -> None:
    issues = validate_catalog(catalog, manifest)
    if issues:
        raise CatalogValidationError("\n".join(issues))


def entry_fingerprint(entry: dict[str, Any]) -> str:
    """Empreinte de l'entrée projetée, indépendante de l'ordre JSON."""
    payload = json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def stable_projection(entry: dict[str, Any]) -> dict[str, Any]:
    """Projection sans texte commercial ni score d'autorité global."""
    bibliography = entry.get("bibliography", {})
    temporal = entry.get("temporality", {})
    editorial = entry.get("editorial_review", {})
    return {
        "source_sha256": entry["source_sha256"],
        "file_name": entry["file_name"],
        "document_kind": entry.get("document_kind", "unknown"),
        "resolution_status": entry.get("resolution", {}).get("status"),
        "bibliography": {
            "title": bibliography.get("title"),
            "authors": bibliography.get("authors", []),
            "language": bibliography.get("language"),
            "publisher": bibliography.get("publisher"),
            "identifiers": bibliography.get("identifiers", {}),
            "provenance": bibliography.get("provenance", []),
        },
        "temporality": {
            "work_first_published": temporal.get("work_first_published"),
            "edition_published": temporal.get("edition_published"),
            "content_revision": temporal.get("content_revision"),
        },
        "editorial_review": {
            "status": editorial.get("status"),
            "reviewed_at": editorial.get("reviewed_at"),
            "domains": editorial.get("domains", []),
            "authority_basis": editorial.get("authority_basis"),
            "review_flags": editorial.get("review_flags", []),
            "proof": editorial.get("proof"),
        },
        "source_catalog_schema_version": CATALOG_SCHEMA_VERSION,
        "source_catalog_entry_sha256": entry_fingerprint(entry),
    }
