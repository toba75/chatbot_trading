from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz
import pytest

from qualification.corpus_reference.manifest import (
    EXCLUSIONS,
    MANIFEST,
    build,
    describe,
    differences,
    main,
    text_layer,
)


def _book(path: Path, pages: int, *, layer: str, text_pages: int | None = None) -> Path:
    """Ouvrage de test : texte rédigé, texte d'OCR sur raster, ou raster seul."""
    document = fitz.open()
    raster = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 400, 560))
    raster.clear_with(220)
    written = pages if text_pages is None else text_pages
    for number in range(pages):
        page = document.new_page(width=400, height=560)
        if layer in ("scanned", "ocr"):
            page.insert_image(page.rect, pixmap=raster)
        if layer == "text" or (layer == "ocr" and number < written):
            page.insert_textbox(
                page.rect + (40, 40, -40, -40),
                f"Page {number}. " + "chapitre analyse du marche " * 20,
            )
    document.save(path)
    document.close()
    return path


def _corpus(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    _book(directory / "retenu.pdf", 30, layer="text")
    return directory


def test_distingue_le_texte_redige_de_l_ocr_et_du_scan(tmp_path: Path) -> None:
    for name, layer in (("texte", "text"), ("scan", "scanned"), ("ocr", "ocr")):
        with fitz.open(_book(tmp_path / f"{name}.pdf", 30, layer=layer)) as document:
            assert text_layer(document) == layer


def test_exige_une_majorite_de_pages_textuelles(tmp_path: Path) -> None:
    """Quelques pages océrisées ne suffisent pas : la majorité décide."""
    minoritaire = _book(tmp_path / "minoritaire.pdf", 30, layer="ocr", text_pages=3)
    majoritaire = _book(tmp_path / "majoritaire.pdf", 30, layer="ocr", text_pages=28)

    with fitz.open(minoritaire) as document:
        assert text_layer(document) == "scanned"
    with fitz.open(majoritaire) as document:
        assert text_layer(document) == "ocr"


def test_ecarte_par_regle_un_document_sans_couche_de_texte_redigee(tmp_path: Path) -> None:
    scan = describe(_book(tmp_path / "scan.pdf", 30, layer="scanned"))
    ocr = describe(_book(tmp_path / "ocr.pdf", 30, layer="ocr"))

    assert scan["included"] is False
    assert "Numérisation sans couche de texte" in scan["exclusion_reason"]
    assert ocr["included"] is False
    assert "produite par OCR" in ocr["exclusion_reason"]


def test_decrit_chaque_document_du_corpus(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path / "corpus")

    manifest = build(corpus)

    assert [entry["name"] for entry in manifest["documents"]] == ["retenu.pdf"]
    entry = manifest["documents"][0]
    assert entry["sha256"] == hashlib.sha256((corpus / "retenu.pdf").read_bytes()).hexdigest()
    assert entry["pages"] == 30
    assert entry["text_layer"] == "text"
    assert entry["included"] is True
    assert "exclusion_reason" not in entry


def test_publie_le_motif_d_une_exclusion_declaree(tmp_path: Path, monkeypatch) -> None:
    corpus = _corpus(tmp_path / "corpus")
    _book(corpus / "ecarte.pdf", 10, layer="text")
    monkeypatch.setitem(EXCLUSIONS, "ecarte.pdf", "doublon exact de retenu.pdf")

    manifest = build(corpus)

    ecarte = next(e for e in manifest["documents"] if e["name"] == "ecarte.pdf")
    assert ecarte["included"] is False
    assert ecarte["exclusion_reason"] == "doublon exact de retenu.pdf"


def test_refuse_de_decrire_un_corpus_vide(tmp_path: Path) -> None:
    vide = tmp_path / "vide"
    vide.mkdir()

    with pytest.raises(ValueError, match="manifeste vide"):
        build(vide)


def test_refuse_un_fichier_qui_n_est_pas_un_pdf(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path / "corpus")
    (corpus / "notes.txt").write_text("note du libraire", encoding="utf-8")

    with pytest.raises(ValueError, match="Fichiers étrangers.*notes.txt"):
        build(corpus)


def test_ne_signale_aucun_ecart_sur_un_corpus_conforme(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path / "corpus")

    assert differences(corpus, build(corpus)) == []


def test_refuse_un_document_absent_du_manifeste(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path / "corpus")
    manifest = build(corpus)
    _book(corpus / "intrus.pdf", 5, layer="text")

    assert differences(corpus, manifest) == [
        "intrus.pdf : présent dans le corpus, absent du manifeste"
    ]


def test_refuse_une_entree_sans_document(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path / "corpus")
    manifest = build(corpus)
    (corpus / "retenu.pdf").unlink()
    _book(corpus / "autre.pdf", 5, layer="text")

    assert "retenu.pdf : déclaré au manifeste, absent du corpus" in differences(
        corpus, manifest
    )


def test_refuse_un_document_modifie(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path / "corpus")
    manifest = build(corpus)
    _book(corpus / "retenu.pdf", 31, layer="text")

    assert differences(corpus, manifest) == [
        "retenu.pdf : bytes, pages, sha256 ne correspond plus au corpus"
    ]


def test_refuse_un_manifeste_dont_la_decision_est_perimee(
    tmp_path: Path, monkeypatch
) -> None:
    """Une exclusion ajoutée sans reconstruction laisse le manifeste en désaccord."""
    corpus = _corpus(tmp_path / "corpus")
    manifest = build(corpus)
    monkeypatch.setitem(EXCLUSIONS, "retenu.pdf", "doublon découvert après coup")

    assert differences(corpus, manifest) == [
        "retenu.pdf : exclusion_reason, included ne correspond plus au corpus"
    ]


def test_refuse_un_en_tete_de_manifeste_depasse(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path / "corpus")
    manifest = build(corpus) | {"schema_version": 0}

    assert differences(corpus, manifest) == [
        "schema_version : en-tête du manifeste dépassé"
    ]


def test_chaque_exclusion_declaree_designe_un_document_du_corpus_reel() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    declared = {entry["name"] for entry in manifest["documents"]}

    assert set(EXCLUSIONS) <= declared, set(EXCLUSIONS) - declared


def test_la_verification_echoue_sur_un_ecart(tmp_path: Path, capsys) -> None:
    corpus = _corpus(tmp_path / "corpus")
    manifest_path = tmp_path / "manifest.json"
    arguments = ["--corpus", str(corpus), "--manifest", str(manifest_path)]

    assert main(["build", *arguments]) == 0
    assert main(["verify", *arguments]) == 0

    _book(corpus / "intrus.pdf", 5, layer="text")
    assert main(["verify", *arguments]) == 1
    assert "absent du manifeste" in capsys.readouterr().out


def test_le_manifeste_ecrit_est_trie_indente_et_accentue(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path / "corpus")
    _book(corpus / "ecarte.pdf", 10, layer="scanned")
    manifest_path = tmp_path / "manifest.json"

    main(["build", "--corpus", str(corpus), "--manifest", str(manifest_path)])

    written = manifest_path.read_text(encoding="utf-8")
    assert json.loads(written) == build(corpus)
    assert '\n  "conservation"' in written
    assert written.index('"bytes"') < written.index('"included"') < written.index('"name"')
    assert "Numérisation" in written
    assert written.endswith("\n")


def test_le_manifeste_ne_se_decrit_pas_lui_meme(tmp_path: Path, monkeypatch) -> None:
    corpus = _corpus(tmp_path / "corpus")
    manifest_path = corpus / "manifest.json"
    monkeypatch.setattr(
        "qualification.corpus_reference.manifest.MANIFEST", manifest_path
    )
    arguments = ["--corpus", str(corpus), "--manifest", str(manifest_path)]

    assert main(["build", *arguments]) == 0
    assert main(["build", *arguments]) == 0
    assert main(["verify", *arguments]) == 0

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert [entry["name"] for entry in manifest["documents"]] == ["retenu.pdf"]
