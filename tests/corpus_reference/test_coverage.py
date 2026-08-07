from __future__ import annotations

import json
from pathlib import Path

import pytest

from qualification.corpus_reference.coverage import (
    ConverterUnreachable,
    aggregate,
    convert,
    lever_partition,
    main,
    measure,
    outcome,
    require_identical_versions,
    retained,
    summarize,
)


def _report(regions: list[dict], pages: list[dict]) -> dict:
    return {
        "status": "completed",
        "coverage": {"pages_total": len(pages)},
        "pages": pages,
        "alignment": {"pdf_source_math_regions": regions},
    }


def _manifest(*entries: dict) -> dict:
    return {"schema_version": 1, "documents": list(entries)}


def _document(name: str, sha: str, pages: int, *, included: bool = True) -> dict:
    return {"name": name, "sha256": sha, "pages": pages, "included": included}


def test_compte_les_verdicts_et_les_causes_de_non_verifiabilite() -> None:
    report = _report(
        regions=[
            {"candidate_status": "matching", "semantic_reasons": []},
            {
                "candidate_status": "not_evaluated",
                "semantic_reasons": [{"code": "pdf_font_exclusion_intersection"}],
                "candidate_link_reason": {"code": "docling_text_alignment_incomplete"},
            },
            {
                "candidate_status": "contradicting",
                "semantic_reasons": [{"code": "pdf_font_exclusion_intersection"}],
            },
        ],
        pages=[
            {"status": "partially_traced", "reasons": [{"code": "agl_mapping_required"}]},
            {"status": "unsupported", "reasons": [{"code": "agl_mapping_required"}]},
        ],
    )

    assert summarize(report) == {
        "status": "completed",
        "pages": 2,
        "regions": 3,
        "candidate_statuses": {"matching": 1, "not_evaluated": 1, "contradicting": 1},
        "page_statuses": {"partially_traced": 1, "unsupported": 1},
        "page_reasons": {"agl_mapping_required": 2},
        "region_reasons": {
            "pdf_font_exclusion_intersection": 2,
            "docling_text_alignment_incomplete": 1,
        },
    }


def test_ne_compte_aucune_cause_pour_une_region_prouvee() -> None:
    """Une région conforme n'alimente pas l'histogramme, même si elle porte une raison."""
    report = _report(
        regions=[
            {
                "candidate_status": "matching",
                "semantic_reasons": [{"code": "pdf_font_exclusion_intersection"}],
            }
        ],
        pages=[{"status": "traced", "reasons": []}],
    )

    assert summarize(report)["region_reasons"] == {}


def test_mesure_les_documents_retenus_du_plus_court_au_plus_long() -> None:
    manifest = _manifest(
        _document("long.pdf", "a" * 64, 400),
        _document("ecarte.pdf", "b" * 64, 10, included=False),
        _document("court.pdf", "c" * 64, 40),
    )

    assert [entry["name"] for entry in retained(manifest)] == ["court.pdf", "long.pdf"]


def test_signale_un_convertisseur_ferme_au_lieu_de_condamner_le_livre(
    tmp_path: Path,
) -> None:
    """Un port fermé est une panne d'infrastructure, pas un verdict sur le document."""
    illisible = tmp_path / "casse.pdf"
    illisible.write_bytes(b"ceci n'est pas un PDF")
    travail = tmp_path / "travail"
    travail.mkdir()

    with pytest.raises(ConverterUnreachable):
        outcome(illisible, travail, endpoint="http://127.0.0.1:1")


def test_agrege_les_livres_mesures_et_signale_les_autres(tmp_path: Path) -> None:
    manifest = _manifest(
        _document("mesure.pdf", "a" * 64, 40),
        _document("attendu.pdf", "b" * 64, 80),
    )
    (tmp_path / "aaaaaaaaaaaa").mkdir(parents=True)
    (tmp_path / "aaaaaaaaaaaa" / "outcome.json").write_text(
        json.dumps(
            {
                "name": "mesure.pdf",
                "sha256": "a" * 64,
                "outcome": "qualified",
                "pages": 40,
                "regions": 2,
                "candidate_statuses": {"matching": 1, "not_evaluated": 1},
                "page_statuses": {"unsupported": 40},
                "page_reasons": {"embedded_type1c_font_required": 12},
                "region_reasons": {"pdf_font_exclusion_intersection": 1},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "aaaaaaaaaaaa" / "report.json").write_text(
        json.dumps(
            {"alignment": {"pdf_source_math_regions": [
                {"candidate_status": "matching", "semantic_reasons": []},
                {"candidate_status": "not_evaluated",
                 "semantic_reasons": [{"code": "pdf_font_exclusion_intersection"}]},
            ]}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = aggregate(manifest, tmp_path)

    assert report["books_retained"] == 2
    assert report["books_qualified"] == 1
    assert report["books_not_measured"] == 1
    assert report["regions"] == 2
    assert report["candidate_statuses"] == {"matching": 1, "not_evaluated": 1}
    assert report["page_reasons"] == {"embedded_type1c_font_required": 12}
    assert [book["outcome"] for book in report["books"]] == ["qualified", "not_measured"]


def test_ecrit_le_rapport_de_couverture(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(_manifest(_document("attendu.pdf", "b" * 64, 80)), ensure_ascii=False),
        encoding="utf-8",
    )
    coverage_path = tmp_path / "coverage.json"

    code = main(
        [
            "aggregate",
            "--manifest", str(manifest_path),
            "--work", str(tmp_path / "work"),
            "--coverage", str(coverage_path),
        ]
    )

    assert code == 0
    written = json.loads(coverage_path.read_text(encoding="utf-8"))
    assert written["books_not_measured"] == 1
    assert written["books"][0]["name"] == "attendu.pdf"


def test_refuse_des_convertisseurs_de_versions_differentes(monkeypatch) -> None:
    """Mélanger deux versions de modèle rendrait l'histogramme ininterprétable."""
    versions = {
        "http://a/version": {"docling": "2.115.0"},
        "http://b/version": {"docling": "2.116.0"},
    }
    monkeypatch.setattr(
        "qualification.corpus_reference.coverage._get_json",
        lambda url, timeout: versions[url],
    )

    with pytest.raises(RuntimeError, match="piles différentes"):
        require_identical_versions(["http://a", "http://b"])

    versions["http://b/version"] = {"docling": "2.115.0"}
    assert require_identical_versions(["http://a", "http://b"]) == {"docling": "2.115.0"}


def test_tolere_des_noyaux_hotes_differents(monkeypatch) -> None:
    """Deux machines n'ont pas le même noyau ; cela ne change rien à la sortie du modèle."""
    versions = {
        "http://a/version": {"docling": "2.115.0", "plaform": "Linux-6.6.87.2"},
        "http://b/version": {"docling": "2.115.0", "plaform": "Linux-6.18.33.2"},
    }
    monkeypatch.setattr(
        "qualification.corpus_reference.coverage._get_json",
        lambda url, timeout: versions[url],
    )

    assert require_identical_versions(["http://a", "http://b"])["plaform"] == "Linux-6.6.87.2"


def test_repartit_les_livres_sur_plusieurs_convertisseurs(tmp_path: Path, monkeypatch) -> None:
    manifest = _manifest(
        _document("court.pdf", "a" * 64, 40),
        _document("moyen.pdf", "b" * 64, 80),
        _document("long.pdf", "c" * 64, 120),
    )
    monkeypatch.setattr(
        "qualification.corpus_reference.coverage.require_identical_versions",
        lambda endpoints: {},
    )
    served: list[str] = []
    monkeypatch.setattr(
        "qualification.corpus_reference.coverage.outcome",
        lambda pdf, destination, endpoint: served.append(endpoint)
        or {"name": pdf.name, "outcome": "failed", "failure": "convertisseur simulé"},
    )

    measure(manifest, tmp_path, ["http://a", "http://b"])

    assert len(served) == 3
    assert set(served) <= {"http://a", "http://b"}
    assert len(list(tmp_path.glob("*/outcome.json"))) == 3
    recorded = json.loads(next(tmp_path.glob("*/outcome.json")).read_text(encoding="utf-8"))
    assert recorded["endpoint"] in ("http://a", "http://b")


def test_ne_remesure_pas_un_livre_deja_mesure(tmp_path: Path, monkeypatch) -> None:
    manifest = _manifest(_document("deja.pdf", "a" * 64, 40))
    (tmp_path / "aaaaaaaaaaaa").mkdir(parents=True)
    (tmp_path / "aaaaaaaaaaaa" / "outcome.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "qualification.corpus_reference.coverage.require_identical_versions",
        lambda endpoints: {},
    )
    monkeypatch.setattr(
        "qualification.corpus_reference.coverage.outcome",
        lambda *args, **kwargs: pytest.fail("un livre déjà mesuré a été repris"),
    )

    measure(manifest, tmp_path, ["http://a"])


def test_reprend_un_livre_en_echec_sur_demande(tmp_path: Path, monkeypatch) -> None:
    """Un échec d'infrastructure doit pouvoir être rejoué, un succès jamais."""
    manifest = _manifest(
        _document("echoue.pdf", "a" * 64, 40),
        _document("reussi.pdf", "b" * 64, 50),
    )
    for digest, resultat in (("a" * 12, "failed"), ("b" * 12, "qualified")):
        (tmp_path / digest).mkdir(parents=True)
        (tmp_path / digest / "outcome.json").write_text(
            json.dumps({"outcome": resultat}), encoding="utf-8"
        )
    monkeypatch.setattr(
        "qualification.corpus_reference.coverage.require_identical_versions",
        lambda endpoints: {},
    )
    repris: list[str] = []
    monkeypatch.setattr(
        "qualification.corpus_reference.coverage.outcome",
        lambda pdf, destination, endpoint: repris.append(pdf.name)
        or {"name": pdf.name, "outcome": "failed", "failure": "convertisseur simulé"},
    )

    measure(manifest, tmp_path, ["http://a"])
    assert repris == []

    measure(manifest, tmp_path, ["http://a"], retry_failed=True)
    assert repris == ["echoue.pdf"]


def test_compte_une_page_entierement_tracee_sans_cle_reasons() -> None:
    """L'analyseur n'écrit `reasons` que s'il existe une limitation."""
    report = _report(
        regions=[],
        pages=[
            {"status": "traced"},
            {"status": "unsupported", "reasons": [{"code": "agl_mapping_required"}]},
        ],
    )

    resume = summarize(report)

    assert resume["page_statuses"] == {"traced": 1, "unsupported": 1}
    assert resume["page_reasons"] == {"agl_mapping_required": 1}


def test_consigne_un_rapport_illisible_au_lieu_de_tuer_le_creneau(
    tmp_path: Path, monkeypatch
) -> None:
    """Un rapport que l'on ne sait pas résumer est un résultat, pas un worker perdu."""
    monkeypatch.setattr(
        "qualification.corpus_reference.coverage.convert",
        lambda pdf, destination, endpoint: destination / "docling-document.json",
    )
    monkeypatch.setattr(
        "qualification.corpus_reference.coverage.qualify",
        lambda pdf, document, destination: _written(destination, '{"pages": []}'),
    )

    result = outcome(tmp_path / "livre.pdf", tmp_path, endpoint="http://a")

    assert result["outcome"] == "failed"
    assert "KeyError" in result["failure"]


def _written(destination: Path, content: str) -> Path:
    report = destination / "report.json"
    report.write_text(content, encoding="utf-8")
    return report


def test_ne_consigne_pas_un_convertisseur_injoignable_comme_echec_du_livre(
    tmp_path: Path, monkeypatch
) -> None:
    """Le redémarrage d'un serveur ne doit pas condamner toute la file restante."""
    manifest = _manifest(
        _document("un.pdf", "a" * 64, 40),
        _document("deux.pdf", "b" * 64, 50),
        _document("trois.pdf", "c" * 64, 60),
    )
    monkeypatch.setattr(
        "qualification.corpus_reference.coverage.require_identical_versions",
        lambda endpoints: {},
    )

    def coupe(pdf, destination, endpoint):
        raise ConverterUnreachable("http://a : connexion fermée")

    monkeypatch.setattr("qualification.corpus_reference.coverage.outcome", coupe)

    measure(manifest, tmp_path, ["http://a"])

    assert list(tmp_path.glob("*/outcome.json")) == []


def test_distingue_une_reponse_du_serveur_d_une_coupure(tmp_path: Path, monkeypatch) -> None:
    """Un refus HTTP est un résultat du document ; une coupure réseau n'en est pas un."""
    monkeypatch.setattr(
        "qualification.corpus_reference.coverage._post_json",
        lambda url, payload, timeout: (_ for _ in ()).throw(
            ConnectionResetError("connexion fermée par l'hôte distant")
        ),
    )
    (tmp_path / "livre.pdf").write_bytes(b"%PDF-1.4")

    with pytest.raises(ConverterUnreachable):
        convert(tmp_path / "livre.pdf", tmp_path, "http://a")


def test_partitionne_les_regions_par_famille_de_levier() -> None:
    regions = [
        {"candidate_status": "matching",
         "semantic_reasons": [{"code": "pdf_font_exclusion_intersection"}]},
        {"candidate_status": "not_evaluated",
         "semantic_reasons": [{"code": "pdf_font_exclusion_intersection"}]},
        {"candidate_status": "not_evaluated",
         "semantic_reasons": [{"code": "candidate_content_missing"}],
         "candidate_link_reason": {"code": "docling_text_alignment_incomplete"}},
        {"candidate_status": "not_evaluated",
         "semantic_reasons": [{"code": "pdf_font_exclusion_intersection"},
                              {"code": "candidate_content_missing"}]},
        {"candidate_status": "not_evaluated",
         "semantic_reasons": [{"code": "source_baseline_ambiguous"}]},
        {"candidate_status": "not_evaluated", "semantic_reasons": []},
    ]

    assert lever_partition(regions) == {
        "preuve_pdf_seule": 1,
        "docling_seule": 1,
        "les_deux": 1,
        "structure_ou_mixte": 1,
    }


def test_une_structure_melee_a_un_levier_n_est_attribuee_a_aucun() -> None:
    """Lever les polices ne libère pas une région dont la structure reste ambiguë."""
    regions = [
        {"candidate_status": "not_evaluated",
         "semantic_reasons": [{"code": "pdf_font_exclusion_intersection"},
                              {"code": "source_baseline_ambiguous"}]},
    ]

    assert lever_partition(regions) == {"structure_ou_mixte": 1}


def test_l_agregat_publie_la_partition_depuis_les_rapports(tmp_path: Path) -> None:
    manifest = _manifest(_document("mesure.pdf", "a" * 64, 40))
    (tmp_path / "aaaaaaaaaaaa").mkdir(parents=True)
    (tmp_path / "aaaaaaaaaaaa" / "outcome.json").write_text(
        json.dumps(
            {
                "name": "mesure.pdf", "sha256": "a" * 64, "outcome": "qualified",
                "pages": 40, "regions": 2,
                "candidate_statuses": {"not_evaluated": 2},
                "page_statuses": {}, "page_reasons": {}, "region_reasons": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "aaaaaaaaaaaa" / "report.json").write_text(
        json.dumps(
            {"alignment": {"pdf_source_math_regions": [
                {"candidate_status": "not_evaluated",
                 "semantic_reasons": [{"code": "pdf_font_exclusion_intersection"}]},
                {"candidate_status": "not_evaluated",
                 "semantic_reasons": [{"code": "candidate_content_missing"}]},
            ]}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = aggregate(manifest, tmp_path)

    assert report["lever_partition"] == {"preuve_pdf_seule": 1, "docling_seule": 1}


def test_un_code_http_d_infrastructure_ne_condamne_pas_le_livre(
    tmp_path: Path, monkeypatch
) -> None:
    """Un 404 décrit l'état du serveur, pas le document : le livre reste à mesurer."""
    import io
    from urllib.error import HTTPError as UrllibHTTPError

    def http_error(code):
        def raiser(url, payload, timeout):
            raise UrllibHTTPError(url, code, "motif", None, io.BytesIO(b"corps"))
        return raiser

    (tmp_path / "livre.pdf").write_bytes(b"%PDF-1.4")

    monkeypatch.setattr("qualification.corpus_reference.coverage._post_json", http_error(404))
    with pytest.raises(ConverterUnreachable, match="HTTP 404"):
        convert(tmp_path / "livre.pdf", tmp_path, "http://a")

    monkeypatch.setattr("qualification.corpus_reference.coverage._post_json", http_error(422))
    with pytest.raises(RuntimeError, match="Conversion refusée \(422.*corps"):
        convert(tmp_path / "livre.pdf", tmp_path, "http://a")


def test_l_outcome_porte_l_identite_du_convertisseur(tmp_path: Path, monkeypatch) -> None:
    """La pile vérifiée au lancement est consignée dans chaque résultat."""
    manifest = _manifest(_document("livre.pdf", "a" * 64, 40))
    monkeypatch.setattr(
        "qualification.corpus_reference.coverage.require_identical_versions",
        lambda endpoints: {"docling": "2.115.0"},
    )
    monkeypatch.setattr(
        "qualification.corpus_reference.coverage.outcome",
        lambda pdf, destination, endpoint: {"name": pdf.name, "outcome": "failed",
                                            "failure": "simulé"},
    )

    measure(manifest, tmp_path, ["http://a"])

    recorded = json.loads(next(tmp_path.glob("*/outcome.json")).read_text(encoding="utf-8"))
    assert recorded["converter_versions"] == {"docling": "2.115.0"}
