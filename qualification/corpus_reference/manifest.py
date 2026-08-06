"""Manifeste du corpus de référence : empreintes, couche de texte et décisions.

Les fichiers du corpus sont conservés hors dépôt ; ce manifeste est la seule
trace committée de leur identité. Il fixe aussi, pour chaque document, la
décision d'inclusion dans l'index RAG et son motif.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import fitz

SCHEMA_VERSION = 1
CORPUS = Path(__file__).resolve().parents[2] / "docs" / "corpus_reference"
MANIFEST = CORPUS / "manifest.json"

CONSERVATION = "outside_repository"
CONSERVATION_REASON = (
    "Livres sous droit d'auteur : les fichiers restent hors du dépôt et hors du "
    "dépôt distant. Seul ce manifeste atteste leur identité."
)

# Un document sans couche de texte rédigée est écarté par cette règle, sans
# décision manuelle : le pipeline prouve les glyphes issus des octets du PDF, et
# une sortie d'OCR est un contenu produit qui ne peut pas passer pour la source.
UNUSABLE_TEXT_LAYER = {
    "scanned": (
        "Numérisation sans couche de texte : la preuve du pipeline décode les "
        "glyphes des octets du PDF, ce qu'un scan ne fournit pas. Un OCR serait "
        "nécessaire ; il n'existe pas à ce jour."
    ),
    "ocr": (
        "Couche de texte produite par OCR au-dessus d'une numérisation : contenu "
        "généré, qui ne peut pas se présenter comme contenu source, et dont les "
        "glyphes synthétiques rendraient toute preuve fictive."
    ),
}

# Décisions éditoriales, hors règle ci-dessus.
EXCLUSIONS = {
    "document.pdf": (
        "Doublon exact de short-term-trading-strategies-that-work-.pdf "
        "(même SHA-256), que sa couche de texte issue d'un OCR écarte aussi."
    ),
    "high frequency trading.pdf": (
        "Même ouvrage que high-frequency-trading-maureen-o-mara-pdf-free.pdf : "
        "257 pages et texte identiques, même producteur ; le nom portant "
        "l'autrice est conservé."
    ),
    "trading-on-momentum.pdf": (
        "Même ouvrage que trading-on-momentum-advanced-techniques-for-high-"
        "percentage-day-trading.pdf, refondu par un outil tiers "
        "(Multivalent Merge) ; la sortie Distiller d'origine est conservée."
    ),
}

_SAMPLE_PAGES = 12
_TEXT_PAGE_CHARACTERS = 200
_PAGE_COVERAGE = 0.5


def _sampled_pages(pages: int) -> range:
    """Pages représentatives : les toutes premières sont images même en typographie native."""
    start = max(1, pages // 20)
    return range(start, pages, max(1, (pages - start) // _SAMPLE_PAGES))


def _page_evidence(page: fitz.Page) -> tuple[bool, bool]:
    area = abs(page.rect.get_area()) or 1.0
    covered = any(
        block["type"] == 1
        and abs(fitz.Rect(block["bbox"]).get_area()) > area * _PAGE_COVERAGE
        for block in page.get_text("dict")["blocks"]
    )
    return len(page.get_text().strip()) >= _TEXT_PAGE_CHARACTERS, covered


def text_layer(document: fitz.Document) -> str:
    """Origine de la couche de texte : rédigée, produite par OCR, ou absente.

    Un raster couvrant la page sous du texte signe une sortie d'OCR : un ouvrage
    nativement numérique n'empile pas les deux sur la majorité de ses pages.
    """
    evidence = [
        _page_evidence(document.load_page(index))
        for index in _sampled_pages(len(document))
    ] or [_page_evidence(document.load_page(0))]
    majority = len(evidence) / 2
    if sum(text and covered for text, covered in evidence) > majority:
        return "ocr"
    if sum(text for text, _covered in evidence) > majority:
        return "text"
    return "scanned"


def describe(path: Path) -> dict[str, Any]:
    with fitz.open(path) as document:
        layer = text_layer(document)
        entry = {
            "name": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
            "pages": len(document),
            "text_layer": layer,
        }
    reason = EXCLUSIONS.get(path.name) or UNUSABLE_TEXT_LAYER.get(layer)
    entry["included"] = reason is None
    if reason is not None:
        entry["exclusion_reason"] = reason
    return entry


def documents(corpus: Path) -> list[Path]:
    """Tout le contenu du corpus, hormis le manifeste qui y réside sans s'y décrire.

    MuPDF ouvrant aussi bien un texte brut qu'un PDF, un fichier étranger serait
    décrit comme un ouvrage : il est refusé plutôt que dilué dans le manifeste.
    """
    content = sorted(path for path in corpus.iterdir() if path != MANIFEST)
    intruders = [path.name for path in content if path.suffix.lower() != ".pdf"]
    if intruders:
        raise ValueError(f"Fichiers étrangers dans {corpus} : {', '.join(intruders)}")
    return content


def build(corpus: Path) -> dict[str, Any]:
    described = [describe(path) for path in documents(corpus)]
    if not described:
        raise ValueError(
            f"Aucun document dans {corpus} : un manifeste vide effacerait la seule "
            "attestation d'identité du corpus."
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "conservation": CONSERVATION,
        "conservation_reason": CONSERVATION_REASON,
        "documents": described,
    }


def differences(corpus: Path, manifest: dict[str, Any]) -> list[str]:
    """Écarts entre le manifeste et ce que le corpus et les décisions produisent aujourd'hui."""
    current = build(corpus)
    described = {entry["name"]: entry for entry in current["documents"]}
    declared = {entry["name"]: entry for entry in manifest["documents"]}
    issues = [
        f"{name} : présent dans le corpus, absent du manifeste"
        for name in sorted(described.keys() - declared.keys())
    ] + [
        f"{name} : déclaré au manifeste, absent du corpus"
        for name in sorted(declared.keys() - described.keys())
    ]
    for name in sorted(described.keys() & declared.keys()):
        drift = sorted(
            field
            for field in described[name].keys() | declared[name].keys()
            if described[name].get(field) != declared[name].get(field)
        )
        if drift:
            issues.append(f"{name} : {', '.join(drift)} ne correspond plus au corpus")
    issues.extend(
        f"{field} : en-tête du manifeste dépassé"
        for field in sorted(set(current) - {"documents"})
        if manifest.get(field) != current[field]
    )
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "verify"])
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    arguments = parser.parse_args(argv)

    if arguments.action == "build":
        manifest = build(arguments.corpus)
        arguments.manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        retained = sum(entry["included"] for entry in manifest["documents"])
        print(
            f"{len(manifest['documents'])} documents décrits, {retained} retenus, "
            f"manifeste écrit dans {arguments.manifest}"
        )
        return 0

    manifest = json.loads(arguments.manifest.read_text(encoding="utf-8"))
    issues = differences(arguments.corpus, manifest)
    for issue in issues:
        print(issue)
    print(f"{len(issues)} écart(s) entre {arguments.corpus} et {arguments.manifest}")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
