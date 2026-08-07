"""Mesure de couverture du corpus : conversion Docling puis qualification en mode audit.

Aucun oracle n'est requis. Le but n'est pas de juger la justesse des formules mais
de dresser l'histogramme des causes de non-vérifiabilité, livre par livre, afin de
savoir où la généralisation du pipeline paierait le plus.

La mesure est reprenable : un livre déjà mesuré est ignoré, et l'échec d'un livre
est consigné comme résultat plutôt que propagé — un PDF sauvage qui fait tomber le
pipeline est une donnée de cette étape.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

from docling_core.types.doc import DoclingDocument

from pdf_math_audit.contract import CAPABILITY_PROFILE, CONTRACT_VERSION
from qualification.corpus_reference.manifest import CORPUS, MANIFEST
from qualification.math_audit.capture import _get_json, _post_json, request_payload

ENDPOINT = "http://127.0.0.1:5001"
WORK = Path(__file__).resolve().parent / "work"
COVERAGE = CORPUS.parent / "corpus_coverage" / "coverage.json"

_CONVERSION_TIMEOUT = 86_400


def _json_bytes(value: Any) -> bytes:
    if isinstance(value, str):
        return value.encode("utf-8")
    return json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")


class ConverterUnreachable(RuntimeError):
    """Le convertisseur ne répond plus : le livre n'a pas été mesuré.

    À distinguer d'un échec du document. Sans cette distinction, le redémarrage
    d'un serveur ferait échouer en cascade toute la file restante, à la vitesse
    des erreurs de connexion.
    """


def convert(pdf: Path, destination: Path, endpoint: str) -> Path:
    """Écrit le DoclingDocument du PDF. Une conversion déjà présente est conservée."""
    document = destination / "docling-document.json"
    if document.exists():
        return document
    try:
        payload = _post_json(
            f"{endpoint.rstrip('/')}/v1/convert/source",
            request_payload(pdf.name, pdf.read_bytes()),
            _CONVERSION_TIMEOUT,
        )
    except HTTPError as error:
        # Seul un refus explicite de la requête (400, 422) est un constat sur le
        # document. Un 404 ou un 5xx décrit l'état du serveur : le consigner
        # condamnerait le livre pour une panne d'infrastructure.
        if error.code in (400, 422):
            body = error.read()[:500].decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Conversion refusée ({error.code} {error.reason}) : {body}"
            ) from error
        raise ConverterUnreachable(
            f"{endpoint} : HTTP {error.code} {error.reason}"
        ) from error
    except OSError as error:
        raise ConverterUnreachable(f"{endpoint} : {error}") from error
    if payload.get("status") != "success" or payload.get("errors"):
        raise RuntimeError(
            f"Conversion Docling refusée : {payload.get('status')}, {payload.get('errors')}"
        )
    content = _json_bytes(payload["document"]["json_content"])
    DoclingDocument.model_validate_json(content)
    document.write_bytes(content)
    return document


def qualify(pdf: Path, document: Path, destination: Path) -> Path:
    """Qualifie via le CLI de production, dans un processus isolé du balayage."""
    report = destination / "report.json"
    subprocess.run(
        [
            sys.executable, "-m", "pdf_math_audit.cli", str(pdf),
            "--docling-document", str(document),
            "--source-sha256", hashlib.sha256(pdf.read_bytes()).hexdigest(),
            "--docling-document-sha256", hashlib.sha256(document.read_bytes()).hexdigest(),
            "--contract-version", CONTRACT_VERSION,
            "--capability-profile", CAPABILITY_PROFILE,
            "--report", str(report),
            "--evidence", str(destination / "evidence.ndjson.gz"),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return report


def summarize(report: dict[str, Any]) -> dict[str, Any]:
    """Extrait d'un rapport d'analyse ce que l'étape mesure : verdicts et causes de refus."""
    regions = report["alignment"]["pdf_source_math_regions"]
    reasons: collections.Counter[str] = collections.Counter()
    for region in regions:
        if region.get("candidate_status") == "matching":
            continue
        reasons.update(_region_reasons(region))
    return {
        "status": report["status"],
        "pages": report["coverage"]["pages_total"],
        "regions": len(regions),
        "candidate_statuses": dict(
            collections.Counter(region.get("candidate_status") for region in regions)
        ),
        "page_statuses": dict(
            collections.Counter(page["status"] for page in report["pages"])
        ),
        # Une page entièrement tracée ne porte aucune clé `reasons` : l'absence de
        # limitation n'est pas une limitation vide.
        "page_reasons": dict(
            collections.Counter(
                reason["code"]
                for page in report["pages"]
                for reason in page.get("reasons", ())
            )
        ),
        "region_reasons": dict(reasons),
    }


FAMILLE_PREUVE_PDF = frozenset({
    "pdf_font_exclusion_intersection",
    "pdf_opaque_region_intersection",
    "authoritative_tounicode_control_invalid",
})
FAMILLE_DOCLING = frozenset({
    "candidate_content_missing",
    "docling_text_alignment_incomplete",
    "docling_text_container_missing",
    "docling_text_container_ambiguous",
    "docling_picture_candidate_missing",
    "candidate_latex_invalid",
    "candidate_mixed_text_invalid",
    "candidate_command_unsupported",
    "candidate_relation_invalid",
    "candidate_relation_unsupported",
})


def _region_reasons(region: dict[str, Any]) -> set[str]:
    reasons = {reason["code"] for reason in region.get("semantic_reasons") or []}
    link = region.get("candidate_link_reason")
    if link:
        reasons.add(link["code"])
    return reasons


def lever_partition(regions: list[dict[str, Any]]) -> dict[str, int]:
    """Partition des régions non conformes par famille de levier.

    Une région n'est attribuée à un levier que si sa famille la bloque seule :
    lever une cause ne libère rien tant qu'une autre famille bloque encore.
    """
    buckets: collections.Counter[str] = collections.Counter()
    for region in regions:
        if region.get("candidate_status") == "matching":
            continue
        reasons = _region_reasons(region)
        if not reasons:
            continue
        preuve = bool(reasons & FAMILLE_PREUVE_PDF)
        docling = bool(reasons & FAMILLE_DOCLING)
        autres = bool(reasons - FAMILLE_PREUVE_PDF - FAMILLE_DOCLING)
        if preuve and not docling and not autres:
            buckets["preuve_pdf_seule"] += 1
        elif docling and not preuve and not autres:
            buckets["docling_seule"] += 1
        elif preuve and docling and not autres:
            buckets["les_deux"] += 1
        else:
            buckets["structure_ou_mixte"] += 1
    return dict(buckets)


def outcome(pdf: Path, destination: Path, endpoint: str) -> dict[str, Any]:
    """Convertit puis qualifie un livre dans un répertoire déjà créé par l'appelant."""
    started = time.monotonic()
    try:
        document = convert(pdf, destination, endpoint)
        converted = time.monotonic()
        report = json.loads(qualify(pdf, document, destination).read_text(encoding="utf-8"))
        measured = summarize(report)
    except ConverterUnreachable:
        raise
    except Exception as error:
        detail = error.stderr.strip()[-2000:] if isinstance(error, subprocess.CalledProcessError) else str(error)
        return {
            "name": pdf.name,
            "outcome": "failed",
            "failure": f"{type(error).__name__}: {detail}",
            "seconds": round(time.monotonic() - started, 1),
        }
    return {
        "name": pdf.name,
        "outcome": "qualified",
        "conversion_seconds": round(converted - started, 1),
        "qualification_seconds": round(time.monotonic() - converted, 1),
        **measured,
    }


def retained(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Les documents à mesurer, du plus court au plus long : l'histogramme s'étoffe plus vite."""
    return sorted(
        (entry for entry in manifest["documents"] if entry["included"]),
        key=lambda entry: entry["pages"],
    )


def require_identical_versions(endpoints: list[str]) -> dict[str, Any]:
    """Refuse des convertisseurs de piles différentes : l'histogramme mélangerait deux modèles.

    Le noyau hôte (`plaform`) est écarté de la comparaison : il varie d'une machine
    à l'autre sans rien changer à la sortie du modèle, contrairement aux versions
    des bibliothèques docling et de l'interpréteur.
    """
    versions = {
        endpoint: _get_json(f"{endpoint.rstrip('/')}/version", 30) for endpoint in endpoints
    }
    stacks = {
        endpoint: {name: value for name, value in version.items() if name != "plaform"}
        for endpoint, version in versions.items()
    }
    if len({json.dumps(stack, sort_keys=True) for stack in stacks.values()}) > 1:
        raise RuntimeError(f"Convertisseurs de piles différentes : {stacks}")
    return versions[endpoints[0]]


def _measured(destination: Path, retry_failed: bool) -> bool:
    recorded = destination / "outcome.json"
    if not recorded.exists():
        return False
    if not retry_failed:
        return True
    return json.loads(recorded.read_text(encoding="utf-8")).get("outcome") != "failed"


def measure(
    manifest: dict[str, Any],
    work: Path,
    endpoints: list[str],
    retry_failed: bool = False,
) -> None:
    """Distribue les livres sur les convertisseurs disponibles ; chacun tire le suivant.

    Une file partagée plutôt qu'un découpage fixe : les livres vont de 36 à 454
    pages, et une répartition figée laisserait un convertisseur inoccupé.
    """
    versions = require_identical_versions(endpoints)
    documents = retained(manifest)
    pending: queue.Queue[dict[str, Any]] = queue.Queue()
    for entry in documents:
        if not _measured(work / entry["sha256"][:12], retry_failed):
            pending.put(entry)
    remaining = pending.qsize()
    print(f"{remaining} livre(s) à mesurer sur {len(documents)}, {len(endpoints)} convertisseur(s)", flush=True)

    def drain(endpoint: str) -> None:
        while True:
            try:
                entry = pending.get_nowait()
            except queue.Empty:
                return
            destination = work / entry["sha256"][:12]
            destination.mkdir(parents=True, exist_ok=True)
            print(f"  {entry['pages']:4}p {entry['name'][:56]} -> {endpoint}", flush=True)
            try:
                measured = outcome(CORPUS / entry["name"], destination, endpoint)
            except ConverterUnreachable as error:
                pending.put(entry)
                print(f"        convertisseur injoignable, créneau arrêté : {error}", flush=True)
                return
            result = measured | {
                "sha256": entry["sha256"],
                "declared_pages": entry["pages"],
                "endpoint": endpoint,
                "converter_versions": versions,
            }
            (destination / "outcome.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print(f"        {result['outcome']} {result.get('failure', '')[:90]}", flush=True)

    workers = [threading.Thread(target=drain, args=(endpoint,)) for endpoint in endpoints]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()


def aggregate(manifest: dict[str, Any], work: Path) -> dict[str, Any]:
    books = []
    for entry in retained(manifest):
        recorded = work / entry["sha256"][:12] / "outcome.json"
        books.append(
            json.loads(recorded.read_text(encoding="utf-8"))
            if recorded.exists()
            else {"name": entry["name"], "sha256": entry["sha256"], "outcome": "not_measured"}
        )
    qualified = [book for book in books if book["outcome"] == "qualified"]
    totals: collections.Counter[str] = collections.Counter()
    page_reasons: collections.Counter[str] = collections.Counter()
    region_reasons: collections.Counter[str] = collections.Counter()
    partition: collections.Counter[str] = collections.Counter()
    for book in qualified:
        totals.update(book["candidate_statuses"])
        page_reasons.update(book["page_reasons"])
        region_reasons.update(book["region_reasons"])
        report_path = work / book["sha256"][:12] / "report.json"
        partition.update(
            lever_partition(
                json.loads(report_path.read_text(encoding="utf-8"))["alignment"][
                    "pdf_source_math_regions"
                ]
            )
        )
    return {
        "schema_version": 1,
        "books_retained": len(books),
        "books_qualified": len(qualified),
        "books_failed": sum(book["outcome"] == "failed" for book in books),
        "books_not_measured": sum(book["outcome"] == "not_measured" for book in books),
        "pages_qualified": sum(book["pages"] for book in qualified),
        "regions": sum(book["regions"] for book in qualified),
        "candidate_statuses": dict(totals.most_common()),
        "lever_partition": dict(partition.most_common()),
        "page_reasons": dict(page_reasons.most_common()),
        "region_reasons": dict(region_reasons.most_common()),
        "books": books,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["measure", "aggregate"])
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--work", type=Path, default=WORK)
    parser.add_argument("--coverage", type=Path, default=COVERAGE)
    parser.add_argument(
        "--endpoint",
        action="append",
        dest="endpoints",
        help=(
            "Convertisseur Docling, répétable. Chaque occurrence est une requête "
            "en vol : répéter la même adresse exploite plusieurs workers du même "
            "serveur, en citer une autre ajoute une machine."
        ),
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help=(
            "Reprend les livres consignés en échec. Un incident d'infrastructure "
            "ne doit pas figer définitivement le résultat d'un livre."
        ),
    )
    arguments = parser.parse_args(argv)
    manifest = json.loads(arguments.manifest.read_text(encoding="utf-8"))

    if arguments.action == "measure":
        arguments.work.mkdir(parents=True, exist_ok=True)
        measure(
            manifest,
            arguments.work,
            arguments.endpoints or [ENDPOINT],
            arguments.retry_failed,
        )
        return 0

    report = aggregate(manifest, arguments.work)
    arguments.coverage.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"{report['books_qualified']}/{report['books_retained']} livres qualifiés, "
        f"{report['books_failed']} en échec, {report['regions']} régions, "
        f"rapport écrit dans {arguments.coverage}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
