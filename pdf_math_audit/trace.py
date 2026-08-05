from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

import fitz
from pypdf import PdfReader, Transformation
from pypdf.generic import ContentStream

from pdf_math_audit.fonts import (
    LoadedFont,
    _trace_font,
    agl_unicode,
    codepoints,
    load_font,
)
from pdf_math_audit.limitations import (
    AnalysisLimitation,
    require_supported,
    require_unambiguous,
)


UNSUPPORTED_OPERATORS = {"Tr", "'", '"', "INLINE IMAGE", "sh"}
FORM_TEXT_OPERATORS = {b"Tj", b"TJ", b"'", b'"'}
IDENTITY_MATRIX = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


@dataclass(frozen=True)
class PageTrace:
    glyphs: list[dict[str, Any]]
    operation_counts: Counter[str]
    fonts: dict[str, LoadedFont]
    layout: dict[str, int]
    horizontal_rules: list[dict[str, float | int]]
    font_limitations: list[dict[str, str]]
    opaque_regions: list[dict[str, Any]]


def number_list(values: Any) -> list[float]:
    return [float(value) for value in values]


def _original_bytes(value: Any) -> bytes | None:
    raw = getattr(value, "original_bytes", None)
    if raw is not None:
        return bytes(raw)
    return bytes(value) if isinstance(value, (bytes, bytearray)) else None


def _text_chunks(operands: list[Any], operator: bytes) -> list[bytes]:
    if operator == b"Tj":
        raw = _original_bytes(operands[-1])
        return [] if raw is None else [raw]
    if operator == b"TJ":
        return [
            raw for item in operands[0] if (raw := _original_bytes(item)) is not None
        ]
    return []


def _resolved(value: Any) -> Any:
    return value.get_object() if hasattr(value, "get_object") else value


def _font_resource_key(
    resource: str, xref: int, first_xrefs: dict[str, int]
) -> str:
    first_xrefs.setdefault(resource, xref)
    return resource if first_xrefs[resource] == xref else f"{resource}@{xref}"


def _matrix(values: Any, *, context: str) -> tuple[float, ...]:
    require_supported(
        values is not None and len(values) == 6,
        "form_xobject_matrix_invalid",
        f"{context}: matrice affine invalide",
    )
    return tuple(float(value) for value in values)


def _form_bbox(values: Any, *, context: str) -> tuple[float, ...]:
    require_supported(
        values is not None and len(values) == 4,
        "form_xobject_bbox_invalid",
        f"{context}: BBox invalide",
    )
    bbox = tuple(float(value) for value in values)
    require_supported(
        bbox[0] < bbox[2] and bbox[1] < bbox[3],
        "form_xobject_bbox_invalid",
        f"{context}: BBox vide ou inversée",
    )
    return bbox


def _compose(
    local: tuple[float, ...], parent: tuple[float, ...]
) -> tuple[float, ...]:
    return tuple(Transformation(local).transform(Transformation(parent)).ctm)


def _xobject(resources: Any, name: Any, *, context: str) -> tuple[Any, Any]:
    resources = _resolved(resources)
    dictionary = _resolved(resources.get("/XObject", {}))
    reference = dictionary.get(name)
    require_supported(
        reference is not None,
        "form_xobject_resource_missing",
        f"{context}: ressource XObject inconnue {name}",
    )
    return reference, _resolved(reference)


def _form_contains_text(
    reference: Any,
    inherited_resources: Any,
    reader: PdfReader,
    active: set[tuple[int, int]],
) -> bool:
    identity = (
        int(getattr(reference, "idnum", 0)),
        int(getattr(reference, "generation", 0)),
    )
    require_supported(
        identity not in active,
        "form_xobject_cycle_unsupported",
        "Cycle de Form XObject non supporté",
    )
    active.add(identity)
    form = _resolved(reference)
    resources = form.get("/Resources")
    resources = inherited_resources if resources is None else _resolved(resources)
    operations = ContentStream(form, reader).operations
    if any(operator in FORM_TEXT_OPERATORS for _operands, operator in operations):
        active.remove(identity)
        return True
    for operands, operator in operations:
        if operator != b"Do":
            continue
        nested_reference, nested = _xobject(
            resources, operands[0], context="Form XObject imbriquée"
        )
        if str(nested.get("/Subtype")) == "/Form" and _form_contains_text(
            nested_reference, resources, reader, active
        ):
            active.remove(identity)
            return True
    active.remove(identity)
    return False


def _top_left_bbox(
    bbox: tuple[float, ...],
    ctm: tuple[float, ...],
    page: fitz.Page,
) -> list[float]:
    transform = Transformation(ctm)
    points = [
        fitz.Point(*transform.apply_on(point)) * page.transformation_matrix
        for point in (
            (bbox[0], bbox[1]),
            (bbox[0], bbox[3]),
            (bbox[2], bbox[1]),
            (bbox[2], bbox[3]),
        )
    ]
    return [
        min(point.x for point in points),
        min(point.y for point in points),
        max(point.x for point in points),
        max(point.y for point in points),
    ]


def _opaque_xobject_regions(
    operations: list[tuple[list[Any], bytes]],
    resources: Any,
    reader: PdfReader,
    page: fitz.Page,
) -> list[dict[str, Any]]:
    current = IDENTITY_MATRIX
    stack: list[tuple[float, ...]] = []
    regions = []
    for operands, operator in operations:
        if operator == b"q":
            stack.append(current)
        elif operator == b"Q":
            require_unambiguous(
                bool(stack),
                "graphics_state_stack_unbalanced",
                "Restauration d’un état graphique absent",
            )
            current = stack.pop()
        elif operator == b"cm":
            current = _compose(_matrix(operands, context="Opérateur cm"), current)
        elif operator == b"Do":
            reference, xobject = _xobject(
                resources, operands[0], context="Contenu de page"
            )
            subtype = str(xobject.get("/Subtype"))
            require_supported(
                subtype in {"/Form", "/Image"},
                "xobject_subtype_unsupported",
                f"{operands[0]}: XObject non supporté {subtype}",
            )
            if subtype == "/Form":
                bbox = _form_bbox(
                    xobject.get("/BBox"), context=f"{operands[0]} /BBox"
                )
                local_matrix = _matrix(
                    xobject.get("/Matrix", IDENTITY_MATRIX),
                    context=f"{operands[0]} /Matrix",
                )
                kind = "form_xobject"
                text_traced = _form_contains_text(reference, resources, reader, set())
                reason = {
                    "code": "form_xobject_vector_content_unqualified",
                    "message": "Le contenu vectoriel du Form XObject reste hors qualification",
                }
            else:
                bbox = (0.0, 0.0, 1.0, 1.0)
                local_matrix = IDENTITY_MATRIX
                kind = "image_xobject"
                text_traced = False
                reason = {
                    "code": "image_xobject_content_unqualified",
                    "message": "Le contenu matriciel du XObject reste hors qualification",
                }
            regions.append(
                {
                    "kind": kind,
                    "resource": str(operands[0]),
                    "xref": int(getattr(reference, "idnum", 0)),
                    "bbox": _top_left_bbox(
                        bbox, _compose(local_matrix, current), page
                    ),
                    "bbox_coord_origin": "TOPLEFT",
                    "text_traced": text_traced,
                    "reason": reason,
                }
            )
    return regions


def _source_glyphs(
    page: Any,
    rendered_page: fitz.Page,
    reader: PdfReader,
) -> tuple[
    list[dict[str, Any]],
    Counter[str],
    dict[str, LoadedFont],
    list[dict[str, str]],
    list[dict[str, Any]],
    set[str],
]:
    resources = page["/Resources"]
    operations = ContentStream(page.get_contents(), reader).operations
    opaque_regions = _opaque_xobject_regions(
        operations, resources, reader, rendered_page
    )
    counts: Counter[str] = Counter()
    fonts: dict[str, LoadedFont] = {}
    font_limitations: dict[str, AnalysisLimitation] = {}
    limited_trace_fonts: set[str] = set()
    first_font_xrefs: dict[str, int] = {}
    glyphs: list[dict[str, Any]] = []
    sequence_index = 0
    operation_index = 0

    def trace_stream(
        content: Any,
        stream_resources: Any,
        active_forms: set[tuple[int, int]],
    ) -> None:
        nonlocal operation_index, sequence_index
        stream_resources = _resolved(stream_resources)
        stream_fonts = stream_resources.get("/Font", {})
        current_font: str | None = None
        current_matrix: list[float] | None = None
        stream_operations = ContentStream(content, reader).operations
        unsupported = sorted(
            UNSUPPORTED_OPERATORS.intersection(
                operator.decode("latin-1") for _operands, operator in stream_operations
            )
        )
        require_supported(
            not unsupported,
            "page_content_unsupported",
            f"Opérateurs non supportés: {', '.join(unsupported)}",
        )
        for operands, operator in stream_operations:
            current_operation = operation_index
            operation_index += 1
            counts[operator.decode("latin-1")] += 1
            if operator == b"Tf":
                current_font = str(operands[0])
            elif operator == b"Tm":
                current_matrix = number_list(operands)
            elif operator == b"Do":
                reference, xobject = _xobject(
                    stream_resources, operands[0], context="Contenu imbriqué"
                )
                if (
                    str(xobject.get("/Subtype")) == "/Form"
                    and _form_contains_text(
                        reference, stream_resources, reader, set()
                    )
                ):
                    identity = (
                        int(getattr(reference, "idnum", 0)),
                        int(getattr(reference, "generation", 0)),
                    )
                    require_supported(
                        identity not in active_forms,
                        "form_xobject_cycle_unsupported",
                        "Cycle de Form XObject non supporté",
                    )
                    child_resources = xobject.get("/Resources")
                    child_resources = (
                        stream_resources
                        if child_resources is None
                        else _resolved(child_resources)
                    )
                    trace_stream(xobject, child_resources, active_forms | {identity})

            for chunk in _text_chunks(operands, operator):
                require_unambiguous(
                    current_font is not None,
                    "text_font_missing",
                    f"Texte sans police à l'opération {current_operation}",
                )
                require_unambiguous(
                    current_font in stream_fonts,
                    "font_resource_missing",
                    f"Ressource de police inconnue: {current_font}",
                )
                reference = (
                    stream_fonts.raw_get(current_font)
                    if hasattr(stream_fonts, "raw_get")
                    else stream_fonts[current_font]
                )
                xref = int(getattr(reference, "idnum", 0))
                font_key = _font_resource_key(current_font, xref, first_font_xrefs)
                if font_key not in fonts and font_key not in font_limitations:
                    try:
                        fonts[font_key] = load_font(font_key, reference)
                    except AnalysisLimitation as limitation:
                        font_limitations[font_key] = limitation
                        limited_trace_fonts.add(
                            _trace_font(str(_resolved(reference).get("/BaseFont", "")))
                        )
                if font_key in font_limitations:
                    sequence_index += len(chunk)
                    continue
                font = fonts[font_key]
                require_supported(
                    len(chunk) % font.code_bytes == 0,
                    "font_code_width_mismatch",
                    f"{font_key}: chaîne incompatible avec la largeur des codes",
                )
                for offset in range(0, len(chunk), font.code_bytes):
                    code = int.from_bytes(
                        chunk[offset : offset + font.code_bytes], "big"
                    )
                    glyph_name = font.encoding_names.get(code, ".notdef")
                    require_supported(
                        glyph_name != ".notdef" and glyph_name in font.glyph_ids,
                        "embedded_glyph_required",
                        f"{font_key} 0x{code:0{font.code_bytes * 2}x}: glyphe absent",
                    )
                    unicode_method = "to_unicode" if font.source_unicode else "agl"
                    unicode_value = font.source_unicode.get(code) or agl_unicode(
                        glyph_name
                    )
                    glyphs.append(
                        {
                            "sequence_index": sequence_index,
                            "operation_index": current_operation,
                            "font_resource": font_key,
                            "code": code,
                            "code_hex": f"0x{code:0{font.code_bytes * 2}x}",
                            "glyph_name": glyph_name,
                            "source_unicode": unicode_value,
                            "source_unicode_method": unicode_method,
                            "source_unicode_codepoints": codepoints(unicode_value),
                            "agl_unicode": (
                                unicode_value if unicode_method == "agl" else None
                            ),
                            "agl_codepoints": (
                                codepoints(unicode_value)
                                if unicode_method == "agl"
                                else []
                            ),
                            "cff_gid": font.glyph_ids[glyph_name],
                            "text_matrix": current_matrix,
                        }
                    )
                    sequence_index += 1

    trace_stream(page.get_contents(), resources, set())
    if not glyphs and font_limitations:
        raise next(iter(font_limitations.values()))
    require_supported(
        bool(glyphs) or not operations,
        "page_content_unsupported",
        "Contenu de page sans texte supporté",
    )
    return (
        glyphs,
        counts,
        fonts,
        [
            limitation.as_dict() | {"font_resource": resource}
            for resource, limitation in font_limitations.items()
        ],
        opaque_regions,
        limited_trace_fonts,
    )


def _rendered_trace(
    page: fitz.Page, supported_fonts: set[str]
) -> tuple[list[dict[str, Any]], int]:
    trace = [
        {
            "font": span["font"],
            "size": span["size"],
            "seqno": span["seqno"],
            "unicode": value,
            "gid": gid,
            "origin": number_list(origin),
            "bbox": number_list(bbox),
        }
        for span in page.get_texttrace()
        if span["font"] in supported_fonts
        for value, gid, origin, bbox in span["chars"]
    ]
    real: defaultdict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for character in trace:
        if character["gid"] >= 0:
            real[
                (
                    character["font"],
                    character["seqno"],
                    character["unicode"],
                    tuple(character["origin"]),
                    character["size"],
                )
            ].append(character)
    synthetic = [character for character in trace if character["gid"] < 0]
    for character in synthetic:
        bbox = character["bbox"]
        key = (
            character["font"],
            character["seqno"],
            character["unicode"],
            tuple(character["origin"]),
            character["size"],
        )
        twins = real[key]
        within_twin = False
        if len(twins) == 1:
            twin_bbox = twins[0]["bbox"]
            within_twin = (
                twin_bbox[0] - 0.01 <= bbox[0] <= twin_bbox[2] + 0.01
                and twin_bbox[0] - 0.01 <= bbox[2] <= twin_bbox[2] + 0.01
                and twin_bbox[1] - 0.01 <= bbox[1] <= twin_bbox[3] + 0.01
                and twin_bbox[1] - 0.01 <= bbox[3] <= twin_bbox[3] + 0.01
            )
        require_unambiguous(
            character["gid"] == -1
            and (bbox[0] == bbox[2] or bbox[1] == bbox[3])
            and within_twin,
            "rendered_synthetic_character_ambiguous",
            "Caractère synthétique MuPDF sans glyphe jumeau univoque",
        )
    return [character for character in trace if character["gid"] >= 0], len(
        synthetic
    )


def _select_rawdict_match(
    exact_matches: list[dict[str, Any]],
    positioned_matches: list[dict[str, Any]],
    sequence_index: int,
) -> tuple[dict[str, Any], bool]:
    matches = exact_matches or positioned_matches
    require_unambiguous(
        len(matches) == 1,
        "rawdict_alignment_ambiguous",
        f"Association rawdict non univoque à {sequence_index}: {len(matches)}",
    )
    return matches[0], bool(exact_matches)


def _attach_render_and_blocks(
    page: fitz.Page,
    glyphs: list[dict[str, Any]],
    fonts: dict[str, LoadedFont],
    limited_trace_fonts: set[str],
) -> dict[str, int]:
    supported_fonts = {font.public["trace_font"] for font in fonts.values()}
    ambiguous_fonts = supported_fonts & limited_trace_fonts
    require_unambiguous(
        not ambiguous_fonts,
        "rendered_font_resource_ambiguous",
        "Ressources supportées et non supportées homonymes: "
        + ", ".join(sorted(ambiguous_fonts)),
    )
    trace, synthetic_duplicates = _rendered_trace(page, supported_fonts)
    require_unambiguous(
        len(trace) == len(glyphs),
        "source_trace_length_mismatch",
        f"Source/trace: {len(glyphs)} != {len(trace)}",
    )
    unicode_matches = 0
    for source, rendered in zip(glyphs, trace, strict=True):
        font = fonts[source["font_resource"]]
        require_unambiguous(
            rendered["font"] == font.public["trace_font"],
            "rendered_font_mismatch",
            f"Police trace divergente à {source['sequence_index']}",
        )
        require_unambiguous(
            rendered["gid"] == source["cff_gid"],
            "rendered_gid_mismatch",
            f"GID divergent à {source['sequence_index']}",
        )
        rendered_unicode = chr(rendered["unicode"])
        rendered["unicode_text"] = rendered_unicode
        rendered["unicode_codepoints"] = codepoints(rendered_unicode)
        rendered["unicode_matches_source"] = (
            rendered_unicode == source["source_unicode"]
        )
        unicode_matches += rendered["unicode_matches_source"]
        source["rendered"] = rendered

    rawdict = page.get_text("rawdict", sort=False)
    block_index: defaultdict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    positioned_block_index: defaultdict[
        tuple[Any, ...], list[dict[str, Any]]
    ] = defaultdict(list)
    rawdict_characters = 0
    for block_id, block in enumerate(rawdict["blocks"]):
        if block.get("type") != 0:
            continue
        for line_id, line in enumerate(block["lines"]):
            for span_id, span in enumerate(line["spans"]):
                for char_id, char in enumerate(span["chars"]):
                    require_unambiguous(
                        len(char["c"]) == 1,
                        "rawdict_character_ambiguous",
                        f"Caractère rawdict non unitaire: {char['c']!r}",
                    )
                    rawdict_characters += 1
                    key = (
                        span["font"],
                        round(char["origin"][0], 3),
                        round(char["origin"][1], 3),
                        ord(char["c"]),
                    )
                    match = {
                        "block": block_id,
                        "line": line_id,
                        "span": span_id,
                        "char": char_id,
                        "unicode_text": char["c"],
                        "unicode_codepoints": codepoints(char["c"]),
                        "span_flags": span["flags"],
                        "block_bbox": number_list(block["bbox"]),
                        "line_bbox": number_list(line["bbox"]),
                    }
                    block_index[key].append(match)
                    positioned_block_index[key[:3]].append(match)

    claimed: set[tuple[int, int, int, int]] = set()
    rawdict_unicode_mismatches = 0
    for source in glyphs:
        rendered = source["rendered"]
        key = (
            rendered["font"],
            round(rendered["origin"][0], 3),
            round(rendered["origin"][1], 3),
            rendered["unicode"],
        )
        match, rawdict_unicode_matches = _select_rawdict_match(
            block_index.get(key, []),
            positioned_block_index.get(key[:3], []),
            source["sequence_index"],
        )
        rawdict_unicode_mismatches += not rawdict_unicode_matches
        match["unicode_matches_rendered"] = rawdict_unicode_matches
        identity = (match["block"], match["line"], match["span"], match["char"])
        require_unambiguous(
            identity not in claimed,
            "rawdict_alignment_reused",
            f"Association rawdict réutilisée à {source['sequence_index']}",
        )
        claimed.add(identity)
        source["rawdict"] = match
    return {
        "trace_characters": len(trace),
        "trace_synthetic_duplicates": synthetic_duplicates,
        "rawdict_characters": rawdict_characters,
        "rawdict_text_blocks": sum(
            block.get("type") == 0 for block in rawdict["blocks"]
        ),
        "rawdict_unicode_mismatches": rawdict_unicode_mismatches,
        "trace_unicode_matches": unicode_matches,
        "trace_unicode_mismatches": len(trace) - unicode_matches,
    }


def _horizontal_rules(page: fitz.Page) -> list[dict[str, float | int]]:
    rules = []
    for drawing in page.get_drawings():
        items = drawing["items"]
        if drawing["type"] != "s" or len(items) != 1 or items[0][0] != "l":
            continue
        _kind, start, end = items[0]
        if abs(start.y - end.y) > 0.01:
            continue
        rules.append(
            {
                "x0": min(start.x, end.x),
                "y": (start.y + end.y) / 2,
                "x1": max(start.x, end.x),
                "width": float(drawing["width"]),
                "seqno": int(drawing["seqno"]),
            }
        )
    return rules


def trace_page(
    source_page: Any, rendered_page: fitz.Page, reader: PdfReader
) -> PageTrace:
    (
        glyphs,
        operation_counts,
        fonts,
        font_limitations,
        opaque_regions,
        limited_trace_fonts,
    ) = _source_glyphs(source_page, rendered_page, reader)
    layout = _attach_render_and_blocks(
        rendered_page, glyphs, fonts, limited_trace_fonts
    )
    return PageTrace(
        glyphs,
        operation_counts,
        fonts,
        layout,
        _horizontal_rules(rendered_page),
        font_limitations,
        opaque_regions,
    )
