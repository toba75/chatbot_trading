from __future__ import annotations

from collections import defaultdict
from typing import Any

ITALIC_FLAG = 1 << 1
BOLD_FLAG = 1 << 4
MATH_DELIMITERS = frozenset("()[]{}_|‖")


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
    resources = page_fonts[page]
    glyphs_by_font: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for glyph in page_glyphs:
        if glyph["font_resource"] in resources:
            glyphs_by_font[glyph["font_resource"]].append(glyph)
    texts_by_font = _variable_texts(page_glyphs)
    flags_by_font = {
        resource: {glyph["rawdict"].get("span_flags", 0) for glyph in glyphs}
        for resource, glyphs in glyphs_by_font.items()
    }
    math_fonts = {
        resource
        for resource in glyphs_by_font
        if any(
            glyph["glyph_name"] in glyph.get("font_math_glyph_evidence", [])
            for glyph in glyphs_by_font[resource]
        )
        or (
            glyphs_by_font[resource]
            and all(
                glyph["unicode"]
                and set(glyph["unicode"]) <= MATH_DELIMITERS
                for glyph in glyphs_by_font[resource]
            )
        )
        or (
            any(flag & ITALIC_FLAG for flag in flags_by_font[resource])
            and texts_by_font[resource]
            and all(short_variable_text(text) for text in texts_by_font[resource])
            and (
                len(texts_by_font[resource]) >= 3
                or any(flag & 1 for flag in flags_by_font[resource])
            )
        )
    }
    seed_lines = {
        (glyph["rawdict"]["block"], glyph["rawdict"]["line"])
        for resource in math_fonts
        for glyph in glyphs_by_font[resource]
    }
    math_fonts.update(
        resource
        for resource, glyphs in glyphs_by_font.items()
        if any(flag & ITALIC_FLAG for flag in flags_by_font[resource])
        and len(
            {
                (glyph["rawdict"]["block"], glyph["rawdict"]["line"])
                for glyph in glyphs
                if (glyph["rawdict"]["block"], glyph["rawdict"]["line"])
                in seed_lines
            }
        )
        >= 2
    )
    variable_fonts = {}
    for resource, glyphs in glyphs_by_font.items():
        flags = flags_by_font[resource]
        if (
            any(flag & BOLD_FLAG for flag in flags)
            and texts_by_font[resource]
            and all(short_variable_text(text) for text in texts_by_font[resource])
        ):
            variable_fonts[resource] = "standalone"
        elif any(flag & ITALIC_FLAG for flag in flags):
            variable_fonts[resource] = "contextual"
    return math_fonts, variable_fonts
