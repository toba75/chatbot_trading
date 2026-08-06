from __future__ import annotations

import hashlib
import json

from experiments.nougat_shadow.evaluation import (
    _assess_target,
    _reject_cross_target_reuse,
    evaluate,
    extract_math,
)
from experiments.nougat_shadow.experiment import _load_inputs, shadow_targets


def test_extract_math_preserve_inline_and_display_order() -> None:
    assert extract_math(r"Text \(x_i\), then \[y^2\] and $z$.") == [
        "x_i",
        "y^2",
        "z",
    ]


def test_shadow_targets_select_only_effective_vision_calls() -> None:
    corrections = {
        "records": [
            {
                "target_id": "selected",
                "kind": "replacement",
                "page": 1,
                "status": "rejected",
                "source_proofs": [
                    {
                        "region_id": "r1",
                        "candidate_charspan": [0, 1],
                        "candidate_text": "x",
                        "tokens": ["x"],
                        "signature": ["x"],
                    }
                ],
                "region_id": "r1",
                "before": "x",
                "proposals": [{"vision_proposal": "x"}],
            },
            {
                "target_id": "insertion",
                "kind": "formula_insertion",
                "page": 1,
                "status": "rejected",
                "source_proofs": [
                    {
                        "region_id": "r1",
                        "candidate_charspan": None,
                        "candidate_text": "",
                        "tokens": ["x"],
                        "signature": ["x"],
                    }
                ],
                "region_id": "r1",
                "before": "",
                "proposals": [{"vision_proposal": "x"}],
            },
            {
                "target_id": "deterministic",
                "kind": "replacement",
                "page": 1,
                "status": "accepted",
                "source_proofs": [],
                "proposals": [{"selected_engine": "deterministic_source"}],
            },
        ]
    }
    report = {
        "alignment": {
            "pdf_source_math_regions": [{"region_id": "r1", "bbox": [1, 2, 3, 4]}]
        }
    }

    result = shadow_targets(corrections, report)

    assert [target["target_id"] for target in result] == ["selected"]
    assert result[0]["proofs"][0]["bbox"] == [1, 2, 3, 4]


def test_prepare_refuse_un_pdf_etranger_aux_preuves(tmp_path) -> None:
    pdf = tmp_path / "source.pdf"
    corrections = tmp_path / "corrections.json"
    report = tmp_path / "report.json"
    pdf.write_bytes(b"%PDF-foreign")
    corrections.write_text(json.dumps({"records": []}), encoding="utf-8")
    report.write_text(
        json.dumps(
            {
                "pdf": {"sha256": "a" * 64},
                "contract": {"source_sha256": "a" * 64},
                "alignment": {"pdf_source_math_regions": []},
            }
        ),
        encoding="utf-8",
    )

    try:
        _load_inputs(pdf, corrections, report)
    except ValueError as error:
        assert str(error) == "le PDF ne correspond pas aux preuves du rapport"
    else:
        raise AssertionError("Un PDF étranger doit être rejeté")


def test_load_inputs_refuse_des_corrections_non_referencees(tmp_path) -> None:
    pdf = tmp_path / "source.pdf"
    corrections = tmp_path / "corrections.json"
    report = tmp_path / "report.json"
    pdf.write_bytes(b"%PDF-source")
    pdf_sha256 = hashlib.sha256(pdf.read_bytes()).hexdigest()
    corrections.write_text(json.dumps({"records": []}), encoding="utf-8")
    report.write_text(
        json.dumps(
            {
                "pdf": {"sha256": pdf_sha256},
                "contract": {"source_sha256": pdf_sha256},
                "correction": {
                    "artifacts": {"corrections": {"bytes": 1, "sha256": "a" * 64}}
                },
            }
        ),
        encoding="utf-8",
    )

    try:
        _load_inputs(pdf, corrections, report)
    except ValueError as error:
        assert str(error) == "les corrections ne correspondent pas au rapport"
    else:
        raise AssertionError("Des corrections étrangères doivent être rejetées")


def test_assess_target_refuses_ambiguous_exact_matches() -> None:
    target = {
        "target_id": "t1",
        "kind": "replacement",
        "before": "x",
        "proofs": [{"tokens": ["x"], "signature": ["x"]}],
    }
    candidates = [
        {"index": 0, "tokens": ["x"], "signature": ["x"], "parse_rejection": None},
        {"index": 1, "tokens": ["x"], "signature": ["x"], "parse_rejection": None},
    ]

    result = _assess_target(target, candidates)

    assert result["shadow_status"] == "partial_or_ambiguous"
    assert result["proofs"][0]["status"] == "exact_ambiguous"


def test_assess_target_rejoue_l_application_sans_modifier_le_document() -> None:
    target = {
        "target_id": "t1",
        "kind": "replacement",
        "before": "x",
        "candidate_format": "mixed_text",
        "proofs": [
            {
                "candidate_charspan": [0, 1],
                "candidate_text": "x",
                "tokens": ["x"],
                "signature": ["x"],
            }
        ],
    }
    candidates = [
        {
            "index": 0,
            "latex": "x",
            "tokens": ["x"],
            "signature": ["x"],
            "parse_rejection": None,
        }
    ]

    result = _assess_target(target, candidates)

    assert result["shadow_status"] == "applicable_exact"
    assert result["after"] == "$x$"


def test_assess_target_refuse_de_reutiliser_une_formule() -> None:
    target = {
        "target_id": "t1",
        "kind": "formula_replacement",
        "before": "xx",
        "proofs": [
            {
                "candidate_charspan": [0, 1],
                "candidate_text": "x",
                "tokens": ["x"],
                "signature": ["x"],
            },
            {
                "candidate_charspan": [1, 2],
                "candidate_text": "x",
                "tokens": ["x"],
                "signature": ["x"],
            },
        ],
    }
    candidates = [
        {
            "index": 0,
            "latex": "x",
            "tokens": ["x"],
            "signature": ["x"],
            "parse_rejection": None,
        }
    ]

    result = _assess_target(target, candidates)

    assert result["shadow_status"] == "partial_or_ambiguous"
    assert result["application_reason"] == "candidate_mapping_not_unique_or_monotonic"


def test_reject_cross_target_reuse() -> None:
    targets = [
        {
            "target_id": target_id,
            "page": 1,
            "shadow_status": "applicable_exact",
            "proofs": [{"status": "exact_unique", "candidate_indices": [0]}],
            "after": "x",
            "mathml": "<math />",
        }
        for target_id in ("t1", "t2")
    ]

    _reject_cross_target_reuse(targets)

    assert {target["shadow_status"] for target in targets} == {"partial_or_ambiguous"}
    assert all("after" not in target for target in targets)


def test_reject_cross_target_reuse_with_partial_target() -> None:
    targets = [
        {
            "target_id": "complete",
            "page": 1,
            "shadow_status": "applicable_exact",
            "proofs": [{"status": "exact_unique", "candidate_indices": [0]}],
            "after": "x",
            "mathml": "<math />",
        },
        {
            "target_id": "partial",
            "page": 1,
            "shadow_status": "partial_or_ambiguous",
            "proofs": [
                {"status": "exact_unique", "candidate_indices": [0]},
                {"status": "no_exact_match", "candidate_indices": []},
            ],
        },
    ]

    _reject_cross_target_reuse(targets)

    assert targets[0]["shadow_status"] == "partial_or_ambiguous"
    assert targets[0]["application_reason"] == "candidate_reused_across_targets"


def test_evaluate_requires_matching_mmd_hash(tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    predictions = tmp_path / "predictions.json"
    output = tmp_path / "result.json"
    (tmp_path / "page.mmd").write_text(r"\(x\)", encoding="utf-8")
    manifest.write_text(
        json.dumps({"pages": [{"page": 1}], "targets": []}), encoding="utf-8"
    )
    predictions.write_text(
        json.dumps(
            {
                "model": "nougat",
                "revision": "revision",
                "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                "model_load_seconds": 1,
                "inference_seconds": 2,
                "pages": [{"page": 1, "mmd": "page.mmd", "mmd_sha256": "0" * 64}],
            }
        ),
        encoding="utf-8",
    )

    try:
        evaluate(manifest, predictions, output)
    except ValueError as error:
        assert "empreinte MMD invalide" in str(error)
    else:
        raise AssertionError("L'empreinte incorrecte doit être rejetée")
