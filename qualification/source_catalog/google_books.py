"""Client minimal et borné de l'API Google Books Volumes."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import re
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ENDPOINT = "https://www.googleapis.com/books/v1/volumes"
Transport = Callable[[str, float], dict[str, Any]]


class ProviderUnavailable(RuntimeError):
    """Le fournisseur n'a pas pu être consulté ; ce n'est pas un no-match."""


class InvalidProviderResponse(ValueError):
    """La réponse du fournisseur ne respecte pas le contrat JSON attendu."""


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def default_transport(url: str, timeout: float) -> dict[str, Any]:
    request = Request(url, headers={"accept": "application/json", "user-agent": "chatbot-trading-source-catalog/1"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except json.JSONDecodeError as error:
        raise InvalidProviderResponse("La réponse Google Books n'est pas un JSON valide") from error
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise ProviderUnavailable(f"Google Books indisponible : {error}") from error
    if not isinstance(payload, dict):
        raise InvalidProviderResponse("La réponse Google Books n'est pas un objet JSON")
    return payload


def _clean_identifier(value: str) -> str:
    return "".join(character for character in value.upper() if character.isdigit() or character == "X")


def _identifiers(volume: dict[str, Any]) -> dict[str, list[str]]:
    result = {"isbn10": [], "isbn13": [], "issn": []}
    for identifier in volume.get("industryIdentifiers", []) or []:
        if not isinstance(identifier, dict):
            continue
        value = _clean_identifier(str(identifier.get("identifier", "")))
        kind = str(identifier.get("type", "")).upper()
        if kind == "ISBN_10" and value:
            result["isbn10"].append(value)
        elif kind == "ISBN_13" and value:
            result["isbn13"].append(value)
        elif kind in {"ISSN", "ISSN_L"} and value:
            result["issn"].append(value)
    return {kind: sorted(set(values)) for kind, values in result.items()}


def normalize_volume(volume: dict[str, Any], observed_at: str) -> dict[str, Any]:
    if not isinstance(volume, dict) or not isinstance(volume.get("id"), str) or not volume["id"]:
        raise InvalidProviderResponse("Volume Google Books sans identifiant")
    info = volume.get("volumeInfo")
    if not isinstance(info, dict):
        raise InvalidProviderResponse(f"Volume {volume['id']} sans volumeInfo")
    rating = None
    average = info.get("averageRating")
    count = info.get("ratingsCount")
    if (
        isinstance(average, (int, float))
        and not isinstance(average, bool)
        and 0 <= float(average) <= 5
        and isinstance(count, int)
        and not isinstance(count, bool)
        and count >= 0
    ):
        rating = {"average": float(average), "count": count}
    return {
        "candidate_id": f"google_books:{volume['id']}",
        "volume_id": volume["id"],
        "status": "candidate",
        "title": info.get("title"),
        "subtitle": info.get("subtitle"),
        "authors": [author for author in info.get("authors", []) if isinstance(author, str) and author.strip()]
        if isinstance(info.get("authors", []), list) else [],
        "publisher": info.get("publisher"),
        "published_date": info.get("publishedDate"),
        "language": info.get("language"),
        "page_count": info.get("pageCount"),
        "categories": [category for category in info.get("categories", []) if isinstance(category, str) and category.strip()]
        if isinstance(info.get("categories", []), list) else [],
        "identifiers": _identifiers(info),
        "rating": rating,
        "proof": {
            "kind": "provider",
            "provider": "google_books",
            "resource_id": volume["id"],
            "observed_at": observed_at,
        },
    }


def _title_similarity(expected: str, actual: str | None) -> float:
    if not actual:
        return 0.0
    left = _tokens(expected)
    right = _tokens(actual)
    return len(left & right) / max(len(left), len(right), 1)


def _tokens(value: str | None) -> set[str]:
    return set(re.findall(r"[\w]+", str(value or "").casefold(), flags=re.UNICODE))


def _canonical_isbn(value: str) -> str | None:
    normalized = _clean_identifier(str(value))
    if len(normalized) == 10:
        if not normalized[:9].isdigit() or not (normalized[9].isdigit() or normalized[9] == "X"):
            return None
        total = sum((10 - index) * (10 if character == "X" else int(character)) for index, character in enumerate(normalized))
        return normalized if total % 11 == 0 else None
    if len(normalized) == 13 and normalized.isdigit():
        total = sum((1 if index % 2 == 0 else 3) * int(character) for index, character in enumerate(normalized))
        return normalized if total % 10 == 0 else None
    return None


def _isbn_variants(value: str) -> set[str]:
    canonical = _canonical_isbn(value)
    if not canonical:
        return set()
    variants = {canonical}
    if len(canonical) == 10:
        body = "978" + canonical[:9]
        checksum = (10 - sum((1 if index % 2 == 0 else 3) * int(character) for index, character in enumerate(body)) % 10) % 10
        variants.add(body + str(checksum))
    elif canonical.startswith("978"):
        body = canonical[3:-1]
        checksum = (11 - sum((10 - index) * int(character) for index, character in enumerate(body)) % 11) % 11
        variants.add(body + ("X" if checksum == 10 else str(checksum)))
    return variants


def _canonical_issn(value: str) -> str | None:
    normalized = _clean_identifier(str(value))
    if len(normalized) != 8 or not normalized[:7].isdigit() or not (normalized[7].isdigit() or normalized[7] == "X"):
        return None
    total = sum((8 - index) * (10 if character == "X" else int(character)) for index, character in enumerate(normalized))
    return normalized if total % 11 == 0 else None


def _token_similarity(expected: str, actual: str | None) -> float:
    left = _tokens(expected)
    right = _tokens(actual)
    return len(left & right) / max(len(left), len(right), 1)


def _author_similarity(expected: list[str], actual: list[str]) -> float:
    if not expected or not actual:
        return 0.0
    return max(
        _title_similarity(author, candidate)
        for author in expected
        for candidate in actual
    )


def _year(value: str | None) -> str | None:
    text = str(value or "")
    return text[:4] if len(text) >= 4 and text[:4].isdigit() else None


def _match_signals(
    candidate: dict[str, Any],
    *,
    title: str,
    authors: list[str],
    publisher: str | None,
    publication_year: str | None,
) -> dict[str, float | bool]:
    signals: dict[str, float | bool] = {
        "title": _title_similarity(title, candidate.get("title")),
    }
    weights = {"title": 0.60}
    if authors:
        signals["author"] = _author_similarity(authors, candidate.get("authors", []))
        weights["author"] = 0.20
    if publisher:
        signals["publisher"] = _token_similarity(publisher, candidate.get("publisher"))
        weights["publisher"] = 0.10
    if publication_year:
        signals["year_match"] = _year(publication_year) == _year(candidate.get("published_date"))
        weights["year"] = 0.10
        signals["year"] = 1.0 if signals["year_match"] else 0.0
    score = sum(float(signals[name]) * weight for name, weight in weights.items()) / sum(weights.values())
    signals["score"] = round(score, 4)
    return signals


def _merge_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        identifier = candidate["candidate_id"]
        current = by_id.setdefault(identifier, candidate)
        for field in ("title", "subtitle", "publisher", "published_date", "language", "page_count", "rating"):
            if not current.get(field) and candidate.get(field):
                current[field] = candidate[field]
        for field in ("authors", "categories"):
            values = current.setdefault(field, [])
            for value in candidate.get(field, []):
                if value not in values:
                    values.append(value)
        current_identifiers = current.setdefault("identifiers", {})
        for kind, values in candidate.get("identifiers", {}).items():
            current_values = current_identifiers.setdefault(kind, [])
            for value in values:
                if value not in current_values:
                    current_values.append(value)
        queries = current.setdefault("matched_queries", [])
        for query in candidate.get("matched_queries", []):
            if query not in queries:
                queries.append(query)
    return list(by_id.values())


class GoogleBooksClient:
    """Résolution Google Books multi-signaux, sans sélection implicite du premier résultat."""

    MAX_AUTHORS = 3

    def __init__(self, *, timeout: float = 10.0, api_key: str | None = None, transport: Transport = default_transport):
        self.timeout = timeout
        self.api_key = api_key
        self.transport = transport

    def _search(self, query: str, kind: str) -> dict[str, Any]:
        params = {"q": query, "maxResults": "40", "printType": "all"}
        if self.api_key:
            params["key"] = self.api_key
        url = f"{ENDPOINT}?{urlencode(params)}"
        observed_at = _now()
        try:
            payload = self.transport(url, self.timeout)
        except (ProviderUnavailable, InvalidProviderResponse) as error:
            error.query = query  # type: ignore[attr-defined]
            error.kind = kind  # type: ignore[attr-defined]
            error.observed_at = observed_at  # type: ignore[attr-defined]
            raise
        if not isinstance(payload, dict):
            raise InvalidProviderResponse("La réponse Google Books n'est pas un objet JSON")
        if not isinstance(payload.get("items", []), list):
            raise InvalidProviderResponse("Google Books: items doit être une liste")
        candidates = []
        invalid_count = 0
        for item in payload.get("items", []):
            try:
                candidate = normalize_volume(item, observed_at)
            except InvalidProviderResponse:
                invalid_count += 1
                continue
            candidate.setdefault("matched_queries", []).append(query)
            candidates.append(candidate)
        return {
            "kind": kind,
            "query": query,
            "url": url.split("&key=", 1)[0],
            "observed_at": observed_at,
            "candidates": candidates,
            "invalid_candidate_count": invalid_count,
        }

    def resolve(
        self,
        *,
        isbns: list[str],
        title: str,
        authors: list[str],
        issns: list[str] | None = None,
        publisher: str | None = None,
        publication_year: str | None = None,
        title_variants: list[str] | None = None,
    ) -> dict[str, Any]:
        attempts: list[dict[str, Any]] = []
        identifier_matches: list[dict[str, Any]] = []
        identifier_conflicts: list[dict[str, Any]] = []
        for isbn in isbns:
            canonical = _canonical_isbn(isbn)
            if not canonical:
                continue
            query = f"isbn:{canonical}"
            attempt = self._search(query, "isbn")
            attempts.append(attempt)
            expected_identifiers = _isbn_variants(canonical)
            exact = [
                candidate
                for candidate in attempt["candidates"]
                if expected_identifiers & set(candidate["identifiers"].get("isbn10", []) + candidate["identifiers"].get("isbn13", []))
            ]
            coherent = [
                candidate
                for candidate in exact
                if _title_similarity(title, candidate.get("title")) >= 0.45
                or any(author.casefold() in " ".join(candidate.get("authors", [])).casefold() for author in authors)
            ]
            identifier_matches.extend(coherent)
            identifier_conflicts.extend(exact if not coherent else [])
        if identifier_matches:
            return {"method": "isbn", "attempts": attempts, "candidates": _merge_candidates(identifier_matches)}
        conflict_candidates = _merge_candidates(identifier_conflicts)

        issn_matches: list[dict[str, Any]] = []
        issn_conflicts: list[dict[str, Any]] = []
        for issn in issns or []:
            canonical = _canonical_issn(issn)
            if not canonical:
                continue
            attempt = self._search(f"issn:{canonical}", "issn")
            attempts.append(attempt)
            exact = [candidate for candidate in attempt["candidates"] if canonical in candidate["identifiers"].get("issn", [])]
            coherent = [
                candidate
                for candidate in exact
                if _title_similarity(title, candidate.get("title")) >= 0.45
                or any(author.casefold() in " ".join(candidate.get("authors", [])).casefold() for author in authors)
            ]
            issn_matches.extend(coherent)
            issn_conflicts.extend(candidate for candidate in exact if candidate not in coherent)
        if issn_matches:
            return {"method": "issn", "attempts": attempts, "candidates": _merge_candidates(issn_matches)}

        title_candidates: list[dict[str, Any]] = []
        for query in self._query_variants(
            title=title,
            authors=authors,
            publisher=publisher,
            title_variants=title_variants,
        ):
            attempt = self._search(query, "title_author")
            attempts.append(attempt)
            title_candidates.extend(attempt["candidates"])
        merged = _merge_candidates(title_candidates)
        fallback_identifier_matches = [
            candidate
            for candidate in merged
            if any(
                _isbn_variants(isbn)
                & set(candidate["identifiers"].get("isbn10", []) + candidate["identifiers"].get("isbn13", []))
                for isbn in isbns
            )
            and (
                _title_similarity(title, candidate.get("title")) >= 0.45
                or any(author.casefold() in " ".join(candidate.get("authors", [])).casefold() for author in authors)
            )
        ]
        if fallback_identifier_matches:
            return {"method": "isbn", "attempts": attempts, "candidates": fallback_identifier_matches}
        if issn_conflicts and not merged:
            return {"method": "issn_conflict", "attempts": attempts, "candidates": _merge_candidates(issn_conflicts)}
        if conflict_candidates and merged and all(
            candidate["candidate_id"] in {item["candidate_id"] for item in conflict_candidates}
            for candidate in merged
        ):
            return {"method": "isbn_conflict", "attempts": attempts, "candidates": conflict_candidates}
        if conflict_candidates and not merged:
            return {"method": "isbn_conflict", "attempts": attempts, "candidates": conflict_candidates}
        return {"method": "title_author", "attempts": attempts, "candidates": merged}

    def _query_variants(
        self,
        *,
        title: str,
        authors: list[str],
        publisher: str | None,
        title_variants: list[str] | None,
    ) -> list[str]:
        titles = []
        for value in [*(title_variants or []), title]:
            normalized = " ".join(str(value).split())
            if normalized and normalized not in titles:
                titles.append(normalized)
        queries: list[str] = []
        primary_title = titles[0] if titles else title
        for author in authors[: self.MAX_AUTHORS]:
            query = f"intitle:{primary_title} inauthor:{author}"
            if query not in queries:
                queries.append(query)
        for candidate_title in titles:
            query = f"intitle:{candidate_title}"
            if query not in queries:
                queries.append(query)
        if publisher:
            query = f"intitle:{primary_title} inpublisher:{publisher}"
            if query not in queries:
                queries.append(query)
        return queries or [f"intitle:{title}"]


def classify_resolution(
    result: dict[str, Any],
    *,
    title: str,
    authors: list[str] | None = None,
    publisher: str | None = None,
    publication_year: str | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    candidates = list(result.get("candidates", []))
    if not candidates:
        return "no_match", []
    if result.get("method") in {"isbn", "issn"}:
        if len(candidates) == 1:
            candidate = candidates[0] | {"status": "accepted"}
            return "accepted", [candidate]
        return "ambiguous", [candidate | {"status": "ambiguous"} for candidate in candidates]
    if result.get("method") == "isbn_conflict":
        return "rejected", [candidate | {"status": "rejected"} for candidate in candidates]
    authors = authors or []
    for candidate in candidates:
        candidate["matching"] = _match_signals(
            candidate,
            title=title,
            authors=authors,
            publisher=publisher,
            publication_year=publication_year,
        )
        candidate["score"] = candidate["matching"]["score"]
    candidates.sort(key=lambda candidate: candidate["score"], reverse=True)
    plausible = [candidate for candidate in candidates if candidate["score"] >= 0.72]
    if len(plausible) == 1:
        return "candidate", [plausible[0] | {"status": "candidate"}]
    if plausible:
        return "ambiguous", [candidate | {"status": "ambiguous"} for candidate in plausible]
    return "rejected", [candidate | {"status": "rejected"} for candidate in candidates]
