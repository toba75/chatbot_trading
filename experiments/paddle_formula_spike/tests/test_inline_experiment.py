import json

from experiments.paddle_formula_spike.inline_experiment import (
    _assess_application,
    evaluate,
    evaluate_source,
)
from experiments.paddle_formula_spike.inline_html_audit import accepted_source_record


def _record() -> dict[str, object]:
    return {
        "region_id": "pdf-source:1:1",
        "target_id": "pdf-source:1:1",
        "page": 1,
        "candidate_text": "wx",
        "candidate_format": "mixed_text",
        "source_tokens": ["w", "x"],
        "source_signature": ["<bold>", "w", "x", "</bold>"],
        "source_region": {
            "docling_ref": "#/texts/0",
            "candidate_charspan": [0, 2],
            "candidate_tokens": ["w", "x"],
            "source_tokens": ["w", "x"],
            "source_canonical_tokens": ["w", "x"],
            "source_relation_signature": ["<bold>", "w", "x", "</bold>"],
        },
    }


def test_applique_une_prediction_exactement_prouvee() -> None:
    result = _assess_application(_record(), r"\mathbf{w x}")

    assert result["paddle_exact"] is True
    assert result["applicable"] is True
    assert result["after"] == r"$\mathbf{w x}$"


def test_evaluate_compte_les_rejets_de_preuve(tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    predictions = tmp_path / "predictions.json"
    output = tmp_path / "results.json"
    manifest.write_text(json.dumps({"records": [_record()]}), encoding="utf-8")
    predictions.write_text(
        json.dumps(
            {
                "model": "PP-FormulaNet_plus-L",
                "device": "gpu:0",
                "model_load_seconds": 1.0,
                "inference_seconds": 2.0,
                "results": [
                    {"region_id": "pdf-source:1:1", "rec_formula": "w_y"}
                ],
            }
        ),
        encoding="utf-8",
    )

    result = evaluate(manifest, predictions, output)

    assert result["summary"]["exact"] == 0
    assert result["summary"]["applicable"] == 0
    assert result["summary"]["rejections"] == {"region_not_exact": 1}


def test_evaluate_source_mesure_le_chemin_deterministe(tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    output = tmp_path / "results.json"
    manifest.write_text(json.dumps({"records": [_record()]}), encoding="utf-8")

    result = evaluate_source(manifest, output)

    assert result["summary"]["applicable"] == 1
    assert result["summary"]["rejections"] == {}


def test_materialise_une_correction_source_rejouable() -> None:
    assessed = _assess_application(_record(), r"\mathbf{w x}")

    accepted = accepted_source_record(_record() | assessed)

    assert accepted["status"] == "accepted"
    assert accepted["docling_ref"] == "#/texts/0"
    assert accepted["charspan"] == [0, 2]
    assert accepted["proposal"] == r"\mathbf{w x}"
