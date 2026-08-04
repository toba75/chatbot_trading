from pathlib import Path

from docling_core.types.doc import DoclingDocument

from pdf_math_audit.alignment import DoclingAlignment
from pdf_math_audit.analyzer import analyze_pdf
from pdf_math_audit.docling_regions import extract_regions


REFERENCE_PDF = (
    Path(__file__).parents[2]
    / "experiments"
    / "math_pipeline_comparison"
    / "source-pages-7-10.pdf"
)
REFERENCE_DOCUMENT = (
    Path(__file__).parents[2]
    / "experiments"
    / "math_pipeline_comparison"
    / "docling-subset-document.json"
)


def _document(*texts: dict[str, object]) -> DoclingDocument:
    children = [{"$ref": text["self_ref"]} for text in texts]
    return DoclingDocument.model_validate(
        {
            "name": "alignment-test",
            "pages": {"1": {"page_no": 1, "size": {"width": 100, "height": 100}}},
            "body": {
                "self_ref": "#/body",
                "children": children,
                "name": "_root_",
                "label": "unspecified",
                "content_layer": "body",
            },
            "texts": list(texts),
        }
    )


def _text(
    index: int,
    text: str,
    bbox: tuple[float, float, float, float],
    *,
    label: str = "formula",
    origin: str = "TOPLEFT",
) -> dict[str, object]:
    left, top, right, bottom = bbox
    return {
        "self_ref": f"#/texts/{index}",
        "parent": {"$ref": "#/body"},
        "label": label,
        "prov": [
            {
                "page_no": 1,
                "bbox": {
                    "l": left,
                    "t": top,
                    "r": right,
                    "b": bottom,
                    "coord_origin": origin,
                },
                "charspan": [0, len(text)],
            }
        ],
        "orig": text,
        "text": text,
    }


def _glyph(index: int, value: str, bbox: list[float]) -> dict[str, object]:
    return {
        "sequence_index": index,
        "source_unicode": value,
        "source_unicode_method": "agl",
        "agl_unicode": value,
        "glyph_name": "equal" if value == "=" else "x",
        "font_resource": "/F1",
        "code": ord(value),
        "code_hex": f"{ord(value):02X}",
        "cff_gid": index + 1,
        "to_unicode": value,
        "rendered": {
            "font": "Regular",
            "bbox": bbox,
            "gid": index + 1,
            "unicode_text": value,
            "origin": [bbox[0], 10.0],
            "size": 10.0,
        },
        "rawdict": {
            "block": 0,
            "line": 0,
            "span": 0,
            "char": index,
            "line_bbox": [0, 0, 100, 20],
        },
    }


def _pdf_report(width: float = 100, height: float = 100) -> dict[str, object]:
    return {
        "pages": [
            {
                "page": 1,
                "status": "traced",
                "box": [0.0, 0.0, width, height],
                "fonts": {},
            }
        ]
    }


def test_aligne_les_formules_et_evalue_les_regions_source_reelles() -> None:
    document = DoclingDocument.model_validate_json(
        REFERENCE_DOCUMENT.read_text(encoding="utf-8")
    )
    alignment = DoclingAlignment(document)
    progress = []
    report = analyze_pdf(REFERENCE_PDF, on_evidence=alignment.observe_glyph)

    result = alignment.finalize(report, on_progress=progress.append)

    formulas = [region for region in result["regions"] if region["kind"] == "formula"]
    inline = [region for region in result["regions"] if region["kind"] == "inline_math"]
    assert [region["status"] for region in formulas] == ["traced"] * 3
    assert [region["glyph_count"] for region in formulas] == [7, 13, 17]
    assert [region["source_glyph_text"] for region in formulas] == [
        "wx−b=0,",
        "y=sign(wx−b),",
        "f(x)=sign(w∗x−b∗)",
    ]
    assert len(inline) == 23
    assert {region["status"] for region in inline} == {"traced"}
    assert all(region["bbox"] is not None for region in inline)
    assert all(not region["reasons"] for region in inline)
    assert inline[0]["candidate_text"] == "$^{1}$"
    assert inline[0]["charspan"] == [23, 29]
    assert inline[0]["source_glyph_text"] == "g1"
    assert inline[0]["localization_method"] == (
        "unique_text_context_with_preceding_script_anchor"
    )
    source_regions = result["pdf_source_math_regions"]
    assert {region["candidate_link_status"] for region in source_regions} == {
        "linked"
    }
    semantic_statuses = [region["semantic_status"] for region in source_regions]
    assert semantic_statuses == ["established"] * 53
    assert {region["verdict"] for region in source_regions} <= {
        "conformant_within_scope",
        "contradicted",
        "non_verifiable",
    }
    assert all(region["verdict"] != "non_verifiable" for region in source_regions)
    assert result["coverage"] == {
        "regions_total": 26,
        "formula_regions": 3,
        "inline_math_regions": 23,
        "regions_traced": 26,
        "regions_ambiguous": 0,
        "regions_unsupported": 0,
        "regions_not_traced": 0,
        "glyphs_assigned": 86,
        "glyphs_observed": 4088,
        "glyphs_unassigned": 4002,
        "glyphs_with_multiple_regions": 0,
        "boundary_glyphs": 0,
        "pdf_math_indicators_unassigned": len(result["pdf_math_indicators_unassigned"]),
        "pdf_math_indicator_regions": len(result["pdf_math_indicator_regions"]),
        "pdf_source_math_regions": 53,
        "pdf_source_math_regions_without_docling_overlap": 34,
    }
    assert result["pdf_math_indicators_unassigned"]
    assert {
        region["localization_method"]
        for region in result["pdf_source_math_regions"]
    } == {
        "pdf_source_typography"
    }
    assert "recall" not in result
    assert progress[0] == {
        "type": "progress",
        "phase": "docling_alignment",
        "completed_units": 0,
        "total_units": 26,
    }
    alignment_events = [
        event for event in progress if event["phase"] == "docling_alignment"
    ]
    assert alignment_events[-1]["completed_units"] == 26
    assert [event["phase"] for event in progress].count("candidate_evaluation") == 54


def test_signale_une_association_multiple_et_une_region_tronquee() -> None:
    document = _document(
        _text(0, "a", (10, 10, 30, 30)),
        _text(1, "b", (20, 10, 40, 30)),
        _text(2, "c", (50, 10, 60, 20)),
    )
    alignment = DoclingAlignment(document)
    alignment.observe_glyph(1, _glyph(1, "x", [22, 15, 24, 20]))
    alignment.observe_glyph(1, _glyph(2, "x", [59, 15, 63, 18]))

    result = alignment.finalize(_pdf_report())

    assert [region["status"] for region in result["regions"]] == [
        "ambiguous",
        "ambiguous",
        "ambiguous",
    ]
    assert result["regions"][0]["reasons"][0]["code"] == (
        "glyph_assigned_to_multiple_regions"
    )
    assert result["regions"][2]["reasons"][0]["code"] == ("boundary_glyph_intersection")


def test_refuse_un_glyphe_dont_la_boite_est_majoritairement_hors_region() -> None:
    alignment = DoclingAlignment(_document(_text(0, "x", (10, 10, 30, 30))))
    alignment.observe_glyph(1, _glyph(1, "x", [0, 0, 40, 40]))

    result = alignment.finalize(_pdf_report())

    assert result["regions"][0]["status"] == "ambiguous"
    assert result["regions"][0]["reasons"][0]["code"] == ("boundary_glyph_intersection")
    assert result["regions"][0]["glyph_sequence_indices"] == []
    assert result["regions"][0]["boundary_glyph_sequence_indices"] == [1]


def test_normalise_bottomleft_et_refuse_une_geometrie_de_page_differente() -> None:
    document = _document(_text(0, "x", (10, 90, 30, 70), origin="BOTTOMLEFT"))
    alignment = DoclingAlignment(document)
    alignment.observe_glyph(1, _glyph(1, "x", [15, 15, 20, 20]))

    aligned = alignment.finalize(_pdf_report())
    mismatched = alignment.finalize(_pdf_report(width=200))

    assert aligned["regions"][0]["status"] == "traced"
    assert aligned["regions"][0]["bbox"] == [10.0, 10.0, 30.0, 30.0]
    assert mismatched["regions"][0]["status"] == "ambiguous"
    assert mismatched["regions"][0]["reasons"][0]["code"] == ("page_geometry_mismatch")


def test_preserve_le_statut_structurel_d_une_page_non_supportee() -> None:
    alignment = DoclingAlignment(_document(_text(0, "x", (10, 10, 30, 30))))
    report = _pdf_report()
    report["pages"][0]["status"] = "unsupported"
    report["pages"][0]["reasons"] = [
        {"code": "font_unsupported", "message": "Police non prise en charge"}
    ]

    result = alignment.finalize(report)

    assert result["regions"][0]["status"] == "unsupported"
    assert result["regions"][0]["reasons"] == report["pages"][0]["reasons"]
    assert result["coverage"]["regions_unsupported"] == 1


def test_refuse_seulement_la_region_docling_dans_une_zone_opaque() -> None:
    alignment = DoclingAlignment(
        _document(
            _text(0, "x", (10, 10, 20, 20)),
            _text(1, "y", (40, 40, 50, 50)),
        )
    )
    alignment.observe_glyph(1, _glyph(1, "x", [12, 12, 18, 18]))
    alignment.observe_glyph(1, _glyph(2, "y", [42, 42, 48, 48]))
    report = _pdf_report()
    report["pages"][0].update(
        {
            "status": "traced_with_exclusions",
            "opaque_regions": [
                {
                    "kind": "form_xobject",
                    "resource": "/X1",
                    "bbox": [5, 5, 25, 25],
                    "text_traced": True,
                }
            ],
        }
    )

    result = alignment.finalize(report)

    assert result["regions"][0]["status"] == "not_traced"
    assert result["regions"][0]["reasons"][0]["code"] == (
        "pdf_opaque_region_intersection"
    )
    assert result["regions"][0]["trace_exclusions"] == report["pages"][0][
        "opaque_regions"
    ]
    assert result["regions"][1]["status"] == "traced"
    assert result["regions"][1]["trace_exclusions"] == []


def test_publie_les_math_inline_et_les_indices_pdf_non_attribues() -> None:
    document = _document(_text(0, "Avant $x_i$ après", (10, 10, 90, 30), label="text"))
    alignment = DoclingAlignment(document)
    alignment.observe_glyph(1, _glyph(1, "=", [40, 40, 45, 45]))

    result = alignment.finalize(_pdf_report())

    expected_structure = {
        "region_id": "#/texts/0:inline:0",
        "kind": "inline_math",
        "docling_ref": "#/texts/0",
        "provenance_index": 0,
        "page": 1,
        "bbox": None,
        "bbox_coord_origin": None,
        "container_bbox": [10.0, 10.0, 90.0, 30.0],
        "charspan": [6, 11],
        "candidate_text": "$x_i$",
        "status": "not_traced",
        "glyph_count": 0,
        "glyph_sequence_indices": [],
        "source_glyph_text": "",
        "boundary_glyph_sequence_indices": [],
        "multiple_region_glyph_sequence_indices": [],
    }
    assert {
        key: result["regions"][0][key] for key in expected_structure
    } == expected_structure
    assert result["regions"][0]["reasons"] == [
        {
            "code": "inline_math_source_alignment_ambiguous",
            "message": "Le fragment inline n’a pas d’alignement textuel source univoque",
        }
    ]
    assert result["pdf_math_indicators_unassigned"] == [
        {
            "page": 1,
            "sequence_index": 1,
            "glyph_name": "equal",
            "unicode": "=",
            "bbox": [40, 40, 45, 45],
            "indicator": "unicode_math_symbol",
        }
    ]
    assert result["pdf_math_indicator_regions"] == [
        {
            "page": 1,
            "bbox": [0, 0, 100, 20],
            "bbox_coord_origin": "TOPLEFT",
            "method": "unassigned_unicode_math_symbol_in_pdf_line",
            "glyph_sequence_indices": [1],
            "source_glyph_text": "=",
            "indicator_glyph_sequence_indices": [1],
        }
    ]


def test_localise_un_indice_inline_par_le_texte_source_univoque() -> None:
    document = _document(
        _text(0, "Avant x$_{i}$ après", (10, 10, 90, 30), label="text")
    )
    alignment = DoclingAlignment(document)
    alignment.observe_glyph(1, _glyph(1, "x", [40, 10, 45, 20]))
    alignment.observe_glyph(1, _glyph(2, "i", [46, 13, 50, 20]))

    result = alignment.finalize(_pdf_report())

    inline = result["regions"][0]
    assert inline["status"] == "traced"
    assert inline["bbox"] == [40, 10, 50, 20]
    assert inline["glyph_sequence_indices"] == [1, 2]
    assert inline["source_glyph_text"] == "xi"
    assert inline["charspan"] == [7, 13]
    assert inline["candidate_text"] == "$_{i}$"
    assert inline["localization_method"] == (
        "unique_text_context_with_preceding_script_anchor"
    )
    assert inline["reasons"] == []
    assert alignment.finalize(_pdf_report()) == result


def test_refuse_de_choisir_entre_deux_fragments_inline_identiques() -> None:
    document = _document(_text(0, "x$_{i}$", (10, 10, 90, 30), label="text"))
    alignment = DoclingAlignment(document)
    for index, value in enumerate("xixi", start=1):
        left = 10 + index * 5
        alignment.observe_glyph(1, _glyph(index, value, [left, 10, left + 4, 20]))

    result = alignment.finalize(_pdf_report())

    inline = result["regions"][0]
    assert inline["status"] == "not_traced"
    assert inline["bbox"] is None
    assert inline["reasons"][0]["code"] == (
        "inline_math_source_alignment_ambiguous"
    )


def test_un_fragment_inline_sans_caractere_alignable_reste_local() -> None:
    document = _document(
        _text(0, "p 1 $_{-$_{p}$}$", (10, 10, 90, 30), label="text"),
        _text(1, "x$_{i}$", (10, 40, 90, 60), label="text"),
    )
    alignment = DoclingAlignment(document)
    alignment.observe_glyph(1, _glyph(1, "x", [20, 40, 25, 50]))
    alignment.observe_glyph(1, _glyph(2, "i", [26, 43, 30, 50]))
    progress = []

    result = alignment.finalize(_pdf_report(), on_progress=progress.append)

    fragment = result["regions"][1]
    assert fragment["region_id"] == "#/texts/0:inline:1"
    assert fragment["candidate_text"] == "$}$"
    assert fragment["charspan"] == [13, 16]
    assert fragment["page"] == 1
    assert fragment["container_bbox"] == [10.0, 10.0, 90.0, 30.0]
    assert fragment["status"] == "not_traced"
    assert fragment["reasons"] == [
        {
            "code": "inline_math_no_alignable_character",
            "message": "Le fragment inline ne contient aucun caractère alignable",
        }
    ]
    assert result["regions"][2]["candidate_text"] == "$_{i}$"
    assert result["regions"][2]["status"] == "traced"
    alignment_progress = [
        event for event in progress if event["phase"] == "docling_alignment"
    ]
    assert alignment_progress[-1] == {
        "type": "progress",
        "phase": "docling_alignment",
        "completed_units": 3,
        "total_units": 3,
    }


def test_ne_compte_pas_un_glyphe_multi_associe_comme_non_attribue() -> None:
    document = _document(
        _text(0, "a", (10, 10, 30, 30)),
        _text(1, "b", (20, 10, 40, 30)),
    )
    alignment = DoclingAlignment(document)
    alignment.observe_glyph(1, _glyph(1, "=", [22, 15, 24, 20]))

    result = alignment.finalize(_pdf_report())

    assert result["coverage"]["glyphs_with_multiple_regions"] == 1
    assert result["coverage"]["glyphs_unassigned"] == 0
    assert result["coverage"]["pdf_math_indicators_unassigned"] == 0


def test_decoupe_le_texte_d_une_formule_selon_chaque_provenance() -> None:
    item = _text(0, "ab", (10, 10, 20, 20))
    item["prov"] = [
        {
            "page_no": 1,
            "bbox": {
                "l": 10,
                "t": 10,
                "r": 15,
                "b": 20,
                "coord_origin": "TOPLEFT",
            },
            "charspan": [0, 1],
        },
        {
            "page_no": 1,
            "bbox": {
                "l": 15,
                "t": 10,
                "r": 20,
                "b": 20,
                "coord_origin": "TOPLEFT",
            },
            "charspan": [1, 2],
        },
    ]

    regions = extract_regions(_document(item))

    assert [region.candidate_text for region in regions] == ["a", "b"]


def test_signale_les_doubles_dollars_sans_perdre_leur_contenu() -> None:
    document = _document(
        _text(0, "Avant $$x_i$$ après", (10, 10, 90, 30), label="text")
    )

    regions = extract_regions(document)

    assert len(regions) == 1
    assert regions[0].candidate_text == "$$x_i$$"
    assert regions[0].charspan == (6, 13)
    assert regions[0].reason["code"] == "inline_math_delimiter_unsupported"


def test_conserve_le_contenu_apres_un_delimiteur_non_apparie() -> None:
    document = _document(_text(0, "Avant $x_i", (10, 10, 90, 30), label="text"))

    regions = extract_regions(document)

    assert len(regions) == 1
    assert regions[0].candidate_text == "$x_i"
    assert regions[0].reason["code"] == "inline_math_delimiter_unpaired"
