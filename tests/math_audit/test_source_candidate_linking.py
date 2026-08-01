from __future__ import annotations

from docling_core.types.doc import DoclingDocument

from pdf_math_audit.source_candidate_linking import link_source_candidates


def _document(text: str, *, label: str = "text") -> DoclingDocument:
    item = {
        "self_ref": "#/texts/0",
        "parent": {"$ref": "#/body"},
        "label": label,
        "prov": [
            {
                "page_no": 1,
                "bbox": {
                    "l": 0,
                    "t": 0,
                    "r": 100,
                    "b": 20,
                    "coord_origin": "TOPLEFT",
                },
                "charspan": [0, len(text)],
            }
        ],
        "orig": text,
        "text": text,
    }
    return DoclingDocument.model_validate(
        {
            "name": "candidate-linking-test",
            "pages": {"1": {"page_no": 1, "size": {"width": 100, "height": 100}}},
            "body": {
                "self_ref": "#/body",
                "children": [{"$ref": "#/texts/0"}],
                "name": "_root_",
                "label": "unspecified",
                "content_layer": "body",
            },
            "texts": [item],
        }
    )


def _glyphs(text: str) -> list[dict[str, object]]:
    return [
        {
            "page": 1,
            "sequence_index": index,
            "unicode": character,
            "bbox": [index * 4, 5, index * 4 + 4, 15],
        }
        for index, character in enumerate(text)
    ]


def _region(source: str, full_source: str) -> dict[str, object]:
    start = full_source.index(source)
    indices = list(range(start, start + len(source)))
    return {
        "region_id": "pdf-source:1:test",
        "page": 1,
        "bbox": [start * 4, 5, (start + len(source)) * 4, 15],
        "glyph_sequence_indices": indices,
        "source_glyph_text": source,
        "status": "traced",
    }


def test_lie_une_region_source_au_fragment_textuel_docling() -> None:
    source = "valuex=1."

    linked = link_source_candidates(
        _document("value x = 1."), [_region("x=1", source)], _glyphs(source)
    )

    assert linked[0]["candidate_text"] == "x = 1"
    assert linked[0]["candidate_format"] == "mixed_text"
    assert linked[0]["docling_ref"] == "#/texts/0"
    assert linked[0]["candidate_alignment_method"] == "global_text_glyph_alignment"


def test_conserve_les_marqueurs_inline_entourant_le_fragment() -> None:
    source = "valuexi."

    linked = link_source_candidates(
        _document("value x$_{i}$."), [_region("xi", source)], _glyphs(source)
    )

    assert linked[0]["candidate_text"] == "x$_{i}$"


def test_conserve_un_candidat_contradictoire_incomplet() -> None:
    source = "y=sign(wx−b)"
    candidate = r"y = \text {sign} ( w - b )"

    linked = link_source_candidates(
        _document(candidate, label="formula"),
        [_region(source, source)],
        _glyphs(source),
    )

    assert linked[0]["candidate_text"] == candidate
    assert linked[0]["candidate_format"] == "latex"


def test_retablit_les_accolades_ignorees_par_l_alignement_textuel() -> None:
    source = "classes{1,2,C}."

    linked = link_source_candidates(
        _document("classes { 1 , 2 , C }."),
        [_region("{1,2,C}", source)],
        _glyphs(source),
    )

    assert linked[0]["candidate_text"] == "{ 1 , 2 , C }"


def test_signale_explicitement_une_region_sans_element_docling() -> None:
    region = _region("x", "x")
    region["bbox"] = [120, 5, 124, 15]

    linked = link_source_candidates(_document("prose"), [region], _glyphs("x"))

    assert linked[0]["candidate_text"] == ""
    assert linked[0]["candidate_format"] is None
    assert linked[0]["candidate_link_status"] == "not_linked"
    assert linked[0]["candidate_link_reason"]["code"] == "docling_container_missing"
