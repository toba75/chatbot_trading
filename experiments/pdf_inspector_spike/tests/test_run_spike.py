import gzip
import hashlib
import json
from dataclasses import dataclass

import pytest

from run_spike import extract_region_texts, expand, item_bbox, load_json, normalized, overlaps, region_index, sha256, summarize


@dataclass
class Item:
    x: float = 10
    y: float = 20
    width: float = 30
    height: float = 5


def test_region_index_finds_nested_regions() -> None:
    region = {"region_id": "r1", "bbox": [1, 2, 3, 4]}
    assert region_index({"pages": [{"regions": [region]}]}) == {"r1": region}


def test_compressed_inputs_keep_the_original_content_identity(tmp_path) -> None:
    content = json.dumps({"qualification": 51}).encode()
    path = tmp_path / "input.json.gz"
    path.write_bytes(gzip.compress(content, mtime=0))

    assert load_json(path) == {"qualification": 51}
    assert sha256(path) == hashlib.sha256(content).hexdigest()


def test_region_index_rejects_conflicting_duplicates() -> None:
    with pytest.raises(ValueError, match="Région dupliquée"):
        region_index([
            {"region_id": "r1", "bbox": [1, 2, 3, 4]},
            {"region_id": "r1", "bbox": [4, 3, 2, 1]},
        ])


def test_pdf_bottom_left_coordinates_are_converted_to_top_left() -> None:
    item = Item()
    assert item_bbox(item, 100) == [10, 75, 40, 80]
    assert overlaps([10, 75, 40, 80], [39, 79, 41, 81])
    assert not overlaps([10, 75, 40, 80], [40, 80, 41, 81])


def test_expand_clips_to_page_box() -> None:
    assert expand([5, 6, 20, 30], 10, [0, 0, 100, 100]) == [0, 0, 30, 40]


def test_normalized_only_removes_spacing_and_normalizes_unicode() -> None:
    assert normalized(" x\n² ") == "x²"
    assert normalized("e\u0301") == "é"


def test_summary_exposes_silent_replacement_character() -> None:
    record = {
        "kind": "formula_insertion",
        "exact_region": {"text": "�wx", "needs_ocr": False},
        "contains_source_glyph_text": True,
        "position_overlaps": [{"text": "wx"}],
        "position_neighborhoods": [{"text": "line"}, {"text": "wx"}],
    }
    summary = summarize([record])
    assert summary["replacement_character_but_needs_ocr_false"] == 1
    assert summary["position_overlap"] == 1
    assert summary["no_position_overlap"] == 0
    assert summary["no_position_neighborhood"] == 0


def test_region_responses_are_matched_by_page_not_return_order(monkeypatch) -> None:
    @dataclass
    class Region:
        text: str
        needs_ocr: bool = False

    @dataclass
    class Page:
        page: int
        regions: list[Region]

    monkeypatch.setattr(
        "run_spike.pdf_inspector.extract_text_in_regions",
        lambda *_: [Page(1, [Region("page 2")]), Page(0, [Region("page 1")])],
    )
    targets = [
        {"target_id": "p1", "page": 1, "bbox": [0, 0, 1, 1]},
        {"target_id": "p2", "page": 2, "bbox": [0, 0, 1, 1]},
    ]

    assert extract_region_texts("source.pdf", targets, "bbox") == {
        "p1": {"text": "page 1", "needs_ocr": False},
        "p2": {"text": "page 2", "needs_ocr": False},
    }
