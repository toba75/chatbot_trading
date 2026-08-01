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


def math_and_variable_fonts(
    page_fonts: dict[int, dict[str, dict[str, Any]]],
    page_glyphs: list[dict[str, Any]],
    page: int,
) -> tuple[set[str], set[str]]:
    font_tokens = {
        resource: _tokens(metadata)
        for resource, metadata in page_fonts[page].items()
    }
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
        texts_by_font[resource].append("".join(characters))

    math_fonts = {
        resource for resource, tokens in font_tokens.items() if "math" in tokens
    }
    variable_fonts = {
        resource
        for resource, tokens in font_tokens.items()
        if "bold" in tokens
        and texts_by_font[resource]
        and all(text.isalpha() and len(text) <= 2 for text in texts_by_font[resource])
    }
    return math_fonts, variable_fonts
