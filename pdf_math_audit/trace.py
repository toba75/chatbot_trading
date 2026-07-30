from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

import fitz
from pypdf import PdfReader
from pypdf.generic import ContentStream

from pdf_math_audit.fonts import LoadedFont, agl_unicode, codepoints, load_font
from pdf_math_audit.limitations import require_supported, require_unambiguous


@dataclass(frozen=True)
class PageTrace:
    glyphs: list[dict[str, Any]]
    operation_counts: Counter[str]
    fonts: dict[str, LoadedFont]
    layout: dict[str, int]


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


def _source_glyphs(
    page: Any,
    reader: PdfReader,
) -> tuple[list[dict[str, Any]], Counter[str], dict[str, LoadedFont]]:
    resources = page["/Resources"]
    font_dictionary = resources.get("/Font", {})
    font_references = {
        str(resource): reference for resource, reference in font_dictionary.items()
    }
    operations = ContentStream(page.get_contents(), reader).operations
    counts = Counter(operator.decode("latin-1") for _, operator in operations)
    require_supported(
        counts["Do"] == counts["Tr"] == counts["'"] == counts['"'] == 0,
        "page_content_unsupported",
        "Les opérateurs Do, Tr, ' et \" ne sont pas supportés",
    )

    current_font: str | None = None
    current_matrix: list[float] | None = None
    fonts: dict[str, LoadedFont] = {}
    glyphs: list[dict[str, Any]] = []
    for operation_index, (operands, operator) in enumerate(operations):
        if operator == b"Tf":
            current_font = str(operands[0])
        elif operator == b"Tm":
            current_matrix = number_list(operands)
        for chunk in _text_chunks(operands, operator):
            require_unambiguous(
                current_font is not None,
                "text_font_missing",
                f"Texte sans police à l'opération {operation_index}",
            )
            require_unambiguous(
                current_font in font_references,
                "font_resource_missing",
                f"Ressource de police inconnue: {current_font}",
            )
            if current_font not in fonts:
                fonts[current_font] = load_font(
                    current_font, font_references[current_font]
                )
            font = fonts[current_font]
            for code in chunk:
                glyph_name = font.encoding_names[code]
                require_supported(
                    glyph_name != ".notdef" and glyph_name in font.glyph_ids,
                    "cff_charstring_required",
                    f"{current_font} 0x{code:02x}: CharString absent",
                )
                unicode_value = agl_unicode(glyph_name)
                glyphs.append(
                    {
                        "sequence_index": len(glyphs),
                        "operation_index": operation_index,
                        "font_resource": current_font,
                        "code": code,
                        "code_hex": f"0x{code:02x}",
                        "glyph_name": glyph_name,
                        "agl_unicode": unicode_value,
                        "agl_codepoints": codepoints(unicode_value),
                        "cff_gid": font.glyph_ids[glyph_name],
                        "text_matrix": current_matrix,
                    }
                )
    require_supported(
        bool(glyphs) or not operations,
        "page_content_unsupported",
        "Contenu de page sans texte supporté",
    )
    return glyphs, counts, fonts


def _attach_render_and_blocks(
    page: fitz.Page,
    glyphs: list[dict[str, Any]],
    fonts: dict[str, LoadedFont],
) -> dict[str, int]:
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
        for value, gid, origin, bbox in span["chars"]
    ]
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
        rendered["unicode_matches_agl"] = rendered_unicode == source["agl_unicode"]
        unicode_matches += rendered["unicode_matches_agl"]
        source["rendered"] = rendered

    rawdict = page.get_text("rawdict", sort=False)
    block_index: defaultdict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
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
                    block_index[key].append(
                        {
                            "block": block_id,
                            "line": line_id,
                            "span": span_id,
                            "char": char_id,
                            "block_bbox": number_list(block["bbox"]),
                            "line_bbox": number_list(line["bbox"]),
                        }
                    )

    claimed: set[tuple[int, int, int, int]] = set()
    for source in glyphs:
        rendered = source["rendered"]
        key = (
            rendered["font"],
            round(rendered["origin"][0], 3),
            round(rendered["origin"][1], 3),
            rendered["unicode"],
        )
        matches = block_index.get(key, [])
        require_unambiguous(
            len(matches) == 1,
            "rawdict_alignment_ambiguous",
            f"Association rawdict non univoque à {source['sequence_index']}: {len(matches)}",
        )
        match = matches[0]
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
        "rawdict_characters": rawdict_characters,
        "rawdict_text_blocks": sum(
            block.get("type") == 0 for block in rawdict["blocks"]
        ),
        "trace_unicode_matches": unicode_matches,
        "trace_unicode_mismatches": len(trace) - unicode_matches,
    }


def trace_page(
    source_page: Any, rendered_page: fitz.Page, reader: PdfReader
) -> PageTrace:
    glyphs, operation_counts, fonts = _source_glyphs(source_page, reader)
    layout = _attach_render_and_blocks(rendered_page, glyphs, fonts)
    return PageTrace(glyphs, operation_counts, fonts, layout)
