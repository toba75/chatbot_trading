"""Enrichissement Google Books observable et rejouable du registre."""

from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from .google_books import GoogleBooksClient, InvalidProviderResponse, ProviderUnavailable, classify_resolution
from .identity import lookup_for_entry
from .registry import utc_now, validate_catalog


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
    client: GoogleBooksClient,
    work: Path | None = None,
    observed_at: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Remplace l'observation Google Books précédente sans toucher aux autres fournisseurs."""
    report = {
        "schema_version": 1,
        "observed_at": observed_at or utc_now(),
        "consultations": Counter(),
        "resolutions": Counter(),
        "candidate_states": Counter(),
        "documents_by_kind": Counter(),
        "identifier_coverage": Counter(),
        "documents": [],
    }
    by_sha = {entry["sha256"]: entry for entry in manifest["documents"] if entry.get("included")}
    for entry in catalog["documents"]:
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
        report["documents_by_kind"][entry["document_kind"]] += 1
        report["identifier_coverage"]["with_identifier" if isbns or issns else "without_identifier"] += 1
        if len(isbns) > 1:
            report["identifier_coverage"]["multiple_identifiers"] += 1
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
            document_candidate_states: dict[str, str] = {}
            for attempt in result["attempts"]:
                attempt_candidates = [
                    marked.get(candidate["candidate_id"], candidate)
                    for candidate in attempt["candidates"]
                ]
                entry["provider_observations"].append(_observation(attempt, attempt_candidates))
                for candidate in attempt_candidates:
                    document_candidate_states[candidate["candidate_id"]] = candidate.get("status", "candidate")
            for state in document_candidate_states.values():
                report["candidate_states"][state] += 1
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
            consultation = "no_match" if resolution == "no_match" else "succeeded"
            report["consultations"][consultation] += 1
            report["resolutions"][resolution] += 1
            report["documents"].append({"source_sha256": entry["source_sha256"], "consultation": consultation, "resolution": resolution, "candidate_count": len(candidates)})
        except ProviderUnavailable as error:
            entry["provider_observations"].append(_provider_error(
                str(error),
                code="provider_unavailable",
                observed_at=getattr(error, "observed_at", None) or observed_at or utc_now(),
                kind=getattr(error, "kind", "unknown"),
                query=getattr(error, "query", None),
            ))
            entry["resolution"] = {"status": "unavailable", "candidate_id": None, "proof": None}
            report["consultations"]["unavailable"] += 1
            report["resolutions"]["unavailable"] += 1
            report["documents"].append({"source_sha256": entry["source_sha256"], "consultation": "unavailable", "resolution": "unavailable"})
        except InvalidProviderResponse as error:
            entry["provider_observations"].append(_provider_error(
                str(error),
                code="invalid_response",
                observed_at=getattr(error, "observed_at", None) or observed_at or utc_now(),
                kind=getattr(error, "kind", "unknown"),
                query=getattr(error, "query", None),
            ))
            entry["resolution"] = {"status": "unavailable", "candidate_id": None, "proof": None}
            report["consultations"]["unavailable"] += 1
            report["resolutions"]["unavailable"] += 1
            report["documents"].append({"source_sha256": entry["source_sha256"], "consultation": "unavailable", "resolution": "unavailable"})
    report["consultations"] = {
        state: report["consultations"].get(state, 0)
        for state in ("succeeded", "no_match", "unavailable")
    }
    report["resolutions"] = {
        state: report["resolutions"].get(state, 0)
        for state in ("accepted", "ambiguous", "candidate", "rejected", "no_match", "unavailable")
    }
    report["candidate_states"] = {
        state: report["candidate_states"].get(state, 0)
        for state in ("candidate", "accepted", "ambiguous", "rejected")
    }
    report["documents_by_kind"] = dict(report["documents_by_kind"])
    report["identifier_coverage"] = dict(report["identifier_coverage"])
    issues = validate_catalog(catalog, manifest)
    if issues:
        raise ValueError("Registre invalide après enrichissement : " + "; ".join(issues))
    return catalog, report
