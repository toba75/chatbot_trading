from pdf_math_audit import mathml_candidate
from pdf_math_audit.mathml_candidate import (
    candidate_analysis,
    candidate_signature,
    candidate_tokens,
    publishable_mathml,
)


def test_analyse_les_jetons_et_la_structure_en_une_seule_conversion(
    monkeypatch,
) -> None:
    conversions = 0
    convert = mathml_candidate.convert_to_element

    def counted_convert(candidate: str):
        nonlocal conversions
        conversions += 1
        return convert(candidate)

    monkeypatch.setattr(mathml_candidate, "convert_to_element", counted_convert)

    tokens, signature, reason = candidate_analysis(r"x_i^2")

    assert reason is None
    assert tokens == list("xi2")
    assert signature == [
        "x",
        "<sub>",
        "i",
        "</sub>",
        "<sup>",
        "2",
        "</sup>",
    ]
    assert conversions == 1


def test_reconstruit_les_fragments_d_indices_docling_sur_une_base_unique() -> None:
    tokens, signature, reason = candidate_analysis(
        r"f$_{w}$$_{,}$$_{b}$ ( x )",
        "mixed_text",
    )

    assert reason is None
    assert tokens == list("fw,b(x)")
    assert signature == [
        "f",
        "<sub>",
        "w",
        ",",
        "b",
        "</sub>",
        "(",
        "x",
        ")",
    ]


def test_reconstruit_un_indice_docling_fragmente_en_plusieurs_groupes() -> None:
    tokens, signature, reason = candidate_analysis(
        r"x$_{n}$$_{-}$$_{1}$",
        "mixed_text",
    )

    assert reason is None
    assert tokens == list("xn−1")
    assert signature == ["x", "<sub>", "n", "−", "1", "</sub>"]


def test_preserve_un_pourcentage_dans_le_texte_mixte_docling() -> None:
    tokens, signature, reason = candidate_analysis("≤ 200%", "mixed_text")

    assert reason is None
    assert tokens == list("≤200%")
    assert signature == list("≤200%")


def test_ne_double_pas_un_pourcentage_deja_echappe() -> None:
    tokens, signature, reason = candidate_analysis(r"≤ 200\%", "mixed_text")

    assert reason is None
    assert tokens == list("≤200%")
    assert signature == list("≤200%")


def test_echappe_un_pourcentage_apres_un_antislash_lui_meme_echappe() -> None:
    tokens, signature, reason = candidate_analysis(r"A\\%B", "mixed_text")

    assert reason is None
    assert tokens == list("A%B")
    assert signature == list("A%B")


def test_refuse_un_fragment_mixed_text_aux_delimiteurs_dollar_incomplets() -> None:
    tokens, signature, reason = candidate_analysis(r"x$_{i}", "mixed_text")

    assert tokens is None
    assert signature is None
    assert reason == {
        "code": "candidate_mixed_text_invalid",
        "message": "Le candidat contient un fragment mathématique non refermé",
    }


def test_refuse_un_indice_docling_vide() -> None:
    tokens, signature, reason = candidate_analysis(r"x$_{i}$$_{}$", "mixed_text")

    assert tokens is None
    assert signature is None
    assert reason == {
        "code": "candidate_mixed_text_invalid",
        "message": "Le candidat contient un indice ou exposant vide",
    }


def test_normalise_dots_comme_les_trois_points_du_pdf() -> None:
    latex = r"w^{(1)}x^{(1)} + \dots + w^{(D)}x^{(D)}"

    tokens, token_reason = candidate_tokens(latex, "latex")
    signature, signature_reason = candidate_signature(latex)

    assert token_reason is None
    assert signature_reason is None
    assert tokens == list("w(1)x(1)+...+w(D)x(D)")
    assert signature == [
        "w",
        "<sup>",
        "(",
        "1",
        ")",
        "</sup>",
        "x",
        "<sup>",
        "(",
        "1",
        ")",
        "</sup>",
        "+",
        ".",
        ".",
        ".",
        "+",
        "w",
        "<sup>",
        "(",
        "D",
        ")",
        "</sup>",
        "x",
        "<sup>",
        "(",
        "D",
        ")",
        "</sup>",
    ]


def test_conserve_la_racine_et_les_bornes_d_une_somme() -> None:
    latex = r"\sqrt{\sum_{j=1}^{D}(w^{(j)})^2}"

    tokens, token_reason = candidate_tokens(latex, "latex")
    signature, signature_reason = candidate_signature(latex)

    assert token_reason is None
    assert signature_reason is None
    assert tokens == list("√∑j=1D(w(j))2")
    assert signature == [
        "√",
        "<radicand>",
        "∑",
        "<sub>",
        "j",
        "=",
        "1",
        "</sub>",
        "<sup>",
        "D",
        "</sup>",
        "(",
        "w",
        "<sup>",
        "(",
        "j",
        ")",
        "</sup>",
        ")",
        "<sup>",
        "2",
        "</sup>",
        "</radicand>",
    ]


def test_conserve_le_numerateur_et_le_denominateur_d_une_fraction() -> None:
    latex = r"\frac{2}{\|\mathbf{w}\|}"

    tokens, token_reason = candidate_tokens(latex, "latex")
    signature, signature_reason = candidate_signature(latex)

    assert token_reason is None
    assert signature_reason is None
    assert tokens == list("2‖w‖")
    assert signature == [
        "<fraction>",
        "<numerator>",
        "2",
        "</numerator>",
        "<denominator>",
        "‖",
        "<bold>",
        "w",
        "</bold>",
        "‖",
        "</denominator>",
        "</fraction>",
    ]


def test_conserve_une_annotation_placee_au_dessus_d_un_operateur() -> None:
    tokens, signature, reason = candidate_analysis(r"S\stackrel{\text{def}}{=}")

    assert reason is None
    assert tokens == list("S=def")
    assert signature == ["S", "=", "<over>", "d", "e", "f", "</over>"]


def test_refuse_une_fraction_incomplete_sans_interrompre_l_analyse() -> None:
    tokens, token_reason = candidate_tokens(r"\frac{2}", "latex")
    signature, signature_reason = candidate_signature(r"\frac{2}")

    assert tokens is None
    assert signature is None
    assert token_reason["code"] == "candidate_relation_invalid"
    assert signature_reason["code"] == "candidate_relation_invalid"


def test_refuse_un_fragment_inline_que_latex2mathml_ne_sait_pas_convertir() -> None:
    assert publishable_mathml("x_") is None
    assert publishable_mathml(r"\left( x") is None


def test_refuse_un_fragment_inline_ampute_par_un_commentaire_latex() -> None:
    assert publishable_mathml("100%") is None
    assert publishable_mathml(r"5\%") is not None


def test_refuse_le_balisage_qu_un_text_fait_traverser_le_serialiseur() -> None:
    assert publishable_mathml(r"\text{<script>alert(1)</script>}") is None
    assert publishable_mathml("a & b") is None


def test_publie_un_fragment_inline_prouve() -> None:
    mathml = publishable_mathml("x_i")

    assert mathml is not None
    assert "<msub>" in mathml
