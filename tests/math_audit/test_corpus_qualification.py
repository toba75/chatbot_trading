from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pypdf import PdfReader

import qualification.math_audit.qualify as qualification_runner
from qualification.math_audit.capture import _require_pages, request_payload
from qualification.math_audit.corpus import build_corpus
from qualification.math_audit.file_integrity import require_hash
from qualification.math_audit.measurement import (
    _assertions_covered,
    _expectation_met,
    measure,
)
from qualification.math_audit.qualify import (
    _observed_mutation,
    _validate_manifest,
    _validate_oracle,
    _verify_independent_proofs,
    qualify,
)
from qualification.math_audit.runtime import _require_model_assets


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_la_capture_docling_demande_exclusivement_le_pipeline_vlm_granite() -> None:
    payload = request_payload("corpus.pdf", b"pdf")

    assert payload["sources"][0]["filename"] == "corpus.pdf"
    assert payload["options"] == {
        "from_formats": ["pdf"],
        "to_formats": ["json"],
        "pipeline": "vlm",
        "vlm_pipeline_preset": "default",
        "document_timeout": 86400,
        "abort_on_error": True,
        "include_images": False,
        "include_page_images": False,
        "images_scale": 2.0,
        "image_export_mode": "placeholder",
    }
    assert payload["target"] == {"kind": "inbody"}


def test_la_capture_exige_exactement_les_pages_du_pdf_source() -> None:
    class Document:
        pages = {1: object(), 2: object()}

    _require_pages(Document(), 2)

    with pytest.raises(RuntimeError, match="Pages Docling inattendues"):
        _require_pages(Document(), 4)


def test_la_preuve_runtime_refuse_un_actif_granite_modifie(tmp_path: Path) -> None:
    model = tmp_path / "ibm-granite--granite-docling-258M"
    model.mkdir()
    asset = model / "config.json"
    asset.write_bytes(b"version exacte")
    manifest = {
        "assets": [
            {
                "relative_path": (
                    "ibm-granite--granite-docling-258M/config.json"
                ),
                "sha256": _sha256(asset),
            }
        ]
    }

    _require_model_assets(tmp_path, manifest)
    asset.write_bytes(b"version differente")

    with pytest.raises(RuntimeError, match="Empreinte Granite inattendue"):
        _require_model_assets(tmp_path, manifest)


def test_le_corpus_genere_est_deterministe_et_son_oracle_exhaustif(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"

    build_corpus(first)
    build_corpus(second)

    assert _sha256(first / "math-regression.pdf") == _sha256(
        second / "math-regression.pdf"
    )
    assert (first / "oracle.json").read_bytes() == (second / "oracle.json").read_bytes()

    oracle = json.loads((first / "oracle.json").read_text(encoding="utf-8"))
    assert oracle["exhaustive"] is True
    assert {page["source_kind"] for page in oracle["pages"]} == {
        "born_digital_type1",
        "born_digital_type0_cid",
        "born_digital_rotated",
        "scanned_raster",
    }
    assert {region["layout"] for region in oracle["regions"]} == {
        "inline",
        "display",
    }
    assert all(region["evidence"]["kind"] == "generator_geometry" for region in oracle["regions"])
    reader = PdfReader(first / "math-regression.pdf")
    page_two_fonts = reader.pages[1]["/Resources"]["/Font"]
    assert any(
        font.get_object()["/Subtype"] == "/Type0"
        for font in page_two_fonts.values()
    )
    assert reader.pages[2]["/Rotate"] == 90
    assert reader.pages[3].extract_text() == ""


def test_l_oracle_reel_est_exhaustif_et_independant_des_candidats() -> None:
    root = Path(__file__).parents[2]
    oracle_path = root / "qualification" / "math_audit" / "real_book" / "oracle.json"
    source_path = (
        root / "experiments" / "math_pipeline_comparison" / "source-pages-7-10.pdf"
    )
    oracle = json.loads(oracle_path.read_text(encoding="utf-8"))

    assert oracle["exhaustive"] is True
    assert oracle["representative"] is True
    assert oracle["source_pdf_sha256"] == _sha256(source_path)
    proofs = oracle["independent_proofs"]
    assert {proof["id"] for proof in proofs} == {
        "source-glyph-proof",
        "page-1-render-600dpi",
        "page-2-render-600dpi",
    }
    for proof in proofs:
        assert proof["sha256"] == _sha256(oracle_path.parent / proof["path"])
    assert oracle["granularity"] == "contiguous_typeset_mathematical_expression"
    assert len(oracle["regions"]) == 53
    assert {region["page"] for region in oracle["regions"]} == {1, 2}
    assert len({region["id"] for region in oracle["regions"]}) == 53
    assert all(region["semantic_assertions"] for region in oracle["regions"])
    assert all(region["evidence"]["kind"] == "source_glyph_and_render" for region in oracle["regions"])
    assert all("candidate" not in region["evidence"]["reference"] for region in oracle["regions"])
    assert oracle["expected_non_verifiable"] == {}

    expected_critical = {
        "p2-04": "wx\u2212b=0",
        "p2-13": "w\u2217",
        "p2-32": "wxi\u2212b\u22651ifyi=+1",
        "p2-33": "wxi\u2212b\u2264\u22121ifyi=\u22121",
    }
    regions = {region["id"]: region for region in oracle["regions"]}
    assert {
        identifier: regions[identifier]["semantic_assertions"][0]["expected"]
        for identifier in expected_critical
    } == expected_critical


def test_le_gate_lit_et_verifie_chaque_preuve_independante(
    tmp_path: Path,
) -> None:
    proof = tmp_path / "proof.json"
    proof.write_bytes(b'{"source":"independent"}')
    oracle_path = tmp_path / "oracle.json"
    oracle = {
        "independent_proofs": [
            {
                "id": "source-glyph-proof",
                "path": proof.name,
                "sha256": _sha256(proof),
            }
        ]
    }

    assert _verify_independent_proofs(oracle_path, oracle) == oracle["independent_proofs"]

    proof.write_bytes(b'{"source":"corrupted"}')
    with pytest.raises(ValueError, match="Empreinte inattendue"):
        _verify_independent_proofs(oracle_path, oracle)


def test_les_assertions_reelles_sont_realisables_depuis_les_glyphes_source() -> None:
    root = Path(__file__).parents[2]
    oracle = json.loads(
        (
            root / "qualification" / "math_audit" / "real_book" / "oracle.json"
        ).read_text(encoding="utf-8")
    )
    regions = {region["id"]: region for region in oracle["regions"]}

    assert _assertions_covered(
        regions["p1-02"],
        {"verdict": "conformant_within_scope", "source_tokens": ["x", "i"]},
    )
    assert _assertions_covered(
        regions["p1-05"],
        {
            "verdict": "conformant_within_scope",
            "source_tokens": ["x", "(", "j", ")"],
        },
    )


def test_un_refus_attendu_est_exact_sans_devenir_une_preuve_semantique() -> None:
    expected = {
        "semantic_assertions": [{"relation": "sequence", "expected": "wx−b=0"}],
        "expected_verdict": "non_verifiable",
        "expected_reason": "source_signal_conflict",
    }
    observed = {
        "verdict": "non_verifiable",
        "semantic_reasons": [{"code": "source_signal_conflict"}],
        "source_tokens": list("wx−b=0"),
    }

    assert _expectation_met(expected, observed)
    assert not _assertions_covered(expected, observed)


def test_le_manifeste_exige_la_preuve_complete_sur_le_corpus_reel() -> None:
    root = Path(__file__).parents[2]
    manifest = json.loads(
        (root / "qualification" / "math_audit" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["thresholds"]["traceability_coverage"] == 1.0
    assert manifest["thresholds"]["semantic_expectation_accuracy"] == 1.0
    assert manifest["thresholds"]["detection_precision"] == 1.0
    real = next(corpus for corpus in manifest["corpora"] if corpus["representative"])
    assert real["id"] == "real-book-pages-3-and-6-v1"
    assert real["exhaustive_oracle"] is True
    assert not manifest["representative_inputs_without_exhaustive_oracle"]
    requirements = manifest["runtime_requirements"]
    provenance = json.loads(
        (root / "qualification" / "math_audit" / real["candidate_provenance"]).read_text(
            encoding="utf-8"
        )
    )
    assert requirements.items() <= provenance["runtime_proof"].items()
    assert provenance["runtime_proof"]["model_manifest_sha256"] == _sha256(
        root / "config" / "granite-docling-258M.manifest.json"
    )
    assert provenance["runtime_proof"]["model_assets_verified"] == 17


def test_le_corpus_non_representatif_mesure_les_limites_sans_bloquer() -> None:
    root = Path(__file__).parents[2]

    report = qualify(root / "qualification" / "math_audit" / "manifest.json")

    generated = next(corpus for corpus in report["corpora"] if not corpus["representative"])
    assert generated["metrics"]["detection_recall"] == 0.0
    assert "detection_recall_below_threshold" not in report["blocking_reasons"]
    assert "detection_precision_below_threshold" not in report["blocking_reasons"]
    assert "traceability_coverage_below_threshold" not in report["blocking_reasons"]
    assert "semantic_expectation_accuracy_below_threshold" not in report["blocking_reasons"]
    assert report["accepted"] is True


def test_la_qualification_mesure_separement_detection_trace_et_semantique() -> None:
    oracle = {
        "exhaustive": True,
        "representative": False,
        "regions": [
            {
                "id": "r1",
                "page": 1,
                "bbox": [10, 10, 30, 30],
                "semantic_assertions": [{"relation": "sequence", "expected": "x"}],
            },
            {
                "id": "r2",
                "page": 1,
                "bbox": [40, 10, 60, 30],
                "semantic_assertions": [{"relation": "sequence", "expected": "y"}],
            },
        ]
    }
    audit = {
        "alignment": {
            "regions": [],
            "pdf_source_math_regions": [
                {
                    "region_id": "candidate-1",
                    "page": 1,
                    "bbox": [10, 10, 30, 30],
                    "status": "traced",
                    "verdict": "conformant_within_scope",
                    "source_tokens": ["x"],
                },
                {
                    "region_id": "candidate-extra",
                    "page": 1,
                    "bbox": [70, 10, 90, 30],
                    "status": "not_traced",
                    "verdict": "non_verifiable",
                },
            ],
        }
    }
    result = measure(oracle["regions"], audit, 0.5)

    metrics = result["metrics"]
    assert metrics == {
        "oracle_regions": 2,
        "candidate_regions": 2,
        "matched_regions": 1,
        "candidate_regions_by_localization_method": {
            "docling_provenance_bbox": 2
        },
        "matched_regions_by_localization_method": {
            "docling_provenance_bbox": 1
        },
        "detection_recall": 0.5,
        "detection_precision": 0.5,
        "traceability_coverage": 0.5,
        "semantic_coverage": 0.5,
        "semantic_assertion_coverage": 0.5,
        "semantic_expectation_accuracy": 0.5,
        "false_alignments": 1,
    }
    assert result["missed_oracle_regions"] == ["r2"]
    assert result["false_alignment_regions"] == ["candidate-extra"]
    assert result["matches"] == [
        {
            "oracle_region": "r1",
            "candidate_region": "candidate-1",
            "localization_method": "docling_provenance_bbox",
            "iou": 1.0,
        }
    ]


def test_un_faux_conforme_sur_une_mutation_bloque_l_acceptation(
    tmp_path: Path,
) -> None:
    manifest = {
        "schema_version": 1,
        "iou_threshold": 0.5,
        "thresholds": {
            "detection_recall": 1.0,
            "detection_precision": 1.0,
            "false_conformant_mutations": 0,
            "traceability_coverage": 0.0,
            "semantic_expectation_accuracy": 0.0,
        },
        "corpora": [],
        "mutations": [
            {
                "id": "wrong-oracle-expectation",
                "source": "x",
                "candidate": "x",
                "expected": "contradicted",
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = qualify(manifest_path)

    assert report["mutations"]["false_conformant"] == 1
    assert "false_conformant_mutation" in report["blocking_reasons"]


def test_une_precision_arbitrairement_faible_bloque_le_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    proof_path = tmp_path / "independent-proof.json"
    proof_path.write_text('{"source":"independent"}', encoding="utf-8")
    oracle = {
        "exhaustive": True,
        "representative": True,
        "independent_proofs": [
            {
                "id": "independent-proof",
                "path": proof_path.name,
                "sha256": _sha256(proof_path),
            }
        ],
        "regions": [
            {
                "id": "expected",
                "page": 1,
                "bbox": [0, 0, 10, 10],
                "semantic_assertions": [{"relation": "sequence", "expected": "x"}],
            }
        ],
    }
    oracle_path = tmp_path / "oracle.json"
    oracle_path.write_text(json.dumps(oracle), encoding="utf-8")
    candidates = [
        {
            "region_id": "correct",
            "page": 1,
            "bbox": [0, 0, 10, 10],
            "status": "traced",
            "verdict": "conformant_within_scope",
            "source_tokens": ["x"],
        }
    ] + [
        {
            "region_id": f"parasite-{index}",
            "page": 1,
            "bbox": [20 + index, 0, 21 + index, 1],
            "status": "not_traced",
            "verdict": "non_verifiable",
        }
        for index in range(99)
    ]
    monkeypatch.setattr(
        qualification_runner,
        "_audit",
        lambda _root, _corpus, _runtime: (
            {
                "alignment": {
                    "regions": [],
                    "pdf_source_math_regions": candidates,
                }
            },
            {},
        ),
    )
    manifest = {
        "schema_version": 1,
        "iou_threshold": 0.5,
        "thresholds": {
            "detection_recall": 1.0,
            "detection_precision": 1.0,
            "false_conformant_mutations": 0,
            "traceability_coverage": 1.0,
            "semantic_expectation_accuracy": 1.0,
        },
        "corpora": [
            {
                "id": "precision-counterexample",
                "oracle": oracle_path.name,
                "oracle_sha256": _sha256(oracle_path),
                "exhaustive_oracle": True,
                "representative": True,
            }
        ],
        "runtime_requirements": {},
        "mutations": [],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = qualify(manifest_path)

    assert report["corpora"][0]["metrics"]["detection_precision"] == 0.01
    assert "detection_precision_below_threshold" in report["blocking_reasons"]


def test_apparie_une_detection_et_compte_le_doublon_comme_faux_positif() -> None:
    oracle = [
        {
            "id": "r1",
            "page": 1,
            "bbox": [10, 10, 30, 30],
            "semantic_assertions": [{"relation": "sequence", "expected": "x"}],
        }
    ]
    candidates = [
        {
            "region_id": identifier,
            "page": 1,
            "bbox": [10, 10, 30, 30],
            "status": "traced",
            "verdict": "conformant_within_scope",
        }
        for identifier in ("first", "duplicate")
    ]

    result = measure(
        oracle,
        {"alignment": {"regions": [], "pdf_source_math_regions": candidates}},
        0.5,
    )

    assert result["metrics"]["matched_regions"] == 1
    assert result["metrics"]["false_alignments"] == 1
    assert len(result["false_alignment_regions"]) == 1


def test_signale_une_detection_superposee_sous_le_seuil_iou() -> None:
    oracle = [
        {
            "id": "wide-source-box",
            "page": 1,
            "bbox": [0, 0, 20, 20],
            "semantic_assertions": [{"relation": "sequence", "expected": "x"}],
        }
    ]
    audit = {
        "alignment": {
            "regions": [],
            "pdf_source_math_regions": [
                {
                    "region_id": "tight-candidate-box",
                    "page": 1,
                    "bbox": [5, 5, 15, 15],
                    "status": "traced",
                    "verdict": "conformant_within_scope",
                }
            ],
        }
    }

    result = measure(oracle, audit, 0.5)

    assert result["metrics"]["matched_regions"] == 0
    assert result["same_page_overlaps_below_threshold"] == [
        {
            "oracle_region": "wide-source-box",
            "candidate_region": "tight-candidate-box",
            "iou": 0.25,
        }
    ]


def test_ne_qualifie_pas_de_provenance_une_region_sans_boite() -> None:
    audit = {
        "alignment": {
            "regions": [],
            "pdf_source_math_regions": [
                {
                    "region_id": "inline-non-localise",
                    "kind": "inline_math",
                    "page": 1,
                    "bbox": None,
                    "status": "not_traced",
                    "verdict": "non_verifiable",
                }
            ],
        }
    }

    result = measure([], audit, 0.5)

    assert result["metrics"]["candidate_regions_by_localization_method"] == {
        "not_localized": 1
    }
    assert result["metrics"]["matched_regions_by_localization_method"] == {}


def test_refuse_les_proprietes_oracle_auto_declarees_et_le_raccourci_observed() -> None:
    oracle = {
        "exhaustive": False,
        "representative": False,
        "regions": [
            {
                "id": "r1",
                "semantic_assertions": [{"relation": "sequence", "expected": "x"}],
            }
        ],
    }
    corpus = {
        "id": "invalid",
        "exhaustive_oracle": True,
        "representative": False,
    }

    with pytest.raises(ValueError, match="exhaustive incohérente"):
        _validate_oracle(oracle, corpus)
    with pytest.raises(ValueError, match="Contrat de mutation invalide"):
        _observed_mutation(
            {"id": "shortcut", "expected": "contradicted", "observed": "contradicted"}
        )

    oracle["exhaustive"] = True
    oracle["representative"] = True
    corpus["representative"] = True
    with pytest.raises(ValueError, match="Preuves indépendantes manquantes"):
        _validate_oracle(oracle, corpus)


def test_bloque_tant_que_les_seuils_de_preuve_ne_sont_pas_fixes(
    tmp_path: Path,
) -> None:
    manifest = {
        "schema_version": 1,
        "iou_threshold": 0.5,
        "thresholds": {
            "detection_recall": 1.0,
            "detection_precision": 1.0,
            "false_conformant_mutations": 0,
            "traceability_coverage": None,
            "semantic_expectation_accuracy": None,
        },
        "corpora": [],
        "mutations": [],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = qualify(manifest_path)

    assert "proof_coverage_thresholds_missing" in report["blocking_reasons"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("iou_threshold", 0.0),
        ("detection_recall", -0.1),
        ("detection_precision", 1.1),
        ("traceability_coverage", 1.1),
        ("semantic_expectation_accuracy", -0.1),
        ("false_conformant_mutations", -1),
    ],
)
def test_refuse_les_seuils_hors_domaine(field: str, value: float) -> None:
    manifest = {
        "schema_version": 1,
        "iou_threshold": 0.5,
        "thresholds": {
            "detection_recall": 1.0,
            "detection_precision": 1.0,
            "false_conformant_mutations": 0,
            "traceability_coverage": None,
            "semantic_expectation_accuracy": None,
        },
        "corpora": [],
        "mutations": [],
    }
    target = manifest if field == "iou_threshold" else manifest["thresholds"]
    target[field] = value

    with pytest.raises(ValueError, match="Seuil invalide"):
        _validate_manifest(manifest)


def test_designe_une_conversion_de_fin_de_ligne_plutot_qu_une_preuve_alteree(
    tmp_path: Path,
) -> None:
    original = b'{"regions":\n[]}\n'
    artefact = tmp_path / "docling-response.json"
    artefact.write_bytes(original.replace(b"\n", b"\r\n"))

    with pytest.raises(ValueError, match="converties en CRLF"):
        require_hash(artefact, hashlib.sha256(original).hexdigest())

    artefact.write_bytes(b'{"regions": ["altere"]}')
    with pytest.raises(ValueError, match="Empreinte inattendue") as altered:
        require_hash(artefact, hashlib.sha256(original).hexdigest())
    assert "CRLF" not in str(altered.value)
