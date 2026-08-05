from __future__ import annotations

import re
from collections import defaultdict
from typing import Any


_FONT_TOKEN = re.compile(r"[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+")


def _tokens(metadata: dict[str, Any]) -> set[str]:
    return {
        match.group().casefold()
        for name in (metadata["base_font"], metadata["trace_font"])
        for match in _FONT_TOKEN.finditer(name)
    }


def short_variable_text(text: str) -> bool:
    letters = text.replace(",", "")
    return letters.isalpha() and len(letters) <= 2


def _variable_texts(
    page_glyphs: list[dict[str, Any]],
) -> dict[str, list[str]]:
    usage: dict[tuple[str, int, int, int], list[str]] = defaultdict(list)
    for glyph in page_glyphs:
        rawdict = glyph["rawdict"]
        usage[
            (
                glyph["font_resource"],
                rawdict["block"],
                rawdict["line"],
                rawdict["span"],
            )
        ].append(glyph["unicode"])
    texts_by_font: dict[str, list[str]] = defaultdict(list)
    for (resource, _block, _line, _span), characters in usage.items():
        text = "".join(characters)
        if text.replace(",", "").isalpha():
            texts_by_font[resource].append(text)
    return texts_by_font


def math_and_variable_fonts(
    page_fonts: dict[int, dict[str, dict[str, Any]]],
    page_glyphs: list[dict[str, Any]],
    page: int,
) -> tuple[set[str], dict[str, str]]:
    font_tokens = {
        resource: _tokens(metadata)
        for resource, metadata in page_fonts[page].items()
    }
    math_fonts = {
        resource for resource, tokens in font_tokens.items() if "math" in tokens
    }
    texts_by_font = _variable_texts(page_glyphs)
    variable_fonts = {}
    for resource, tokens in font_tokens.items():
        if (
            "bold" in tokens
            and texts_by_font[resource]
            and all(short_variable_text(text) for text in texts_by_font[resource])
        ):
            variable_fonts[resource] = "standalone"
        elif "italic" in tokens:
            variable_fonts[resource] = "contextual"
    return math_fonts, variable_fonts
