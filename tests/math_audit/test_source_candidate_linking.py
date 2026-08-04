from __future__ import annotations

from docling_core.types.doc import DoclingDocument

from pdf_math_audit.source_candidate_linking import link_source_candidates


def _document(
    text: str,
    *,
    label: str = "text",
    page_size: tuple[int, int] = (100, 100),
    bbox: tuple[int, int, int, int] = (0, 0, 100, 20),
) -> DoclingDocument:
    item = {
        "self_ref": "#/texts/0",
        "parent": {"$ref": "#/body"},
        "label": label,
        "prov": [
            {
                "page_no": 1,
                "bbox": {
                    "l": bbox[0],
                    "t": bbox[1],
                    "r": bbox[2],
                    "b": bbox[3],
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
            "pages": {
                "1": {
                    "page_no": 1,
                    "size": {"width": page_size[0], "height": page_size[1]},
                }
            },
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


def _picture_document() -> DoclingDocument:
    return DoclingDocument.model_validate(
        {
            "name": "picture-candidate-linking-test",
            "pages": {
                "1": {
                    "page_no": 1,
                    "size": {"width": 100, "height": 100},
                }
            },
            "body": {
                "self_ref": "#/body",
                "children": [{"$ref": "#/pictures/0"}],
                "name": "_root_",
                "label": "unspecified",
                "content_layer": "body",
            },
            "pictures": [
                {
                    "self_ref": "#/pictures/0",
                    "parent": {"$ref": "#/body"},
                    "children": [],
                    "label": "picture",
                    "content_layer": "body",
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
                            "charspan": [0, 0],
                        }
                    ],
                    "captions": [],
                    "references": [],
                    "footnotes": [],
                    "annotations": [],
                }
            ],
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


SOURCE_PAGE_BOXES = {1: [0, 0, 100, 100]}


def test_lie_une_region_source_au_fragment_textuel_docling() -> None:
    source = "valuex=1."

    linked = link_source_candidates(
        _document("value x = 1."),
        [_region("x=1", source)],
        _glyphs(source),
        SOURCE_PAGE_BOXES,
    )

    assert linked[0]["candidate_text"] == "x = 1"
    assert linked[0]["candidate_format"] == "mixed_text"
    assert linked[0]["docling_ref"] == "#/texts/0"
    assert (
        linked[0]["candidate_alignment_method"]
        == "normalized_bbox_and_canonical_text_glyph_alignment"
    )


def test_conserve_les_marqueurs_inline_entourant_le_fragment() -> None:
    source = "valuexi."

    linked = link_source_candidates(
        _document("value x$_{i}$."),
        [_region("xi", source)],
        _glyphs(source),
        SOURCE_PAGE_BOXES,
    )

    assert linked[0]["candidate_text"] == "x$_{i}$"


def test_conserve_un_candidat_contradictoire_incomplet() -> None:
    source = "y=sign(wx−b)"
    candidate = r"y = \text {sign} ( w - b )"

    linked = link_source_candidates(
        _document(candidate, label="formula"),
        [_region(source, source)],
        _glyphs(source),
        SOURCE_PAGE_BOXES,
    )

    assert linked[0]["candidate_text"] == candidate
    assert linked[0]["candidate_format"] == "latex"


def test_retablit_les_accolades_ignorees_par_l_alignement_textuel() -> None:
    source = "classes{1,2,C}."

    linked = link_source_candidates(
        _document("classes { 1 , 2 , C }."),
        [_region("{1,2,C}", source)],
        _glyphs(source),
        SOURCE_PAGE_BOXES,
    )

    assert linked[0]["candidate_text"] == "{ 1 , 2 , C }"


def test_signale_explicitement_une_region_sans_element_docling() -> None:
    region = _region("x", "x")
    region["bbox"] = [120, 5, 124, 15]

    linked = link_source_candidates(
        _document("prose"), [region], _glyphs("x"), SOURCE_PAGE_BOXES
    )

    assert linked[0]["candidate_text"] == ""
    assert linked[0]["candidate_format"] is None
    assert linked[0]["candidate_link_status"] == "not_linked"
    assert (
        linked[0]["candidate_link_reason"]["code"]
        == "docling_text_container_missing"
    )


def test_signale_une_picture_sans_inventer_de_transcription_candidate() -> None:
    linked = link_source_candidates(
        _picture_document(),
        [_region("x", "x")],
        _glyphs("x"),
        SOURCE_PAGE_BOXES,
    )

    result = linked[0]
    assert result["docling_ref"] == "#/pictures/0"
    assert result["candidate_source_kind"] == "picture"
    assert result["candidate_text"] == ""
    assert result["candidate_link_status"] == "not_linked"
    assert (
        result["candidate_link_reason"]["code"]
        == "docling_picture_candidate_missing"
    )


def test_normalise_les_coordonnees_docling_vers_la_page_pdf_source() -> None:
    source = "valuex=1."
    region = _region("x=1", source)
    region["bbox"] = [20, 45, 32, 55]
    glyphs = _glyphs(source)
    for glyph in glyphs:
        glyph["bbox"] = [glyph["bbox"][0], 45, glyph["bbox"][2], 55]

    linked = link_source_candidates(
        _document("value x = 1.", page_size=(200, 200), bbox=(0, 80, 200, 120)),
        [region],
        glyphs,
        SOURCE_PAGE_BOXES,
    )

    assert linked[0]["docling_ref"] == "#/texts/0"
    assert linked[0]["candidate_text"] == "x = 1"
    assert (
        linked[0]["candidate_alignment_method"]
        == "normalized_bbox_and_canonical_text_glyph_alignment"
    )


def test_retablit_l_accolade_ouvrante_d_une_formule_plus_large() -> None:
    source = "value{xi}Ni=1."
    candidate = "value { x$_{i}$ } N i = $_{1}$."

    linked = link_source_candidates(
        _document(candidate),
        [_region("{xi}Ni=1", source)],
        _glyphs(source),
        SOURCE_PAGE_BOXES,
    )

    assert linked[0]["candidate_text"] == "{ x$_{i}$ } N i = $_{1}$"


def test_refuse_une_correspondance_partielle_avec_un_caractere_de_prose() -> None:
    source = "y=x+z"

    linked = link_source_candidates(
        _document("prose x prose"),
        [_region(source, source)],
        _glyphs(source),
        SOURCE_PAGE_BOXES,
    )

    assert linked[0]["candidate_link_status"] == "not_linked"
    assert linked[0]["candidate_text"] == ""
    assert (
        linked[0]["candidate_link_reason"]["code"]
        == "docling_text_alignment_incomplete"
    )


def test_aligne_les_commandes_latex_sur_leurs_symboles_pdf() -> None:
    source = "θ=√x"
    candidate = r"\theta = \sqrt{x}"

    linked = link_source_candidates(
        _document(candidate, label="formula"),
        [_region(source, source)],
        _glyphs(source),
        SOURCE_PAGE_BOXES,
    )

    result = linked[0]
    assert result["candidate_text"] == candidate
    assert result["candidate_format"] == "latex"
    assert result["candidate_link_status"] == "linked"


def test_aligne_l_apostrophe_docling_sur_le_prime_mathematique() -> None:
    source = "S\u2032"
    linked = link_source_candidates(
        _document("S'"),
        [_region(source, source)],
        _glyphs(source),
        SOURCE_PAGE_BOXES,
    )

    assert linked[0]["candidate_text"] == "S'"
    assert linked[0]["candidate_link_status"] == "linked"


def test_delimite_un_fragment_mixte_par_ses_ancres_malgre_une_substitution() -> None:
    source = "A={a1,a2}"
    candidate = "A = { a1 ; a2 }"

    linked = link_source_candidates(
        _document(candidate),
        [_region(source, source)],
        _glyphs(source),
        SOURCE_PAGE_BOXES,
    )

    assert linked[0]["candidate_text"] == candidate
    assert linked[0]["candidate_link_status"] == "linked"
    assert linked[0]["candidate_alignment_method"] == (
        "canonical_boundary_anchored_text_glyph_alignment"
    )


def test_refuse_deux_ancres_trop_faibles_dans_un_texte_repetitif() -> None:
    source = "A+B+A"

    linked = link_source_candidates(
        _document("A prose A formula A"),
        [_region(source, source)],
        _glyphs(source),
        SOURCE_PAGE_BOXES,
    )

    assert linked[0]["candidate_link_status"] == "not_linked"
    assert linked[0]["candidate_text"] == ""


def test_conserve_la_macro_structurelle_autour_du_glyphe_aligne() -> None:
    candidate = r"\mathbf{x}"

    linked = link_source_candidates(
        _document(candidate, label="formula"),
        [_region("x", "x")],
        _glyphs("x"),
        SOURCE_PAGE_BOXES,
    )

    assert linked[0]["candidate_text"] == candidate
    assert linked[0]["candidate_charspan"] == [0, len(candidate)]
