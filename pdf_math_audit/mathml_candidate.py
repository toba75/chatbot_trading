from __future__ import annotations

import unicodedata
from html import unescape

from latex2mathml import exceptions as latex_exceptions
from latex2mathml.converter import convert_to_element

from pdf_math_audit.math_unicode import is_mathematical_bold, normalize_bold_variants
from pdf_math_audit.relation_signature import normalize_relation_signature


_SEQUENCE_MATHML_TAGS = {
    "math",
    "mrow",
    "mi",
    "mo",
    "mn",
    "mspace",
    "mfrac",
    "mover",
    "msub",
    "msup",
    "msubsup",
    "msqrt",
    "mtext",
}
_TOKEN_EQUIVALENTS = str.maketrans({"-": "−", "*": "∗"})
_RELATION_ARITIES = {
    "mfrac": 2,
    "mover": 2,
    "msub": 2,
    "msup": 2,
    "msubsup": 3,
}


def _normalized_tokens(text: str) -> list[str]:
    normalized = normalize_bold_variants(unescape(text)).translate(_TOKEN_EQUIVALENTS)
    return [
        token
        for character in normalized
        for token in ("..." if character == "…" else character)
        if not token.isspace()
    ]


def _reason(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _relation_arity_reason(root: object) -> dict[str, str] | None:
    invalid = [
        element.tag
        for element in root.iter()
        if (
            element.tag in _RELATION_ARITIES
            and len(element) != _RELATION_ARITIES[element.tag]
        )
        or (element.tag == "msqrt" and len(element) == 0)
    ]
    return (
        _reason(
            "candidate_relation_invalid",
            f"Relations MathML incomplètes : {', '.join(sorted(set(invalid)))}",
        )
        if invalid
        else None
    )


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


def _candidate_root(
    candidate: str, candidate_format: str
) -> tuple[object | None, dict[str, str] | None]:
    if not candidate.strip():
        return None, None
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
    if arity_reason := _relation_arity_reason(root):
        return None, arity_reason
    return root, None


def _candidate_tokens(root: object) -> list[str]:
    def walk(element: object) -> list[str]:
        if element.tag in {"mi", "mo", "mn", "mtext"}:
            return _normalized_tokens(element.text or "")
        children = [token for child in element for token in walk(child)]
        return ["√", *children] if element.tag == "msqrt" else children

    return list(unicodedata.normalize("NFC", "".join(walk(root))))


def _candidate_signature(root: object) -> list[str]:
    def walk(element: object) -> list[str]:
        tag = element.tag
        children = list(element)
        if tag in {"mi", "mo", "mn", "mtext"}:
            source_text = unescape(element.text or "")
            tokens = _normalized_tokens(source_text)
            bold = "bold" in element.attrib.get("mathvariant", "") or any(
                is_mathematical_bold(token) for token in source_text
            )
            return ["<bold>", *tokens, "</bold>"] if bold else tokens
        if tag == "msub":
            return walk(children[0]) + ["<sub>"] + walk(children[1]) + ["</sub>"]
        if tag == "msup":
            return walk(children[0]) + ["<sup>"] + walk(children[1]) + ["</sup>"]
        if tag == "msubsup":
            return (
                walk(children[0])
                + ["<sub>"]
                + walk(children[1])
                + ["</sub>", "<sup>"]
                + walk(children[2])
                + ["</sup>"]
            )
        if tag == "mfrac":
            return [
                "<fraction>",
                "<numerator>",
                *walk(children[0]),
                "</numerator>",
                "<denominator>",
                *walk(children[1]),
                "</denominator>",
                "</fraction>",
            ]
        if tag == "mover":
            return walk(children[0]) + ["<over>"] + walk(children[1]) + ["</over>"]
        if tag == "msqrt":
            return [
                "√",
                "<radicand>",
                *[token for child in children for token in walk(child)],
                "</radicand>",
            ]
        return [token for child in children for token in walk(child)]

    return normalize_relation_signature(walk(root))


def candidate_analysis(
    candidate: str, candidate_format: str = "latex"
) -> tuple[list[str] | None, list[str] | None, dict[str, str] | None]:
    if not candidate.strip():
        return [], [], None
    root, reason = _candidate_root(candidate, candidate_format)
    if reason is not None or root is None:
        return None, None, reason

    tokens = _candidate_tokens(root)
    signature = _candidate_signature(root)
    if any("\\" in token for token in [*tokens, *signature]):
        return (
            None,
            None,
            _reason(
                "candidate_command_unsupported",
                "Le candidat contient une commande LaTeX non interprétée",
            ),
        )
    return tokens, signature, None


def candidate_tokens(
    candidate: str, candidate_format: str
) -> tuple[list[str] | None, dict[str, str] | None]:
    tokens, _signature, reason = candidate_analysis(candidate, candidate_format)
    return tokens, reason


def candidate_signature(
    candidate: str,
    candidate_format: str = "latex",
) -> tuple[list[str] | None, dict[str, str] | None]:
    _tokens, signature, reason = candidate_analysis(candidate, candidate_format)
    return signature, reason
