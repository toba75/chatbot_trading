from __future__ import annotations

import unicodedata
from html import unescape

from latex2mathml import exceptions as latex_exceptions
from latex2mathml.converter import convert_to_element


_SEQUENCE_MATHML_TAGS = {
    "math",
    "mrow",
    "mi",
    "mo",
    "mn",
    "mspace",
    "msub",
    "msup",
    "msubsup",
    "mtext",
}
_TOKEN_EQUIVALENTS = str.maketrans({"-": "−", "*": "∗"})


def _reason(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _mixed_text_latex(candidate: str) -> str:
    converted = []
    in_math = False
    for character in candidate:
        if character == "$":
            in_math = not in_math
        elif not in_math and character in "{}_":
            converted.append("\\" + character)
        else:
            converted.append(character)
    return "".join(converted)


def candidate_tokens(
    candidate: str, candidate_format: str
) -> tuple[list[str] | None, dict[str, str] | None]:
    if not candidate.strip():
        return [], None
    if candidate_format == "mixed_text":
        candidate = _mixed_text_latex(candidate)
    elif candidate_format != "latex":
        raise ValueError(f"Format candidat inconnu : {candidate_format}")
    try:
        root = convert_to_element(candidate)
    except Exception as error:
        if error.__class__.__module__ != latex_exceptions.__name__:
            raise
        return None, _reason(
            "candidate_latex_invalid",
            "Le candidat n’est pas un fragment LaTeX analysable",
        )

    unsupported = sorted(
        {element.tag for element in root.iter()} - _SEQUENCE_MATHML_TAGS
    )
    if unsupported:
        return None, _reason(
            "candidate_relation_unsupported",
            f"Relations MathML non prises en charge : {', '.join(unsupported)}",
        )

    tokens = []
    for element in root.iter():
        if element.tag in {"mi", "mo", "mn", "mtext"} and element.text:
            normalized = unicodedata.normalize(
                "NFC", unescape(element.text)
            ).translate(_TOKEN_EQUIVALENTS)
            tokens.extend(
                character for character in normalized if not character.isspace()
            )
    if any("\\" in token for token in tokens):
        return None, _reason(
            "candidate_command_unsupported",
            "Le candidat contient une commande LaTeX non interprétée",
        )
    return tokens, None
