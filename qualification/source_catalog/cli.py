"""Commandes build/enrich/review/verify du registre de sources."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

from qualification.corpus_reference.coverage import WORK
from qualification.corpus_reference.manifest import MANIFEST

from .enrichment import enrich_catalog
from .google_books import GoogleBooksClient
from .rails_credentials import load_google_books_credentials
from .registry import CATALOG, build_skeleton, load_catalog, save_catalog, verify_catalog
from .review import review_catalog

# Une reprise ne rejoue que ce qui n'a pas abouti : une consultation réussie
# n'est jamais re-interrogée, donc jamais dégradée par une limitation de débit.
UNRESOLVED_STATES = {"unavailable", "not_queried"}


def _manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _catalog_or_skeleton(catalog_path: Path, manifest_path: Path, work: Path) -> dict[str, Any]:
    manifest = _manifest(manifest_path)
    if catalog_path.exists():
        return load_catalog(catalog_path)
    return build_skeleton(manifest, manifest_path=manifest_path, work=work)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "enrich", "review", "verify"))
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--work", type=Path, default=WORK)
    parser.add_argument("--network", choices=("offline", "google-books"), default="offline")
    parser.add_argument(
        "--only-unresolved",
        action="store_true",
        help="Ne consulte que les entrées sans consultation aboutie ; les autres sont conservées.",
    )
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--reviewer", default="codex")
    parser.add_argument("--date", dest="reviewed_at")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    manifest = _manifest(arguments.manifest)
    if arguments.action == "build":
        catalog = build_skeleton(manifest, manifest_path=arguments.manifest, work=arguments.work)
        save_catalog(catalog, arguments.catalog)
        print(f"{len(catalog['documents'])} entrées écrites dans {arguments.catalog}")
        return 0
    if arguments.action == "verify":
        catalog = load_catalog(arguments.catalog)
        verify_catalog(catalog, manifest)
        expected_hash = hashlib.sha256(arguments.manifest.read_bytes()).hexdigest()
        if catalog.get("manifest_sha256") not in (None, expected_hash):
            raise ValueError("manifest_sha256 : le registre ne correspond pas au manifeste")
        print(f"registre valide : {len(catalog['documents'])} documents")
        return 0
    catalog = _catalog_or_skeleton(arguments.catalog, arguments.manifest, arguments.work)
    if arguments.action == "enrich":
        if arguments.network != "google-books":
            raise ValueError("L'enrichissement réseau exige --network google-books explicite")
        only = None
        if arguments.only_unresolved:
            only = {
                entry["source_sha256"]
                for entry in catalog["documents"]
                if entry["resolution"]["status"] in UNRESOLVED_STATES
            }
            print(f"reprise ciblée : {len(only)} entrée(s) à consulter")
        client = None
        if only is None or only:
            credentials = load_google_books_credentials()
            client = GoogleBooksClient(
                timeout=arguments.timeout,
                api_key=credentials.api_key,
            )
        catalog, report = enrich_catalog(
            manifest, catalog, client=client, work=arguments.work, only=only
        )
        save_catalog(catalog, arguments.catalog)
        report_path = arguments.catalog.with_name("enrichment-report.json")
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"consultations : {report['consultations']}")
        print(f"résolutions : {report['resolutions']}")
        return 0
    catalog = review_catalog(catalog, reviewed_at=arguments.reviewed_at, reviewer=arguments.reviewer)
    save_catalog(catalog, arguments.catalog)
    counts = Counter(entry["editorial_review"]["status"] for entry in catalog["documents"])
    print(f"revue éditoriale : {dict(counts)}")
    return 0
