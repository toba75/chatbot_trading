from pdf_math_audit.latex_locus import formula_locus
from pdf_math_audit.mathml_candidate import candidate_analysis


def test_relocalise_un_fragment_apres_un_operateur_latex() -> None:
    latex = r"a \ln f _ { X } - b \ln c"
    expected = r"f _ { X } - b"
    tokens, signature, reason = candidate_analysis(expected)
    assert reason is None
    start = latex.index("X")
    end = latex.index(r" \ln c")
    region = {
        "candidate_charspan": [start, end],
        "candidate_tokens": tokens,
        "candidate_relation_signature": signature,
        "source_canonical_tokens": tokens,
    }

    _start, _end, candidate = formula_locus(latex, region)

    assert candidate == expected


def test_conserve_un_wrapper_contradictoire_autour_du_locus() -> None:
    latex = r"\mathbb { E } [ \hat { \theta } ( S _ { X } ) ]"
    expected = r"\hat { \theta } ( S _ { X } )"
    tokens, signature, reason = candidate_analysis(expected)
    assert reason is None
    start = latex.index(r"\theta")
    end = latex.index(" ]")
    region = {
        "candidate_charspan": [start, end],
        "candidate_tokens": tokens,
        "candidate_relation_signature": signature,
        "source_canonical_tokens": list("θ(SX)"),
    }

    _start, _end, candidate = formula_locus(latex, region)

    assert candidate == expected
