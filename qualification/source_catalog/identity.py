"""Résolution locale de l'identité de recherche et des ISBN du DoclingDocument."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

ISBN_RE = re.compile(r"(?i)\b(?:e?isbn(?:[- ]?1[03])?\s*[:#-]?\s*)?((?:97[89][ -]?)?[0-9][0-9 -]{8,}[0-9X])\b")
ISSN_RE = re.compile(r"(?i)\bISSN\s*[:#-]?\s*([0-9]{4})[- ]?([0-9]{3}[0-9X])\b")
TITLE_AUTHOR_OVERRIDES = {
    "a century of profitable industry trends carlo zarattini gary antonacci.pdf": (
        "A Century of Profitable Industry Trends",
        ["Carlo Zarattini", "Gary Antonacci"],
    ),
    "optimal trend following rules in two state switching regime models.pdf": (
        "Optimal Trend Following Rules in Two State Switching Regime Models",
        [],
    ),
}


def _digits(value: str) -> str:
    return re.sub(r"[^0-9Xx]", "", value).upper()


def _valid_isbn10(value: str) -> bool:
    return (
        len(value) == 10
        and value[:9].isdigit()
        and (value[9].isdigit() or value[9] == "X")
        and sum((10 - i) * (10 if char == "X" else int(char)) for i, char in enumerate(value)) % 11 == 0
    )


def _valid_isbn13(value: str) -> bool:
    return len(value) == 13 and value.isdigit() and sum((1 if i % 2 == 0 else 3) * int(char) for i, char in enumerate(value)) % 10 == 0


def _isbn_kind(value: str) -> str | None:
    if _valid_isbn10(value):
        return "isbn10"
    if _valid_isbn13(value):
        return "isbn13"
    return None


def _valid_issn(value: str) -> bool:
    if len(value) != 8 or not value[:7].isdigit() or not (value[7].isdigit() or value[7] == "X"):
        return False
    return sum((8 - index) * (10 if character == "X" else int(character)) for index, character in enumerate(value)) % 11 == 0


def _docling_text(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [item for item in data.get("texts", []) if isinstance(item, dict) and item.get("text")]


def extract_identifiers(document_path: Path) -> dict[str, list[dict[str, Any]]]:
    found: dict[str, dict[str, dict[str, Any]]] = {"isbn10": {}, "isbn13": {}, "issn": {}}
    for item in _docling_text(document_path):
        text = str(item["text"])
        for match in ISBN_RE.finditer(text):
            value = _digits(match.group(1))
            kind = _isbn_kind(value)
            if kind and value not in found[kind]:
                page = item.get("prov", [{}])[0].get("page_no") if item.get("prov") else None
                found[kind][value] = {
                    "value": value,
                    "proof": {
                        "kind": "source_text",
                        "locator": {
                            "page": page,
                            "docling_ref": item.get("self_ref"),
                            "charspan": [match.start(), match.end()],
                        },
                    },
                }
        for match in ISSN_RE.finditer(text):
            value = _digits("".join(match.groups()))
            if _valid_issn(value) and value not in found["issn"]:
                page = item.get("prov", [{}])[0].get("page_no") if item.get("prov") else None
                found["issn"][value] = {
                    "value": value,
                    "proof": {
                        "kind": "source_text",
                        "locator": {
                            "page": page,
                            "docling_ref": item.get("self_ref"),
                            "charspan": [match.start(), match.end()],
                        },
                    },
                }
    return {kind: list(values.values()) for kind, values in found.items()}


def _display_name(filename: str) -> str:
    name = Path(filename).stem.replace("_", " ")
    name = re.sub(r"\s+", " ", name.replace(".pub ", " ")).strip()
    return name


def _title_hints(title: str) -> tuple[str, list[str], str | None, str | None]:
    """Retire les suffixes d'édition du nom de fichier sans perdre la variante brute."""
    raw_title = " ".join(title.split())
    publisher = None
    year = None
    match = re.search(r"\s*[-–]\s*(?P<publisher>[^-–()]+?)\s*\((?P<year>(?:19|20)\d{2})\)\s*$", raw_title)
    if match:
        publisher = match.group("publisher").strip() or None
        year = match.group("year")
        clean_title = raw_title[: match.start()].strip()
    else:
        year_match = re.search(r"(?:\(|\[)?(?P<year>(?:19|20)\d{2})(?:\)|\])?\s*$", raw_title)
        year = year_match.group("year") if year_match else None
        clean_title = raw_title
    variants = [clean_title]
    if raw_title not in variants:
        variants.append(raw_title)
    return clean_title, variants, publisher, year


def lookup_for_entry(entry: dict[str, Any], work: Path | None = None) -> dict[str, Any]:
    title = _display_name(entry["name"])
    authors: list[str] = []
    override = TITLE_AUTHOR_OVERRIDES.get(entry["name"].casefold())
    if override:
        title, authors = override
    if " - " in title:
        title, author = title.rsplit(" - ", 1)
        if not authors:
            authors = [author.strip()]
    kind = "book"
    lowered = entry["name"].casefold()
    if "optimal trend following rules" in lowered or "century of profitable industry trends" in lowered:
        kind = "article"
    elif "ssrn" in lowered or "working paper" in lowered:
        kind = "working_paper"
    title, title_variants, publisher_hint, publication_year_hint = _title_hints(title)
    identifiers = {"isbn10": [], "isbn13": [], "issn": []}
    identifier_proofs: dict[str, list[dict[str, Any]]] = {
        "isbn10": [], "isbn13": [], "issn": []
    }
    if work is not None:
        extracted = extract_identifiers(work / entry["sha256"][:12] / "docling-document.json")
        identifiers = {kind: [item["value"] for item in values] for kind, values in extracted.items()}
        identifier_proofs = extracted
    return {
        "title": title,
        "title_variants": title_variants,
        "authors": authors,
        "publisher_hint": publisher_hint,
        "publication_year_hint": publication_year_hint,
        "identifiers": identifiers,
        "identifier_proofs": identifier_proofs,
        "document_kind": kind,
    }
