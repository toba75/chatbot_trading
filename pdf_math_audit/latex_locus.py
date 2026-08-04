from __future__ import annotations

from functools import lru_cache
from typing import Any, Iterable

from pylatexenc.latexwalker import LatexWalker

from pdf_math_audit.latex_boundaries import expanded_latex_locus
from pdf_math_audit.mathml_candidate import candidate_analysis


_SEARCH_RADIUS = 128
_MAX_CANDIDATE_INTERVALS = 512
_WRAPPER_MACROS = {
    "bar",
    "boldsymbol",
    "hat",
    "mathbb",
    "mathbf",
    "mathcal",
    "mathit",
    "mathrm",
    "mathsf",
    "mathtt",
    "overline",
    "underline",
    "vec",
}


def _semantic_tokens(tokens: object) -> object:
    if not isinstance(tokens, list):
        return tokens
    return [token for token in tokens if token != "&"]


def _walk_nodes(nodes: Iterable[Any]) -> Iterable[Any]:
    for node in nodes:
        yield node
        children = getattr(node, "nodelist", None)
        if children:
            yield from _walk_nodes(children)
        arguments = getattr(getattr(node, "nodeargd", None), "argnlist", None) or []
        for argument in arguments:
            if argument is not None:
                yield argument
                nested = getattr(argument, "nodelist", None)
                if nested:
                    yield from _walk_nodes(nested)


@lru_cache(maxsize=256)
def _boundaries(latex: str) -> tuple[int, ...]:
    try:
        nodes, _position, _length = LatexWalker(latex).get_latex_nodes()
    except Exception:
        return tuple(range(len(latex) + 1))
    positions = {0, len(latex)}
    for node in _walk_nodes(nodes):
        start = int(node.pos)
        end = start + int(node.len)
        positions.update((start, end))
        chars = getattr(node, "chars", None)
        if chars is not None:
            for offset, character in enumerate(chars):
                if not character.isspace():
                    positions.update((start + offset, start + offset + 1))
    return tuple(sorted(positions))


@lru_cache(maxsize=256)
def _macro_bounds(latex: str) -> tuple[tuple[int, int], ...]:
    try:
        nodes, _position, _length = LatexWalker(latex).get_latex_nodes()
    except Exception:
        return ()
    return tuple(
        (int(node.pos), int(node.pos) + int(node.len))
        for node in _walk_nodes(nodes)
        if getattr(node, "macroname", None) in _WRAPPER_MACROS
    )


def _complete_macros(latex: str, start: int, end: int) -> tuple[int, int]:
    changed = True
    bounds = _macro_bounds(latex)
    while changed:
        changed = False
        for macro_start, macro_end in bounds:
            if macro_start < start < macro_end:
                start = macro_start
                changed = True
            if macro_start < end < macro_end:
                end = macro_end
                changed = True
    return start, end


def _candidate_intervals(
    latex: str, start: int, end: int
) -> list[tuple[int, int]]:
    boundaries = _boundaries(latex)
    starts = [
        position
        for position in boundaries
        if max(0, start - _SEARCH_RADIUS)
        <= position
        <= min(len(latex), start + _SEARCH_RADIUS)
    ]
    ends = [
        position
        for position in boundaries
        if max(0, end - _SEARCH_RADIUS)
        <= position
        <= min(len(latex), end + _SEARCH_RADIUS)
    ]
    intervals = {
        (left, right)
        for left in starts
        for right in ends
        if left < right and left < end and right > start
    }
    return sorted(
        intervals,
        key=lambda interval: (
            abs(interval[0] - start) + abs(interval[1] - end),
            interval[1] - interval[0],
        ),
    )[:_MAX_CANDIDATE_INTERVALS]


def formula_locus(
    latex: str,
    region: dict[str, Any],
    *,
    minimum_start: int = 0,
) -> tuple[int, int, str]:
    span = region.get("candidate_charspan")
    if not isinstance(span, list) or len(span) != 2:
        raise ValueError("candidate_charspan_missing")
    start, end = span
    candidate_tokens = region.get("candidate_tokens")
    candidate_signature = region.get("candidate_relation_signature")
    source_tokens = region.get("source_canonical_tokens")
    source_glyph_text = str(region.get("source_glyph_text", ""))
    start, end = _complete_macros(latex, start, end)
    start, end = expanded_latex_locus(
        latex,
        start,
        end,
        source_glyph_text,
    )
    try:
        initial_tokens, initial_signature, initial_reason = candidate_analysis(
            latex[start:end]
        )
    except StopIteration:
        initial_tokens = initial_signature = initial_reason = None
    if start >= minimum_start and initial_reason is None and (
        _semantic_tokens(initial_tokens) == source_tokens
        or (
            initial_tokens == candidate_tokens
            and initial_signature == candidate_signature
        )
    ):
        return start, end, latex[start:end]

    candidate_match: tuple[int, int] | None = None
    token_match: tuple[int, int] | None = None
    source_match: tuple[int, int] | None = None
    for left, right in _candidate_intervals(latex, start, end):
        if left < minimum_start:
            continue
        try:
            tokens, signature, reason = candidate_analysis(latex[left:right])
        except StopIteration:
            continue
        if reason is not None:
            continue
        if (
            candidate_match is None
            and tokens == candidate_tokens
            and signature == candidate_signature
        ):
            candidate_match = (left, right)
        if token_match is None and tokens == candidate_tokens:
            token_match = (left, right)
        if _semantic_tokens(tokens) == source_tokens:
            source_match = (left, right)
            break
    selected = source_match or candidate_match or token_match
    if selected is None:
        selected = expanded_latex_locus(
            latex,
            start,
            end,
            source_glyph_text,
        )
    start, end = _complete_macros(latex, selected[0], selected[1])
    start, end = expanded_latex_locus(
        latex,
        start,
        end,
        source_glyph_text,
    )
    return start, end, latex[start:end]
