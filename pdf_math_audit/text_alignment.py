from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any


IGNORED_ALIGNMENT_CHARACTERS = frozenset("$_^{}")
_EQUIVALENTS = str.maketrans({"-": "−", "*": "∗"})


def document_characters(text: str) -> list[tuple[str, int]]:
    return [
        (character.translate(_EQUIVALENTS), index)
        for index, character in enumerate(text)
        if not character.isspace()
        and character not in IGNORED_ALIGNMENT_CHARACTERS
    ]


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
