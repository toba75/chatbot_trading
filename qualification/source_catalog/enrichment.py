"""Enrichissement Google Books observable et rejouable du registre."""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection
from datetime import date
from pathlib import Path
from typing import Any

from .candidate_review import CANDIDATE_REVIEWS, apply_candidate_review, observed_candidates
from .constants import QUERY_STATES, RESOLUTION_STATES
from .google_books import GoogleBooksClient, InvalidProviderResponse, ProviderUnavailable, classify_resolution
from .identity import lookup_for_entry
from .registry import utc_now, validate_catalog


# Une consultation qui n'a pas abouti garde son état propre : l'indisponibilité
# du fournisseur n'est jamais confondue avec une absence de correspondance.
CONSULTATION_BY_RESOLUTION = {
    "unavailable": "unavailable",
    "no_match": "no_match",
    "not_queried": "not_queried",
}

# Le rapport publie tous les états du contrat, dans un ordre stable : un état
# omis ferait disparaître des documents du total sans que rien ne le signale.
CONSULTATION_ORDER = ("not_queried", "succeeded", "no_match", "unavailable", "expired")
RESOLUTION_ORDER = (
    "not_queried",
    "accepted",
    "ambiguous",
    "candidate",
    "rejected",
    "no_match",
    "unavailable",
)
assert set(CONSULTATION_ORDER) == QUERY_STATES
assert set(RESOLUTION_ORDER) == RESOLUTION_STATES


def _date_value(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    text = str(value)
    precision = "year"
    if len(text) >= 7:
        precision = "month"
    if len(text) >= 10:
        precision = "day"
    try:
        date.fromisoformat(text[:10])
    except ValueError:
        try:
            if precision == "year":
                int(text[:4])
            elif precision == "month":
                date.fromisoformat(f"{text[:7]}-01")
            else:
                raise ValueError
        except ValueError:
            return None
    return {"value": text[:10] if precision == "day" else text[:7] if precision == "month" else text[:4], "precision": precision}


def _merge_source_identifiers(entry: dict[str, Any], lookup: dict[str, Any]) -> None:
    bibliography = entry["bibliography"]
    for kind, values in lookup.get("identifiers", {}).items():
        bibliography["identifiers"].setdefault(kind, [])
        for value in values:
            if value not in bibliography["identifiers"][kind]:
                bibliography["identifiers"][kind].append(value)
    known = {str(proof.get("locator", {}).get("charspan")): proof for proof in bibliography.get("provenance", [])}
    for values in lookup.get("identifier_proofs", {}).values():
        for item in values:
            proof = item["proof"]
            key = str(proof.get("locator", {}).get("charspan"))
            if key not in known:
                bibliography.setdefault("provenance", []).append(proof)
                known[key] = proof


def _observation(attempt: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "provider": "google_books",
        "request": {"kind": attempt["kind"], "query": attempt["query"], "url": attempt["url"]},
        "observed_at": attempt["observed_at"],
        "status": "succeeded",
        "invalid_candidate_count": attempt.get("invalid_candidate_count", 0),
        "candidates": candidates,
    }


def _provider_error(
    message: str,
    *,
    code: str,
    observed_at: str,
    kind: str = "unknown",
    query: str | None = None,
) -> dict[str, Any]:
    return {
        "provider": "google_books",
        "request": {"kind": kind, "query": query},
        "observed_at": observed_at,
        "status": "unavailable",
        "error": {"code": code, "message": message[:500]},
        "candidates": [],
    }


def _apply_candidate(entry: dict[str, Any], candidate: dict[str, Any]) -> None:
    proof = candidate["proof"]
    source_ids = entry["bibliography"].get("identifiers", {})
    provider_ids = candidate.get("identifiers", {})
    identifiers = {
        kind: sorted(set(source_ids.get(kind, []) + provider_ids.get(kind, [])))
        for kind in ("isbn10", "isbn13", "issn")
    }
    entry["bibliography"] = {
        "title": candidate.get("title"),
        "authors": candidate.get("authors", []),
        "language": candidate.get("language"),
        "publisher": candidate.get("publisher"),
        "identifiers": identifiers,
        "provenance": entry["bibliography"].get("provenance", []) + [proof],
    }
    edition = _date_value(candidate.get("published_date"))
    if edition:
        entry["temporality"]["edition_published"] = edition | {"proof": proof}


def enrich_catalog(
    manifest: dict[str, Any],
    catalog: dict[str, Any],
    *,
    client: GoogleBooksClient | None,
    work: Path | None = None,
    observed_at: str | None = None,
    only: Collection[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Consulte Google Books, applique les revues, puis résume l'état du registre.

    `only` restreint la consultation réseau aux empreintes indiquées. Les autres
    entrées gardent leurs observations : une reprise après indisponibilité ne
    rejoue pas — et ne peut donc pas dégrader — les consultations réussies.
    """
    by_sha = {entry["sha256"]: entry for entry in manifest["documents"] if entry.get("included")}
    for entry in catalog["documents"] if client is not None else []:
        if only is not None and entry["source_sha256"] not in only:
            continue
        manifest_entry = by_sha[entry["source_sha256"]]
        lookup = lookup_for_entry(manifest_entry, work)
        entry["lookup"] = {key: value for key, value in lookup.items() if key != "identifier_proofs"}
        _merge_source_identifiers(entry, lookup)
        entry["provider_observations"] = [
            observation
            for observation in entry.get("provider_observations", [])
            if observation.get("provider") != "google_books"
        ]
        isbns = lookup["identifiers"].get("isbn13", []) + lookup["identifiers"].get("isbn10", [])
        issns = lookup["identifiers"].get("issn", [])
        try:
            result = client.resolve(
                isbns=isbns,
                issns=issns,
                title=lookup["title"],
                authors=lookup["authors"],
                publisher=lookup.get("publisher_hint"),
                publication_year=lookup.get("publication_year_hint"),
                title_variants=lookup.get("title_variants"),
            )
            resolution, candidates = classify_resolution(
                result,
                title=lookup["title"],
                authors=lookup["authors"],
                publisher=lookup.get("publisher_hint"),
                publication_year=lookup.get("publication_year_hint"),
            )
            marked = {candidate["candidate_id"]: candidate for candidate in candidates}
            document_candidates: dict[str, dict[str, Any]] = {}
            for attempt in result["attempts"]:
                attempt_candidates = [
                    marked.get(candidate["candidate_id"], candidate)
                    for candidate in attempt["candidates"]
                ]
                entry["provider_observations"].append(_observation(attempt, attempt_candidates))
                for candidate in attempt_candidates:
                    document_candidates[candidate["candidate_id"]] = candidate
            entry["resolution"] = {"status": resolution, "candidate_id": None, "proof": None}
            if resolution == "accepted" and candidates:
                accepted = candidates[0]
                entry["resolution"] = {
                    "status": "accepted",
                    "candidate_id": accepted["candidate_id"],
                    "proof": accepted["proof"] | {
                        "match": "exact_issn" if result.get("method") == "issn" else "exact_isbn"
                    },
                }
                _apply_candidate(entry, accepted)
        except ProviderUnavailable as error:
            entry["provider_observations"].append(_provider_error(
                str(error),
                code="provider_unavailable",
                observed_at=getattr(error, "observed_at", None) or observed_at or utc_now(),
                kind=getattr(error, "kind", "unknown"),
                query=getattr(error, "query", None),
            ))
            entry["resolution"] = {"status": "unavailable", "candidate_id": None, "proof": None}
        except InvalidProviderResponse as error:
            entry["provider_observations"].append(_provider_error(
                str(error),
                code="invalid_response",
                observed_at=getattr(error, "observed_at", None) or observed_at or utc_now(),
                kind=getattr(error, "kind", "unknown"),
                query=getattr(error, "query", None),
            ))
            entry["resolution"] = {"status": "unavailable", "candidate_id": None, "proof": None}
    apply_reviews(catalog)
    issues = validate_catalog(catalog, manifest)
    if issues:
        raise ValueError("Registre invalide après enrichissement : " + "; ".join(issues))
    return catalog, summarize_catalog(catalog, observed_at=observed_at)


def apply_reviews(
    catalog: dict[str, Any],
    *,
    reviews: dict[str, dict[str, Any]] = CANDIDATE_REVIEWS,
) -> None:
    """Applique les décisions humaines à tout le registre, quelle que soit la passe.

    L'opération est idempotente : une décision déjà appliquée redonne le même
    état, de sorte qu'une reprise partielle ne perde aucune revue.
    """
    for entry in catalog["documents"]:
        accepted = apply_candidate_review(
            entry, entry["resolution"]["status"], reviews=reviews
        )
        if accepted is not None:
            _apply_candidate(entry, accepted)


def summarize_catalog(catalog: dict[str, Any], *, observed_at: str | None = None) -> dict[str, Any]:
    """Résume l'état du registre, sans dépendre du périmètre de la consultation."""
    consultations: Counter[str] = Counter()
    resolutions: Counter[str] = Counter()
    candidate_states: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    coverage: Counter[str] = Counter()
    documents = []
    for entry in catalog["documents"]:
        resolution = entry["resolution"]["status"]
        consultation = CONSULTATION_BY_RESOLUTION.get(resolution, "succeeded")
        candidates = observed_candidates(entry)
        for candidate in candidates.values():
            candidate_states[candidate.get("status", "candidate")] += 1
        identifiers = entry["lookup"]["identifiers"]
        isbns = identifiers.get("isbn13", []) + identifiers.get("isbn10", [])
        coverage["with_identifier" if isbns or identifiers.get("issn") else "without_identifier"] += 1
        if len(isbns) > 1:
            coverage["multiple_identifiers"] += 1
        kinds[entry["document_kind"]] += 1
        consultations[consultation] += 1
        resolutions[resolution] += 1
        decision = entry["resolution"].get("proof") or {}
        documents.append({
            "source_sha256": entry["source_sha256"],
            "consultation": consultation,
            "resolution": resolution,
            "candidate_count": len(candidates),
            "reviewed": decision.get("kind") == "manual",
            # Chaque acceptation nomme son candidat et la ressource qui la prouve.
            "accepted_candidate_id": entry["resolution"].get("candidate_id"),
            "accepted_proof": {
                key: decision[key]
                for key in ("kind", "provider", "resource_id", "observed_at", "match", "reviewer")
                if key in decision
            }
            or None,
        })
    return {
        "schema_version": 1,
        "observed_at": observed_at or utc_now(),
        "consultations": {state: consultations.get(state, 0) for state in CONSULTATION_ORDER},
        "resolutions": {state: resolutions.get(state, 0) for state in RESOLUTION_ORDER},
        "candidate_states": {
            state: candidate_states.get(state, 0)
            for state in ("candidate", "accepted", "ambiguous", "rejected")
        },
        "documents_by_kind": dict(kinds),
        "identifier_coverage": dict(coverage),
        "documents": documents,
    }
