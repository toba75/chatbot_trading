"""Validation structurelle du registre de sources versionné."""

from __future__ import annotations

from datetime import date
import re
from typing import Any

from .constants import (
    CATALOG_SCHEMA_VERSION,
    EDITORIAL_STATES,
    QUERY_STATES,
    RESOLUTION_STATES,
)

SHA256 = re.compile(r"^[0-9a-f]{64}$")


class CatalogValidationError(ValueError):
    """Le registre ne respecte pas son contrat versionné."""


def _proof(proof: Any, location: str, issues: list[str]) -> None:
    if not isinstance(proof, dict):
        issues.append(f"{location}: preuve absente")
        return
    kind = proof.get("kind")
    if kind not in {"source_text", "provider", "manual"}:
        issues.append(f"{location}: kind de preuve invalide")
    if kind == "provider" and not all(
        isinstance(proof.get(field), str) and proof[field]
        for field in ("provider", "resource_id", "observed_at")
    ):
        issues.append(f"{location}: preuve fournisseur incomplète")
    if kind == "source_text" and not isinstance(proof.get("locator"), dict):
        issues.append(f"{location}: localisation source absente")
    if kind == "manual" and not isinstance(proof.get("reviewer"), str):
        issues.append(f"{location}: réviseur absent")


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, tuple, set)):
        return any(_present(item) for item in value)
    if isinstance(value, dict):
        return any(_present(item) for item in value.values())
    return True


def _dated_value(value: Any, location: str, issues: list[str]) -> None:
    if value is None:
        return
    if not isinstance(value, dict) or not isinstance(value.get("value"), str):
        issues.append(f"{location}: date non structurée")
        return
    text = value["value"]
    try:
        date.fromisoformat(text[:10])
    except ValueError:
        try:
            if len(text) == 4:
                int(text)
            elif len(text) == 7:
                date.fromisoformat(f"{text}-01")
            else:
                raise ValueError
        except ValueError:
            issues.append(f"{location}: date invalide")
    _proof(value.get("proof"), f"{location}.proof", issues)


def _candidate(candidate: Any, location: str, issues: list[str]) -> None:
    if not isinstance(candidate, dict):
        issues.append(f"{location}: candidat non structuré")
        return
    if candidate.get("status") not in {"candidate", "accepted", "ambiguous", "rejected"}:
        issues.append(f"{location}.status: état invalide")
    if not isinstance(candidate.get("candidate_id"), str) or not candidate["candidate_id"]:
        issues.append(f"{location}.candidate_id: absent")
    rating = candidate.get("rating")
    if rating is not None:
        if not isinstance(rating, dict) or not isinstance(rating.get("average"), (int, float)) or not isinstance(rating.get("count"), int):
            issues.append(f"{location}.rating: moyenne et nombre de votes requis")
        elif rating["count"] < 0 or not 0 <= float(rating["average"]) <= 5:
            issues.append(f"{location}.rating: valeurs hors limites")
    if candidate.get("status") == "accepted":
        _proof(candidate.get("proof"), f"{location}.proof", issues)


def _document(entry: Any, location: str, issues: list[str], allow_unreviewed: bool) -> None:
    if not isinstance(entry, dict):
        issues.append(f"{location}: entrée non structurée")
        return
    source = entry.get("source_sha256")
    if not isinstance(source, str) or not SHA256.fullmatch(source):
        issues.append(f"{location}.source_sha256: empreinte invalide")
    if not isinstance(entry.get("file_name"), str) or not entry["file_name"]:
        issues.append(f"{location}.file_name: absent")
    lookup = entry.get("lookup")
    if not isinstance(lookup, dict) or not isinstance(lookup.get("title"), str):
        issues.append(f"{location}.lookup: titre de recherche absent")
    identity = entry.get("bibliography")
    if not isinstance(identity, dict):
        issues.append(f"{location}.bibliography: absente")
    else:
        provenance = identity.get("provenance", [])
        if not isinstance(provenance, list):
            issues.append(f"{location}.bibliography.provenance: liste attendue")
        for field in ("title", "authors", "language", "publisher", "identifiers"):
            if _present(identity.get(field)) and not provenance:
                issues.append(f"{location}.bibliography.{field}: valeur sans preuve")
                break
        for index, proof in enumerate(provenance):
            _proof(proof, f"{location}.bibliography.provenance[{index}]", issues)
    temporal = entry.get("temporality")
    if not isinstance(temporal, dict):
        issues.append(f"{location}.temporality: absente")
    else:
        for field in ("work_first_published", "edition_published", "content_revision"):
            _dated_value(temporal.get(field), f"{location}.temporality.{field}", issues)
        if temporal.get("edition_published") is not None and temporal.get("content_revision") is not None and temporal["edition_published"] == temporal["content_revision"]:
            issues.append(f"{location}: date d'édition confondue avec date de révision")
    observations = entry.get("provider_observations")
    accepted_candidate_ids: set[str] = set()
    if not isinstance(observations, list):
        issues.append(f"{location}.provider_observations: liste attendue")
    else:
        for index, observation in enumerate(observations):
            prefix = f"{location}.provider_observations[{index}]"
            if not isinstance(observation, dict) or observation.get("status") not in QUERY_STATES:
                issues.append(f"{prefix}.status: état invalide")
                continue
            if not isinstance(observation.get("provider"), str) or not observation["provider"]:
                issues.append(f"{prefix}.provider: absent")
            if not isinstance(observation.get("observed_at"), str):
                issues.append(f"{prefix}.observed_at: absent")
            for candidate_index, candidate in enumerate(observation.get("candidates", [])):
                _candidate(candidate, f"{prefix}.candidates[{candidate_index}]", issues)
                if isinstance(candidate, dict) and candidate.get("status") == "accepted":
                    candidate_id = candidate.get("candidate_id")
                    if isinstance(candidate_id, str):
                        accepted_candidate_ids.add(candidate_id)
    resolution = entry.get("resolution")
    if not isinstance(resolution, dict) or resolution.get("status") not in RESOLUTION_STATES:
        issues.append(f"{location}.resolution.status: état invalide")
    elif resolution["status"] == "accepted":
        if not resolution.get("candidate_id"):
            issues.append(f"{location}.resolution.candidate_id: absent")
        elif resolution["candidate_id"] not in accepted_candidate_ids:
            issues.append(f"{location}.resolution.candidate_id: candidat accepté absent des observations")
        _proof(resolution.get("proof"), f"{location}.resolution.proof", issues)
    editorial = entry.get("editorial_review")
    if not isinstance(editorial, dict) or editorial.get("status") not in EDITORIAL_STATES:
        if not allow_unreviewed or not isinstance(editorial, dict) or editorial.get("status") != "unreviewed":
            issues.append(f"{location}.editorial_review.status: état invalide")
    elif editorial["status"] == "reviewed":
        for field in ("reviewed_at", "method", "justification", "limitations"):
            if not isinstance(editorial.get(field), str) or not editorial[field]:
                issues.append(f"{location}.editorial_review.{field}: absent")
        if not isinstance(editorial.get("domains"), list) or not editorial["domains"]:
            issues.append(f"{location}.editorial_review.domains: domaine requis")
        _proof(editorial.get("proof"), f"{location}.editorial_review.proof", issues)
    elif not isinstance(editorial.get("reviewed_at"), str) or not editorial.get("reason"):
        issues.append(f"{location}.editorial_review: raison et date requises")
    for index, observation in enumerate(entry.get("commercial_observations", [])):
        prefix = f"{location}.commercial_observations[{index}]"
        if not isinstance(observation, dict):
            issues.append(f"{prefix}: observation non structurée")
            continue
        if observation.get("rank") is not None and not all(isinstance(observation.get(field), str) and observation[field] for field in ("market", "category", "observed_at")):
            issues.append(f"{prefix}.rank: marché, catégorie et instant requis")
        if observation.get("rank") is not None or observation.get("rating") is not None:
            _proof(observation.get("proof"), f"{prefix}.proof", issues)
        rating = observation.get("rating")
        if rating is not None and (not isinstance(rating, dict) or not isinstance(rating.get("average"), (int, float)) or not isinstance(rating.get("count"), int)):
            issues.append(f"{prefix}.rating: moyenne et nombre de votes requis")


def validate_catalog(catalog: dict[str, Any], manifest: dict[str, Any], *, allow_unreviewed: bool = False) -> list[str]:
    """Retourne toutes les violations, sans transformer une absence en zéro."""
    issues: list[str] = []
    if catalog.get("schema_version") != CATALOG_SCHEMA_VERSION:
        issues.append("schema_version: version inconnue")
    documents = catalog.get("documents")
    expected = {entry["sha256"]: entry for entry in manifest.get("documents", []) if entry.get("included")}
    actual = {entry.get("source_sha256"): entry for entry in documents or [] if isinstance(entry, dict)}
    for source in sorted(expected.keys() - actual.keys()):
        issues.append(f"{source}: document inclus absent du registre")
    for source in sorted(actual.keys() - expected.keys()):
        issues.append(f"{source}: document absent du manifeste inclus")
    if not isinstance(documents, list):
        issues.append("documents: liste attendue")
    else:
        for index, entry in enumerate(documents):
            source = entry.get("source_sha256") if isinstance(entry, dict) else None
            location = f"documents[{index}]"
            _document(entry, location, issues, allow_unreviewed)
            if source in expected and entry.get("file_name") != expected[source].get("name"):
                issues.append(f"{location}.file_name: différent du manifeste")
    return issues
