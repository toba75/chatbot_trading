from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import Any

from latex2mathml.symbols_parser import convert_symbol


IGNORED_ALIGNMENT_CHARACTERS = frozenset("$_^{}")
_EQUIVALENTS = str.maketrans({"-": "−", "*": "∗", "'": "′"})
_LATEX_TOKEN = re.compile(r"\\(?:begin|end)\s*\{[^{}]*\}|\\[A-Za-z]+|\\.")


def _literal_characters(text: str, offset: int) -> list[tuple[str, int]]:
    return [
        (character.translate(_EQUIVALENTS), offset + index)
        for index, character in enumerate(text)
        if not character.isspace()
        and character not in IGNORED_ALIGNMENT_CHARACTERS
    ]


def _latex_character(token: str) -> str | None:
    if token.startswith((r"\begin", r"\end")):
        return None
    codepoint = convert_symbol(token)
    if codepoint is not None:
        return chr(int(codepoint, 16)).translate(_EQUIVALENTS)
    if len(token) == 2 and not token[1].isalpha():
        return token[1].translate(_EQUIVALENTS)
    return None


def document_characters(text: str) -> list[tuple[str, int]]:
    characters: list[tuple[str, int]] = []
    position = 0
    for match in _LATEX_TOKEN.finditer(text):
        characters.extend(_literal_characters(text[position : match.start()], position))
        if character := _latex_character(match.group()):
            characters.append((character, match.start()))
        position = match.end()
    characters.extend(_literal_characters(text[position:], position))
    return characters


def source_characters(
    glyphs: list[dict[str, Any]],
) -> list[tuple[str, dict[str, Any]]]:
    return [
        (character.translate(_EQUIVALENTS), glyph)
        for glyph in glyphs
        for character in glyph["unicode"]
        if not character.isspace()
        and character not in IGNORED_ALIGNMENT_CHARACTERS
    ]


def matching_positions(document_text: str, source_text: str) -> dict[int, int]:
    matcher = SequenceMatcher(None, document_text, source_text, autojunk=False)
    return {
        block.a + offset: block.b + offset
        for block in matcher.get_matching_blocks()
        for offset in range(block.size)
    }
