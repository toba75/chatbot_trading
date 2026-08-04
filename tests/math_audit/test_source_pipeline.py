from docling_core.types.doc import DoclingDocument

from pdf_math_audit import source_pipeline


def test_interdit_la_correction_d_une_region_issue_d_une_page_partielle(
    monkeypatch,
) -> None:
    regions = [{"page": 1, "status": "traced", "glyph_sequence_indices": [1]}]
    monkeypatch.setattr(
        source_pipeline,
        "source_math_regions",
        lambda glyphs, fonts, rules: regions,
    )
    monkeypatch.setattr(
        source_pipeline,
        "link_source_candidates",
        lambda document, candidates, glyphs, boxes: candidates,
    )
    monkeypatch.setattr(
        source_pipeline,
        "evaluate_regions",
        lambda candidates, glyphs, on_progress: (candidates, {}),
    )
    report = {
        "pages": [
            {
                "page": 1,
                "status": "partially_traced",
                "fonts": {},
                "box": [0, 0, 10, 10],
                "horizontal_rules": [],
            }
        ]
    }

    evaluated, _metrics = source_pipeline.evaluate_source_regions(
        DoclingDocument(name="test"), [], report, set(), None
    )

    assert evaluated[0]["status"] == "not_traced"
    assert evaluated[0]["trace_limitation"] == "pdf_page_partially_traced"


def test_refuse_seulement_la_region_qui_intersecte_une_zone_opaque(
    monkeypatch,
) -> None:
    regions = [
        {
            "page": 1,
            "bbox": [10, 10, 20, 20],
            "status": "traced",
            "glyph_sequence_indices": [1],
        },
        {
            "page": 1,
            "bbox": [40, 40, 50, 50],
            "status": "traced",
            "glyph_sequence_indices": [2],
        },
    ]
    monkeypatch.setattr(
        source_pipeline,
        "source_math_regions",
        lambda glyphs, fonts, rules: regions,
    )
    monkeypatch.setattr(
        source_pipeline,
        "link_source_candidates",
        lambda document, candidates, glyphs, boxes: candidates,
    )
    monkeypatch.setattr(
        source_pipeline,
        "evaluate_regions",
        lambda candidates, glyphs, on_progress: (candidates, {}),
    )
    exclusion = {
        "kind": "form_xobject",
        "resource": "/X1",
        "bbox": [5, 5, 25, 25],
        "text_traced": True,
    }
    report = {
        "pages": [
            {
                "page": 1,
                "status": "traced_with_exclusions",
                "fonts": {},
                "box": [0, 0, 100, 100],
                "horizontal_rules": [],
                "opaque_regions": [exclusion],
            }
        ]
    }

    evaluated, _metrics = source_pipeline.evaluate_source_regions(
        DoclingDocument(name="test"), [], report, set(), None
    )

    assert evaluated[0]["status"] == "not_traced"
    assert evaluated[0]["trace_limitation"] == "pdf_opaque_region_intersection"
    assert evaluated[0]["trace_exclusions"] == [exclusion]
    assert evaluated[1]["status"] == "traced"
    assert "trace_limitation" not in evaluated[1]
