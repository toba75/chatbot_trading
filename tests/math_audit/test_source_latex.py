from __future__ import annotations

import pytest

from pdf_math_audit.source_latex import proven_source_latex


@pytest.mark.parametrize(
    ("tokens", "signature"),
    [
        (
            list("{(xi,yi)}i=1N"),
            [
                "{", "(", "<bold>", "x", "</bold>", "<sub>", "i",
                "</sub>", ",", "y", "<sub>", "i", "</sub>", ")", "}",
                "<sub>", "i", "=", "1", "</sub>", "<sup>", "N", "</sup>",
            ],
        ),
        (
            list("12"),
            [
                "<fraction>", "<numerator>", "1", "</numerator>",
                "<denominator>", "2", "</denominator>", "</fraction>",
            ],
        ),
        (list("√x"), ["√", "<radicand>", "x", "</radicand>"]),
        (list("=def"), ["=", "<over>", "d", "e", "f", "</over>"]),
        (list("x∈A≥0"), list("x∈A≥0")),
    ],
)
def test_serialise_une_structure_source_et_reverifie_la_preuve(
    tokens: list[str], signature: list[str]
) -> None:
    latex, reason = proven_source_latex(
        {
            "source_canonical_tokens": tokens,
            "source_relation_signature": signature,
        }
    )

    assert reason is None
    assert latex


def test_refuse_un_symbole_source_sans_serialisation_connue() -> None:
    latex, reason = proven_source_latex(
        {
            "source_canonical_tokens": ["\uf8f0"],
            "source_relation_signature": ["\uf8f0"],
        }
    )

    assert latex is None
    assert reason == "source_symbol_unsupported"


def test_refuse_une_relation_source_mal_formee() -> None:
    latex, reason = proven_source_latex(
        {
            "source_canonical_tokens": ["x"],
            "source_relation_signature": ["x", "<sub>", "i"],
        }
    )

    assert latex is None
    assert reason == "source_relation_unbalanced"
