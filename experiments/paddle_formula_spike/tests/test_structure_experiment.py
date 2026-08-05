import pytest

from experiments.paddle_formula_spike.structure_experiment import (
    contains_center,
    insertion_regions,
    polygon_bbox,
)


def test_polygon_bbox_accepts_points() -> None:
    assert polygon_bbox([[10, 20], [40, 20], [40, 60], [10, 60]]) == [
        10,
        20,
        40,
        60,
    ]
    assert polygon_bbox([10, 20, 40, 60]) == [10, 20, 40, 60]


def test_contains_center_accepts_a_source_region_inside_formula() -> None:
    assert contains_center([0, 0, 100, 100], [40, 40, 60, 60]) is True
    assert contains_center([0, 0, 20, 20], [40, 40, 60, 60]) is False


def test_insertion_regions_rejects_missing_source_proof() -> None:
    corrections = {
        "records": [
            {
                "kind": "formula_insertion",
                "source_proofs": [{"region_id": "missing"}],
            }
        ]
    }
    report = {"alignment": {"pdf_source_math_regions": []}}

    with pytest.raises(
        ValueError, match="Missing insertion source regions in report: missing"
    ):
        insertion_regions(corrections, report)
