import json

import pytest

from experiments.paddle_formula_spike.picture_experiment import (
    clamp_bbox,
    evaluate,
    oriented_bbox,
    pdf_bbox,
    picture_specs,
    relative_bbox,
)
from pdf_math_audit.mathml_candidate import candidate_analysis


def test_pdf_bbox_scales_docling_page_coordinates() -> None:
    bbox = {"l": 140.0, "t": 120.0, "r": 940.0, "b": 580.0, "coord_origin": "TOPLEFT"}

    assert pdf_bbox(
        bbox,
        docling_width=1080,
        docling_height=1332,
        pdf_width=540,
        pdf_height=666,
    ) == [70.0, 60.0, 470.0, 290.0]


def test_relative_bbox_uses_crop_origin_and_render_scale() -> None:
    assert relative_bbox([80, 70, 100, 90], [70, 60, 470, 290], 4, 4) == [
        40,
        40,
        120,
        120,
    ]


def test_clamp_bbox_absorbs_subpixel_rounding_outside_crop() -> None:
    assert clamp_bbox([-0.2, 10, 100.1, 110], 100, 100) == [0.0, 10, 100.0, 100.0]


@pytest.mark.parametrize(
    ("angle", "expected"),
    [
        (-1, [10, 20, 30, 40]),
        (0, [10, 20, 30, 40]),
        (90, [20, 70, 40, 90]),
        (180, [70, 160, 90, 180]),
        (270, [160, 10, 180, 30]),
    ],
)
def test_oriented_bbox_matches_paddle_preprocessor_coordinates(
    angle: int, expected: list[int]
) -> None:
    assert oriented_bbox([10, 20, 30, 40], angle, 100, 200) == expected


def test_evaluate_maps_source_region_to_oriented_prediction(tmp_path) -> None:
    tokens, signature, rejection = candidate_analysis("x")
    assert rejection is None
    manifest = {
        "pictures": [
            {
                "picture_ref": "#/pictures/1",
                "page": 1,
                "width": 100,
                "height": 200,
                "regions": [
                    {
                        "region_id": "source:1",
                        "page": 1,
                        "rendered_bbox": [10, 20, 30, 40],
                        "source_tokens": tokens,
                        "source_signature": signature,
                    }
                ],
            }
        ]
    }
    predictions = {
        "model_load_seconds": 1,
        "inference_seconds": 2,
        "pictures": [
            {
                "picture_ref": "#/pictures/1",
                "result": {
                    "doc_preprocessor_res": {"angle": 270},
                    "formula_res_list": [
                        {
                            "formula_region_id": 1,
                            "rec_formula": "x",
                            "dt_polys": [150, 0, 190, 40],
                        }
                    ],
                },
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    predictions_path = tmp_path / "predictions.json"
    output_path = tmp_path / "results.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    predictions_path.write_text(json.dumps(predictions), encoding="utf-8")

    result = evaluate(manifest_path, predictions_path, output_path)

    assert result["summary"]["detected_regions"] == 1
    assert result["summary"]["exact_regions"] == 1


def test_picture_specs_rejects_a_missing_picture() -> None:
    insertions = [{"docling_ref": "#/pictures/10", "page": 36}]

    with pytest.raises(ValueError, match="Missing Docling pictures: #/pictures/10"):
        picture_specs({"pictures": []}, insertions)
