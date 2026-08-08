from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

import pytest

from qualification.source_catalog.candidate_review import (
    CANDIDATE_REVIEWS,
    CandidateReviewError,
    apply_candidate_review,
)
from qualification.source_catalog.registry import build_skeleton, validate_catalog


SHA = "a" * 64


def _manifest() -> dict[str, Any]:
    return {"documents": [{"name": "livre.pdf", "sha256": SHA, "included": True}]}


def _entry(*candidate_ids: str) -> dict[str, Any]:
    catalog = build_skeleton(_manifest(), now="2026-08-08T00:00:00+00:00")
    entry = catalog["documents"][0]
    entry["provider_observations"] = [
        {
            "provider": "google_books",
            "observed_at": "2026-08-08T00:00:00+00:00",
            "status": "succeeded",
            "candidates": [
                {"candidate_id": identifier, "status": "candidate", "title": "Titre"}
                for identifier in candidate_ids
            ],
        }
    ]
    return entry


def _review(decisions: dict[str, str], **extra: Any) -> dict[str, Any]:
    return {
        "reviewer": "toba75",
        "reviewed_at": "2026-08-08",
        "decisions": decisions,
        "justification": "Revue de contrôle.",
        **extra,
    }


def _catalog(entry: dict[str, Any]) -> dict[str, Any]:
    catalog = build_skeleton(_manifest(), now="2026-08-08T00:00:00+00:00")
    catalog["documents"] = [entry]
    return catalog


def test_sans_revue_la_resolution_du_resolveur_est_conservee() -> None:
    entry = _entry("google_books:v1")

    assert apply_candidate_review(entry, "candidate", reviews={}) is None
    assert entry["resolution"]["status"] == "not_queried"


def test_un_rejet_integral_rend_rejected_et_trace_sa_preuve() -> None:
    entry = _entry("google_books:v1", "google_books:v2")
    reviews = {SHA: _review({"google_books:v1": "rejected", "google_books:v2": "rejected"})}

    assert apply_candidate_review(entry, "candidate", reviews=reviews) is None
    assert entry["resolution"]["status"] == "rejected"
    assert entry["resolution"]["proof"]["reviewer"] == "toba75"
    statuses = [
        candidate["status"]
        for observation in entry["provider_observations"]
        for candidate in observation["candidates"]
    ]
    assert statuses == ["rejected", "rejected"]


def test_une_acceptation_manuelle_porte_le_candidat_et_sa_preuve() -> None:
    entry = _entry("google_books:v1", "google_books:v2")
    reviews = {SHA: _review({"google_books:v1": "accepted", "google_books:v2": "rejected"})}

    accepted = apply_candidate_review(entry, "ambiguous", reviews=reviews)

    assert accepted is not None and accepted["candidate_id"] == "google_books:v1"
    assert entry["resolution"]["candidate_id"] == "google_books:v1"
    assert entry["resolution"]["proof"]["match"] == "manual_review"


def test_refuse_de_surclasser_une_correspondance_prouvee_par_identifiant() -> None:
    entry = _entry("google_books:v1")
    reviews = {SHA: _review({"google_books:v1": "rejected"})}

    with pytest.raises(CandidateReviewError, match="la preuve d'identifiant prime"):
        apply_candidate_review(entry, "accepted", reviews=reviews)


def test_refuse_une_revue_qui_nomme_un_candidat_non_observe() -> None:
    entry = _entry("google_books:v1")
    reviews = {SHA: _review({"google_books:absent": "rejected"})}

    with pytest.raises(CandidateReviewError, match="absent des observations"):
        apply_candidate_review(entry, "candidate", reviews=reviews)


def test_refuse_une_decision_inconnue() -> None:
    entry = _entry("google_books:v1")
    reviews = {SHA: _review({"google_books:v1": "peut-être"})}

    with pytest.raises(CandidateReviewError, match="décision inconnue"):
        apply_candidate_review(entry, "candidate", reviews=reviews)


def test_refuse_deux_editions_acceptees_sans_rien_ecrire() -> None:
    entry = _entry("google_books:v1", "google_books:v2")
    reviews = {SHA: _review({"google_books:v1": "accepted", "google_books:v2": "accepted"})}
    avant = deepcopy(entry)

    with pytest.raises(CandidateReviewError, match="une seule édition"):
        apply_candidate_review(entry, "ambiguous", reviews=reviews)

    # Un échec ne laisse pas deux candidats acceptés derrière lui.
    assert entry == avant


def _source_proof(value: str, ref: str) -> dict[str, Any]:
    return {
        "kind": "source_text",
        "locator": {"page": 2, "docling_ref": ref, "charspan": [0, len(value)]},
        "value": value,
    }


def test_refuse_une_revendication_que_les_preuves_citees_n_etablissent_pas() -> None:
    entry = _entry("google_books:v1")
    reviews = {
        SHA: _review(
            {"google_books:v1": "rejected"},
            source_claims={
                "title": "Titre inventé",
                "proofs": [_source_proof("Auteur", "#/texts/5")],
            },
        )
    }

    with pytest.raises(CandidateReviewError, match="valeur revendiquée sans preuve"):
        apply_candidate_review(entry, "candidate", reviews=reviews)


def test_une_acceptation_conserve_la_preuve_fournisseur_du_candidat() -> None:
    entry = _entry("google_books:v1")
    fournisseur = {
        "kind": "provider",
        "provider": "google_books",
        "resource_id": "v1",
        "observed_at": "2026-08-08T00:00:00+00:00",
    }
    entry["provider_observations"][0]["candidates"][0]["proof"] = fournisseur
    reviews = {SHA: _review({"google_books:v1": "accepted"})}

    accepted = apply_candidate_review(entry, "candidate", reviews=reviews)

    # La bibliographie dérivée doit rester rattachée à sa source, pas à la décision.
    assert accepted is not None and accepted["proof"] == fournisseur
    assert accepted["review"]["kind"] == "manual"
    assert entry["resolution"]["proof"]["kind"] == "manual"


def test_une_acceptation_par_revue_reste_idempotente() -> None:
    entry = _entry("google_books:v1")
    reviews = {SHA: _review({"google_books:v1": "accepted"})}

    apply_candidate_review(entry, "candidate", reviews=reviews)
    premier = deepcopy(entry)
    apply_candidate_review(entry, entry["resolution"]["status"], reviews=reviews)

    assert entry == premier


def test_une_valeur_prouvee_par_le_texte_source_reste_valide_sans_edition() -> None:
    entry = _entry("google_books:v1")
    titre = _source_proof("Titre prouvé", "#/texts/3")
    auteur = _source_proof("Auteur", "#/texts/5")
    reviews = {
        SHA: _review(
            {"google_books:v1": "rejected"},
            source_claims={
                "title": "Titre prouvé",
                "authors": ["Auteur"],
                "proofs": [titre, auteur],
            },
        )
    }

    apply_candidate_review(entry, "candidate", reviews=reviews)

    assert entry["bibliography"]["title"] == "Titre prouvé"
    assert entry["bibliography"]["authors"] == ["Auteur"]
    assert titre in entry["bibliography"]["provenance"]
    # Le titre prouvé ne crée aucune identité d'édition ni aucune date.
    assert entry["temporality"] == {
        "work_first_published": None,
        "edition_published": None,
        "content_revision": None,
    }
    assert not validate_catalog(_catalog(entry), _manifest())


def test_les_revues_reelles_respectent_le_contrat() -> None:
    for sha, review in CANDIDATE_REVIEWS.items():
        assert len(sha) == 64
        assert review["justification"] and review["reviewer"]
        assert set(review["decisions"].values()) <= {"accepted", "rejected"}
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", review["reviewed_at"])
        claims = review.get("source_claims") or {}
        proofs = claims.get("proofs", [])
        prouvees = {" ".join(str(proof["value"]).split()).casefold() for proof in proofs}
        for proof in proofs:
            assert proof["kind"] == "source_text"
            locator = proof["locator"]
            assert locator["page"] >= 1
            assert locator["docling_ref"].startswith("#/")
            debut, fin = locator["charspan"]
            assert fin - debut == len(proof["value"])
        # Toute valeur revendiquée par une revue réelle cite sa preuve.
        for value in [claims.get("title"), *claims.get("authors", [])]:
            if value:
                assert " ".join(str(value).split()).casefold() in prouvees
