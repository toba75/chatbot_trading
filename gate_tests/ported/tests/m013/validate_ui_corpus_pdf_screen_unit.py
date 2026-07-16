"""Tests unitaires du read-model du corpus PDF après ADR-038."""

from __future__ import annotations

import pytest

from app.platform.ui_corpus import (
    CorpusPdfDocument,
    CorpusPdfScreenState,
    build_registration_payload,
    ensure_no_destructive_ui_fields,
    render_corpus_pdf_screen,
)


def _document(**overrides) -> CorpusPdfDocument:
    values = {
        "document_id": "DOC-M013-UI-0001",
        "title": "Rapport",
        "authors": ("Auteur",),
        "publication_year": 2026,
        "edition": "1",
        "metadata_status": "EXTRACTED",
        "source_status": "REGISTERED",
        "diagnostic_status": "ROUTE_PLANNED",
        "conversion_status": "CANONICAL_ACCEPTED",
        "canonical_version_id": "CANON-M013-UI-0001",
        "projection_status": "SEARCHABLE",
        "conversion_action_available": False,
        "selected": True,
    }
    values.update(overrides)
    return CorpusPdfDocument(**values)


def _metadonnees_pending_sont_coherentes_et_non_selectionnables() -> None:
    pending = _document(
        title=None,
        authors=None,
        publication_year=None,
        edition=None,
        metadata_status="PENDING",
        conversion_status="CONVERSION_NOT_REQUESTED",
        canonical_version_id=None,
        projection_status="PROJECTION_NOT_REQUESTED",
        selected=False,
    )
    assert pending.selectable_for_conversation is False
    with pytest.raises(ValueError, match="métadonnées en attente incohérentes"):
        _document(metadata_status="PENDING")


def _metadonnees_extraites_exigent_titre_et_auteurs() -> None:
    with pytest.raises(ValueError, match="titre requis"):
        _document(title=None)
    with pytest.raises(ValueError, match="auteurs requis"):
        _document(authors=None)


def _formulaire_admet_uniquement_le_pdf() -> None:
    payload = build_registration_payload(original_content=b"%PDF-1.7\n")
    assert payload == {"original_content": b"%PDF-1.7\n"}
    with pytest.raises(ValueError, match="original_content requis"):
        build_registration_payload(original_content=b"")
    with pytest.raises(ValueError, match="champ UI destructif interdit"):
        ensure_no_destructive_ui_fields({"delete": True})


def _rendu_echappe_les_metadonnees_et_affiche_leur_etat() -> None:
    unsafe = _document(
        title="<script>alert('x')</script>",
        authors=("A&B",),
        publication_year=None,
        edition=None,
    )
    state = CorpusPdfScreenState(
        documents=(unsafe,),
        active_selected_document_ids=(unsafe.document_id,),
        read_model_status="READ_MODEL_READY",
    )
    html = render_corpus_pdf_screen(state)
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert "Métadonnées : EXTRACTED" in html
    assert "Auteurs : A&amp;B" in html
    assert "Année : Non renseignée" in html


def test_validate_ui_corpus_pdf_screen_unit() -> None:
    _metadonnees_pending_sont_coherentes_et_non_selectionnables()
    _metadonnees_extraites_exigent_titre_et_auteurs()
    _formulaire_admet_uniquement_le_pdf()
    _rendu_echappe_les_metadonnees_et_affiche_leur_etat()
