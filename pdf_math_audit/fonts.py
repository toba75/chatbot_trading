from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from fontTools import agl
from fontTools.cffLib import CFFFontSet
from fontTools.encodings.MacRoman import MacRoman
from fontTools.encodings.StandardEncoding import StandardEncoding

from pdf_math_audit.limitations import require_supported


SUPPORTED_BASE_ENCODINGS = {
    "/MacRomanEncoding": MacRoman,
    "/StandardEncoding": StandardEncoding,
}


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

    lines = (
        stream.get_object().get_data().decode("latin-1").replace("\r", "").splitlines()
    )
    result: dict[int, str] = {}
    mode: str | None = None
    for raw_line in lines:
        line = raw_line.split("%", 1)[0].strip()
        if line.endswith("beginbfchar"):
            mode = "char"
            continue
        if line.endswith("beginbfrange"):
            mode = "range"
            continue
        if line in {"endbfchar", "endbfrange"}:
            mode = None
            continue
        if not line or mode is None:
            continue

        tokens = re.findall(r"<([0-9A-Fa-f]+)>", line)
        if mode == "char":
            require_supported(
                len(tokens) == 2,
                "to_unicode_cmap_unsupported",
                f"ToUnicode bfchar non supporté: {line}",
            )
            source, destination = tokens
            require_supported(
                len(source) == 2,
                "to_unicode_cmap_unsupported",
                f"Code ToUnicode non monooctet: {source}",
            )
            result[int(source, 16)] = bytes.fromhex(destination).decode("utf-16-be")
            continue

        require_supported(
            len(tokens) == 3 and "[" not in line,
            "to_unicode_cmap_unsupported",
            f"ToUnicode bfrange non supporté: {line}",
        )
        start, end, destination = tokens
        require_supported(
            len(start) == len(end) == 2,
            "to_unicode_cmap_unsupported",
            f"Plage ToUnicode non monooctet: {line}",
        )
        base = bytes.fromhex(destination).decode("utf-16-be")
        require_supported(
            len(base) == 1,
            "to_unicode_cmap_unsupported",
            f"Destination ToUnicode complexe: {destination}",
        )
        for offset, source in enumerate(range(int(start, 16), int(end, 16) + 1)):
            result[source] = chr(ord(base) + offset)
    return result


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
