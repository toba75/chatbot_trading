from pdf_math_audit import mathml_candidate
from pdf_math_audit.mathml_candidate import (
    candidate_analysis,
    candidate_signature,
    candidate_tokens,
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
