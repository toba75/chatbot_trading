from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from docling_core.types.doc import ContentLayer, DocItemLabel


_INLINE_RELATION = re.compile(r"\A\S+\s*[<>=]\s*\S+\Z")
_INLINE_SYNTAX = re.compile(r"[+*/^_{}()\[\]\\]")
_PROSE_WORD = re.compile(r"[^\W\d_]{2,}")
_NON_PROSE_LABELS = frozenset({DocItemLabel.CODE, DocItemLabel.FORMULA})


def unescaped_positions(text: str, character: str) -> list[int]:
    positions = []
    for index, current in enumerate(text):
        if current != character:
            continue
        backslashes = 0
        cursor = index - 1
        while cursor >= 0 and text[cursor] == "\\":
            backslashes += 1
            cursor -= 1
        if backslashes % 2 == 0:
            positions.append(index)
    return positions


def _unescaped_dollars(text: str) -> list[int]:
    return unescaped_positions(text, "$")


def carries_inline_math(item: Any) -> bool:
    """Un item Docling peut-il porter des mathématiques délimitées par `$` ?

    Les blocs de code emploient `$` comme caractère littéral, et les couches hors
    corps ne sont pas exportées en HTML : les inclure produirait respectivement une
    prose typographiée en mathématiques et un fragment introuvable dans le rendu.
    """
    if getattr(item, "label", None) in _NON_PROSE_LABELS:
        return False
    layer = getattr(item, "content_layer", ContentLayer.BODY)
    return layer == ContentLayer.BODY


def _valid_pair(text: str, start: int, end: int) -> bool:
    latex = text[start + 1 : end]
    return bool(latex) and "\n" not in latex and "\r" not in latex


def _is_monetary_dollar(text: str, positions: list[int], offset: int) -> bool:
    position = positions[offset]
    previous_pair = (
        offset > 0
        and _valid_pair(text, positions[offset - 1], position)
        and is_unambiguous_inline_math(text[positions[offset - 1] + 1 : position])
    )
    next_pair = (
        offset + 1 < len(positions)
        and _valid_pair(text, position, positions[offset + 1])
        and is_unambiguous_inline_math(text[position + 1 : positions[offset + 1]])
    )
    if previous_pair or next_pair:
        return False

    before = text[:position]
    after = text[position + 1 :]
    monetary_suffix = re.search(
        r"(?:^|\s)(?:\d+(?:[.,]\d+)?\s*[kKmMbB]?|[kKmMbB])\Z",
        before,
    )
    monetary_prefix = re.match(r"\d+(?:[.,]\d+)?(?:\b|\Z)", after)
    return bool(monetary_suffix or monetary_prefix)


def _delimiter_positions(text: str) -> list[int]:
    positions = _unescaped_dollars(text)
    return [
        position
        for offset, position in enumerate(positions)
        if not _is_monetary_dollar(text, positions, offset)
    ]


def inline_math_spans(text: str) -> Iterator[tuple[int, int, str]]:
    positions = _delimiter_positions(text)
    for start, closing in zip(positions[::2], positions[1::2], strict=False):
        latex = text[start + 1 : closing]
        if latex and "\n" not in latex and "\r" not in latex:
            yield start, closing + 1, latex


def has_balanced_inline_math_delimiters(text: str) -> bool:
    return len(_delimiter_positions(text)) % 2 == 0


def is_unambiguous_inline_math(latex: str) -> bool:
    stripped = latex.strip()
    if not stripped:
        return False
    if (
        stripped.startswith(("\\", "{"))
        or _INLINE_RELATION.fullmatch(stripped)
        or _INLINE_SYNTAX.search(stripped)
    ):
        return True
    # Sans la moindre syntaxe LaTeX, un mot reste un mot : « et » ou « vaut » entre
    # deux montants ne prouve pas que les dollars qui l'entourent délimitent une
    # formule. Une variable isolée (`x`, `n`, `10`) reste une preuve suffisante.
    return not any(
        character.isspace() for character in stripped
    ) and not _PROSE_WORD.fullmatch(stripped)
