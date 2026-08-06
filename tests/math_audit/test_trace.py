from __future__ import annotations

import fitz

from pdf_math_audit.trace import _font_exclusion_regions


class FakePage:
    rect = fitz.Rect(0, 0, 100, 120)

    def __init__(self, rawdict: dict[str, object]) -> None:
        self.rawdict = rawdict

    def get_text(self, kind: str, *, sort: bool) -> dict[str, object]:
        assert kind == "rawdict"
        assert sort is False
        return self.rawdict


LIMITATIONS = [
    {
        "font_resource": "/F1@12",
        "code": "identity_cid_to_gid_required",
        "message": "CIDToGIDMap non supportée",
        "operation_indices": [7],
        "glyph_sequence_indices": [10, 11],
    }
]


def test_localise_une_police_exclue_a_la_ligne_rendue() -> None:
    page = FakePage(
        {
            "blocks": [
                {
                    "type": 0,
                    "lines": [
                        {
                            "bbox": [10, 20, 80, 30],
                            "spans": [{"font": "LimitedFont"}],
                        }
                    ],
                }
            ]
        }
    )

    assert _font_exclusion_regions(
        page,
        {"LimitedFont": {"/F1@12"}},
        LIMITATIONS,
    ) == [
        {
            "kind": "font",
            "scope": "line",
            "resources": ["/F1@12"],
            "trace_font": "LimitedFont",
            "bbox": [10, 20, 80, 30],
            "operation_index_ranges": [[7, 7]],
            "glyph_sequence_index_ranges": [[10, 11]],
            "reasons": [
                {
                    "font_resource": "/F1@12",
                    "code": "identity_cid_to_gid_required",
                    "message": "CIDToGIDMap non supportée",
                }
            ],
        }
    ]


def test_conserve_une_exclusion_page_entiere_si_la_police_est_introuvable() -> None:
    page = FakePage({"blocks": []})

    assert _font_exclusion_regions(
        page,
        {"LimitedFont": {"/F1@12"}},
        LIMITATIONS,
    ) == [
        {
            "kind": "font",
            "scope": "page",
            "resources": ["/F1@12"],
            "trace_font": "LimitedFont",
            "bbox": [0.0, 0.0, 100.0, 120.0],
            "operation_index_ranges": [[7, 7]],
            "glyph_sequence_index_ranges": [[10, 11]],
            "reasons": [
                {
                    "font_resource": "/F1@12",
                    "code": "identity_cid_to_gid_required",
                    "message": "CIDToGIDMap non supportée",
                }
            ],
        }
    ]


def test_nomme_une_police_sans_basefont_par_sa_ressource() -> None:
    page = FakePage({"blocks": []})
    limitation = {
        "font_resource": "/FType3",
        "code": "embedded_font_type_unsupported",
        "message": "Police Type3 non supportée",
    }

    regions = _font_exclusion_regions(page, {"": {"/FType3"}}, [limitation])

    assert regions[0]["scope"] == "page"
    assert regions[0]["trace_font"] == "/FType3"


def test_nomme_une_police_localisee_sans_nom_par_sa_ressource() -> None:
    page = FakePage(
        {
            "blocks": [
                {
                    "type": 0,
                    "lines": [
                        {"bbox": [10, 20, 80, 30], "spans": [{"font": ""}]}
                    ],
                }
            ]
        }
    )
    limitation = {
        "font_resource": "/FType3",
        "code": "embedded_font_type_unsupported",
        "message": "Police Type3 non supportée",
    }

    regions = _font_exclusion_regions(page, {"": {"/FType3"}}, [limitation])

    assert regions[0]["scope"] == "line"
    assert regions[0]["trace_font"] == "/FType3"
