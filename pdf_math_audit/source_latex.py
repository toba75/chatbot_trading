from __future__ import annotations

import re
from collections import defaultdict

from latex2mathml.symbols_parser import SYMBOLS

from pdf_math_audit.mathml_candidate import candidate_analysis


_OPENING_MARKERS = {
    "<bold>": "</bold>",
    "<sub>": "</sub>",
    "<sup>": "</sup>",
    "<over>": "</over>",
    "<radicand>": "</radicand>",
}
_CLOSING_MARKERS = set(_OPENING_MARKERS.values()) | {
    "</fraction>",
    "</numerator>",
    "</denominator>",
}
_COMMAND = re.compile(r"\\[A-Za-z]+\Z")


def _symbol_commands() -> dict[str, tuple[str, ...]]:
    by_character: dict[str, list[str]] = defaultdict(list)
    for latex, codepoint in SYMBOLS.items():
        character = chr(int(codepoint, 16))
        if latex == character or _COMMAND.fullmatch(latex):
            by_character[character].append(latex)
    return {
        character: tuple(sorted(set(candidates), key=lambda value: (len(value), value)))
        for character, candidates in by_character.items()
    }


_SYMBOL_COMMANDS = _symbol_commands()
_ESCAPED_ASCII = {
    "#": r"\#",
    "$": r"\$",
    "%": r"\%",
    "&": r"\&",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
}
_ASCII_EQUIVALENTS = {"−": "-", "∗": "*"}


class SourceSerializationError(ValueError):
    pass


def _latex_token(token: str) -> str:
    serialized = []
    for character in token:
        if character in _ASCII_EQUIVALENTS:
            serialized.append(_ASCII_EQUIVALENTS[character])
        elif character in _ESCAPED_ASCII:
            serialized.append(_ESCAPED_ASCII[character])
        elif character == "\\":
            serialized.append(r"\backslash")
        elif character.isascii():
            if character.isspace() or character in "^~":
                raise SourceSerializationError("source_token_unsupported")
            serialized.append(character)
        else:
            candidates = _SYMBOL_COMMANDS.get(character, ())
            if not candidates:
                raise SourceSerializationError("source_symbol_unsupported")
            serialized.append(candidates[0])
    return " ".join(serialized)


def _sequence(
    signature: list[str], position: int = 0, closing: str | None = None
) -> tuple[str, int]:
    parts: list[str] = []
    while position < len(signature):
        token = signature[position]
        if token == closing:
            return " ".join(parts), position + 1
        if token in _CLOSING_MARKERS:
            raise SourceSerializationError("source_relation_unbalanced")
        if token == "<fraction>":
            if signature[position + 1 : position + 2] != ["<numerator>"]:
                raise SourceSerializationError("source_fraction_invalid")
            numerator, position = _sequence(
                signature, position + 2, "</numerator>"
            )
            if signature[position : position + 1] != ["<denominator>"]:
                raise SourceSerializationError("source_fraction_invalid")
            denominator, position = _sequence(
                signature, position + 1, "</denominator>"
            )
            if signature[position : position + 1] != ["</fraction>"]:
                raise SourceSerializationError("source_fraction_invalid")
            parts.append(rf"\frac{{{numerator}}}{{{denominator}}}")
            position += 1
            continue
        if token in _OPENING_MARKERS:
            content, position = _sequence(
                signature, position + 1, _OPENING_MARKERS[token]
            )
            if token == "<bold>":
                parts.append(rf"\mathbf{{{content}}}")
            elif token in {"<sub>", "<sup>", "<over>", "<radicand>"}:
                if not parts:
                    raise SourceSerializationError("source_relation_anchor_missing")
                anchor = parts.pop()
                if token == "<sub>":
                    parts.append(rf"{anchor}_{{{content}}}")
                elif token == "<sup>":
                    parts.append(rf"{anchor}^{{{content}}}")
                elif token == "<over>":
                    parts.append(rf"\stackrel{{{content}}}{{{anchor}}}")
                elif anchor in {r"\sqrt", "√"}:
                    parts.append(rf"\sqrt{{{content}}}")
                else:
                    raise SourceSerializationError("source_radical_anchor_invalid")
            continue
        if token.startswith("<") and token.endswith(">"):
            raise SourceSerializationError("source_relation_unsupported")
        parts.append(_latex_token(token))
        position += 1
    if closing is not None:
        raise SourceSerializationError("source_relation_unbalanced")
    return " ".join(parts), position


def proven_source_latex(region: dict[str, object]) -> tuple[str | None, str | None]:
    signature = region.get("source_relation_signature")
    tokens = region.get("source_canonical_tokens")
    if not isinstance(signature, list) or not isinstance(tokens, list):
        return None, "source_relations_not_established"
    try:
        latex, position = _sequence(signature)
    except (IndexError, SourceSerializationError) as error:
        return None, str(error)
    if position != len(signature):
        return None, "source_relation_unbalanced"
    candidate_tokens, candidate_signature, reason = candidate_analysis(latex)
    if (
        reason is not None
        or candidate_tokens != tokens
        or candidate_signature != signature
    ):
        return None, "deterministic_serialization_not_proven"
    return latex, None
