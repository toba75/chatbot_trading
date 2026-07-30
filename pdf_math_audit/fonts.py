from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from fontTools import agl
from fontTools.cffLib import CFFFontSet
from fontTools.encodings.MacRoman import MacRoman
from fontTools.encodings.StandardEncoding import StandardEncoding
from pypdf._cmap import get_encoding

from pdf_math_audit.limitations import require_supported


SUPPORTED_BASE_ENCODINGS = {
    "/MacRomanEncoding": MacRoman,
    "/StandardEncoding": StandardEncoding,
}
HEX_STRING = re.compile(rb"(?<!<)<([^<>]*)>(?!>)")


@dataclass(frozen=True)
class LoadedFont:
    public: dict[str, Any]
    encoding_names: list[str]
    to_unicode: dict[int, str]
    glyph_ids: dict[str, int]


def codepoints(value: str | None) -> list[str]:
    return [] if value is None else [f"U+{ord(char):04X}" for char in value]


def agl_unicode(glyph_name: str) -> str:
    value = agl.toUnicode(glyph_name)
    require_supported(
        bool(value), "agl_mapping_required", f"/{glyph_name}: aucun Unicode AGL"
    )
    return value


def parse_to_unicode(font: Any) -> dict[int, str]:
    stream = font.get("/ToUnicode")
    if stream is None:
        return {}
    cmap = re.sub(rb"%[^\r\n]*", b"", stream.get_object().get_data())
    hex_strings = HEX_STRING.findall(cmap)
    require_supported(
        all(
            token and len(token) % 2 == 0 and re.fullmatch(rb"[0-9A-Fa-f]+", token)
            for token in hex_strings
        ),
        "to_unicode_cmap_invalid",
        "Chaîne hexadécimale ToUnicode invalide",
    )
    _encoding, character_map = get_encoding(font)
    require_supported(
        character_map.get(-1) == 1,
        "to_unicode_cmap_unsupported",
        "Seules les CMap ToUnicode monooctet sont supportées",
    )
    mappings = {
        ord(source): destination
        for source, destination in character_map.items()
        if isinstance(source, str)
    }
    require_supported(
        all(mappings.values()),
        "to_unicode_cmap_invalid",
        "Destination ToUnicode vide ou invalide",
    )
    require_supported(
        len(mappings) == len(character_map) - 1,
        "to_unicode_cmap_unsupported",
        "Entrée ToUnicode non supportée",
    )
    return mappings


def font_encoding(font: Any) -> tuple[list[str], dict[str, Any]]:
    encoding = font.get("/Encoding", "/StandardEncoding")
    encoding = encoding.get_object() if hasattr(encoding, "get_object") else encoding
    if isinstance(encoding, str):
        base_name = str(encoding)
        raw_differences: list[Any] = []
    else:
        base_name = str(encoding.get("/BaseEncoding", "/StandardEncoding"))
        raw_differences = list(encoding.get("/Differences", []))

    require_supported(
        base_name in SUPPORTED_BASE_ENCODINGS,
        "font_encoding_unsupported",
        f"Encodage non supporté: {base_name}",
    )
    names = list(SUPPORTED_BASE_ENCODINGS[base_name])
    differences: list[dict[str, Any]] = []
    code: int | None = None
    for item in raw_differences:
        if isinstance(item, int):
            code = int(item)
            continue
        require_supported(
            code is not None and 0 <= code <= 255,
            "font_encoding_unsupported",
            "Differences sans code valide",
        )
        glyph_name = str(item).removeprefix("/")
        names[code] = glyph_name
        differences.append(
            {"code": code, "code_hex": f"0x{code:02x}", "glyph_name": glyph_name}
        )
        code += 1
    return names, {"base": base_name, "differences": differences}


def load_font(resource: str, reference: Any) -> LoadedFont:
    font = reference.get_object()
    require_supported(
        str(font.get("/Subtype")) == "/Type1",
        "embedded_type1c_font_required",
        f"{resource}: seule une police Type1 est supportée",
    )
    descriptor = font.get("/FontDescriptor")
    require_supported(
        descriptor is not None,
        "embedded_type1c_font_required",
        f"{resource}: FontDescriptor absent",
    )
    font_file = descriptor.get_object().get("/FontFile3")
    require_supported(
        font_file is not None,
        "embedded_type1c_font_required",
        f"{resource}: FontFile3 embarqué absent",
    )
    font_stream = font_file.get_object()
    require_supported(
        str(font_stream.get("/Subtype")) == "/Type1C",
        "embedded_type1c_font_required",
        f"{resource}: FontFile3 non Type1C",
    )

    cff_bytes = font_stream.get_data()
    cff = CFFFontSet()
    cff.decompile(BytesIO(cff_bytes), None)
    require_supported(
        len(cff.fontNames) == 1,
        "embedded_type1c_font_required",
        f"{resource}: plusieurs polices CFF",
    )
    top = cff[cff.fontNames[0]]
    charset = list(top.charset)
    names, encoding = font_encoding(font)
    to_unicode = parse_to_unicode(font)
    base_font = str(font.get("/BaseFont"))
    return LoadedFont(
        public={
            "resource": resource,
            "xref": int(reference.idnum),
            "base_font": base_font,
            "trace_font": base_font.removeprefix("/").split("+", 1)[-1],
            "subtype": "/Type1",
            "encoding": encoding,
            "to_unicode": {
                f"0x{code:02x}": value for code, value in to_unicode.items()
            },
            "embedded_font": {
                "subtype": "/Type1C",
                "bytes": len(cff_bytes),
                "charset": charset,
            },
        },
        encoding_names=names,
        to_unicode=to_unicode,
        glyph_ids={name: index for index, name in enumerate(charset)},
    )
