from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any

from fontTools import agl
from fontTools.cffLib import CFFFontSet
from fontTools.encodings.MacRoman import MacRoman
from fontTools.encodings.StandardEncoding import StandardEncoding
from fontTools.ttLib import TTFont
from reportlab.pdfbase._fontdata_enc_winansi import WinAnsiEncoding

from pdf_math_audit.cmap import parse_to_unicode
from pdf_math_audit.limitations import require_supported
from pdf_math_audit.pdf_indicators import is_math_indicator


SUPPORTED_BASE_ENCODINGS = {
    "/MacRomanEncoding": MacRoman,
    "/StandardEncoding": StandardEncoding,
    "/WinAnsiEncoding": WinAnsiEncoding,
}
TEX_GLYPH_UNICODE = {
    "Sigma": "Σ",
    "alpha": "α",
    "angle": "∠",
    "arrowleft": "←",
    "arrowright": "→",
    "asteriskmath": "∗",
    "bardbl": "‖",
    "braceleftBigg": "{",
    "bracketleftBig": "[",
    "bracketleftbig": "[",
    "bracketleftbigg": "[",
    "bracketrightBig": "]",
    "bracketrightbig": "]",
    "bracketrightbigg": "]",
    "element": "∈",
    "epsilon1": "ϵ",
    "gamma": "γ",
    "greaterequal": "≥",
    "intersection": "∩",
    "integraldisplay": "∫",
    "integraltext": "∫",
    "lambda": "λ",
    "latticetop": "⊤",
    "lessequal": "≤",
    "lessmuch": "≪",
    "mapsto": "↦",
    "minus": "−",
    "multiply": "×",
    "nabla": "∇",
    "parenleftBig": "(",
    "parenleftBigg": "(",
    "parenleftbig": "(",
    "parenleftbigg": "(",
    "parenrightBig": ")",
    "parenrightBigg": ")",
    "parenrightbig": ")",
    "parenrightbigg": ")",
    "partialdiff": "∂",
    "phi": "φ",
    "pi": "π",
    "prime": "′",
    "productdisplay": "∏",
    "producttext": "∏",
    "radical": "√",
    "radicalBig": "√",
    "radicalbig": "√",
    "radicalbigg": "√",
    "radicalbt": "√",
    "radicaltp": "√",
    "radicalvertex": "√",
    "rho": "ρ",
    "sigma": "σ",
    "similar": "∼",
    "summationdisplay": "∑",
    "summationtext": "∑",
    "tau": "τ",
    "theta": "θ",
    "union": "∪",
}
TEX_EXTENSIBLE_DELIMITER_GLYPHS = {
    "bracketleftbt",
    "bracketlefttp",
    "bracketrightbt",
    "bracketrighttp",
}


@dataclass(frozen=True)
class LoadedFont:
    public: dict[str, Any]
    code_bytes: int
    encoding_names: dict[int, str]
    source_unicode: dict[int, str]
    to_unicode: dict[int, str]
    glyph_ids: dict[str, int]


def codepoints(value: str | None) -> list[str]:
    return [] if value is None else [f"U+{ord(char):04X}" for char in value]


def agl_unicode(glyph_name: str) -> str:
    value = agl.toUnicode(glyph_name) or TEX_GLYPH_UNICODE.get(glyph_name, "")
    require_supported(
        bool(value), "agl_mapping_required", f"/{glyph_name}: aucun Unicode AGL"
    )
    return value


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
    names = [name or ".notdef" for name in SUPPORTED_BASE_ENCODINGS[base_name]]
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


def _trace_font(base_font: str) -> str:
    return base_font.removeprefix("/").split("+", 1)[-1][:24]


def _math_glyph_evidence(glyph_names: list[str]) -> list[str]:
    """Return font-internal evidence without interpreting the font's name."""
    return sorted(set(glyph_names) & TEX_GLYPH_UNICODE.keys())


def _math_unicode_evidence(values: dict[int, str]) -> list[str]:
    return sorted({value for value in values.values() if is_math_indicator(value)})


def _load_type1_font(resource: str, reference: Any, font: Any) -> LoadedFont:
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
    to_unicode_anomalies: list[dict[str, Any]] = []
    to_unicode = parse_to_unicode(
        font,
        allow_simple_codespace_mismatch=True,
        anomalies=to_unicode_anomalies,
    )
    base_font = str(font.get("/BaseFont"))
    return LoadedFont(
        public={
            "resource": resource,
            "xref": int(reference.idnum),
            "base_font": base_font,
            "trace_font": _trace_font(base_font),
            "subtype": "/Type1",
            "encoding": encoding,
            "to_unicode": {
                f"0x{code:02x}": value for code, value in to_unicode.items()
            },
            "to_unicode_anomalies": to_unicode_anomalies,
            "embedded_font": {
                "subtype": "/Type1C",
                "bytes": len(cff_bytes),
                "charset": charset,
            },
            "math_glyph_evidence": _math_glyph_evidence(charset),
            "math_unicode_evidence": _math_unicode_evidence(to_unicode),
        },
        code_bytes=1,
        encoding_names=dict(enumerate(names)),
        source_unicode={},
        to_unicode=to_unicode,
        glyph_ids={name: index for index, name in enumerate(charset)},
    )


def _load_type0_font(resource: str, reference: Any, font: Any) -> LoadedFont:
    require_supported(
        str(font.get("/Encoding")) == "/Identity-H",
        "type0_identity_h_required",
        f"{resource}: seule la CMap Type0 Identity-H est supportée",
    )
    descendants = list(font.get("/DescendantFonts", []))
    require_supported(
        len(descendants) == 1,
        "embedded_cidfonttype2_required",
        f"{resource}: police descendante unique requise",
    )
    descendant = descendants[0].get_object()
    require_supported(
        str(descendant.get("/Subtype")) == "/CIDFontType2",
        "embedded_cidfonttype2_required",
        f"{resource}: seule une CIDFontType2 est supportée",
    )
    cid_to_gid = descendant.get("/CIDToGIDMap")
    descriptor = descendant.get("/FontDescriptor")
    require_supported(
        descriptor is not None,
        "embedded_cidfonttype2_required",
        f"{resource}: FontDescriptor absent",
    )
    font_file = descriptor.get_object().get("/FontFile2")
    require_supported(
        font_file is not None,
        "embedded_cidfonttype2_required",
        f"{resource}: FontFile2 embarqué absent",
    )
    font_bytes = font_file.get_object().get_data()
    with TTFont(BytesIO(font_bytes)) as true_type:
        glyph_order = true_type.getGlyphOrder()
    to_unicode = parse_to_unicode(font)
    require_supported(
        bool(to_unicode),
        "type0_to_unicode_required",
        f"{resource}: ToUnicode requis pour une police Type0",
    )
    require_supported(
        cid_to_gid is None or str(cid_to_gid) == "/Identity",
        "cid_to_gid_stream_not_qualified",
        f"{resource}: flux CIDToGIDMap sans gain mathématique qualifié",
    )
    code_to_gid = {code: code for code in to_unicode}
    require_supported(
        len(code_to_gid) == len(to_unicode)
        and all(
            0 < gid < len(glyph_order) and glyph_order[gid] != ".notdef"
            for gid in code_to_gid.values()
        ),
        "cid_to_gid_map_required",
        f"{resource}: correspondance CID/GID incomplète ou sans glyphe",
    )
    base_font = str(font.get("/BaseFont"))
    return LoadedFont(
        public={
            "resource": resource,
            "xref": int(reference.idnum),
            "base_font": base_font,
            "trace_font": _trace_font(base_font),
            "subtype": "/Type0",
            "encoding": {"base": "/Identity-H", "code_bytes": 2},
            "to_unicode": {
                f"0x{code:04x}": value for code, value in to_unicode.items()
            },
            "embedded_font": {
                "subtype": "/CIDFontType2",
                "bytes": len(font_bytes),
                "glyphs": len(glyph_order),
                "cid_to_gid": "/Identity",
            },
            "math_glyph_evidence": _math_glyph_evidence(glyph_order),
            "math_unicode_evidence": _math_unicode_evidence(to_unicode),
        },
        code_bytes=2,
        encoding_names={code: glyph_order[gid] for code, gid in code_to_gid.items()},
        source_unicode=to_unicode,
        to_unicode=to_unicode,
        glyph_ids={glyph_order[gid]: gid for gid in code_to_gid.values()},
    )


def _load_true_type_font(resource: str, reference: Any, font: Any) -> LoadedFont:
    descriptor = font.get("/FontDescriptor")
    require_supported(
        descriptor is not None,
        "embedded_truetype_font_required",
        f"{resource}: FontDescriptor absent",
    )
    font_file = descriptor.get_object().get("/FontFile2")
    require_supported(
        font_file is not None,
        "embedded_truetype_font_required",
        f"{resource}: FontFile2 embarqué absent",
    )
    font_bytes = font_file.get_object().get_data()
    to_unicode_anomalies: list[dict[str, Any]] = []
    to_unicode = parse_to_unicode(
        font,
        allow_simple_codespace_mismatch=True,
        anomalies=to_unicode_anomalies,
    )
    require_supported(
        bool(to_unicode),
        "truetype_to_unicode_required",
        f"{resource}: ToUnicode requis pour une police TrueType simple",
    )
    with TTFont(BytesIO(font_bytes)) as true_type:
        glyph_order = true_type.getGlyphOrder()
        unicode_cmap = true_type.getBestCmap() or {}
        encoded_cmaps = [table.cmap for table in true_type["cmap"].tables]

    code_to_gid = {}
    for code, unicode_value in to_unicode.items():
        encoded_names = {cmap[code] for cmap in encoded_cmaps if code in cmap}
        require_supported(
            len(encoded_names) <= 1,
            "truetype_code_to_gid_ambiguous",
            f"{resource}: plusieurs GID pour le code 0x{code:02x}",
        )
        glyph_name = next(iter(encoded_names), None)
        if glyph_name is None and len(unicode_value) == 1:
            glyph_name = unicode_cmap.get(ord(unicode_value))
        if glyph_name in glyph_order:
            code_to_gid[code] = glyph_order.index(glyph_name)

    require_supported(
        all(code in code_to_gid for code in to_unicode),
        "truetype_code_to_gid_required",
        f"{resource}: correspondance code/GID incomplète",
    )
    base_font = str(font.get("/BaseFont"))
    encoding_names = {code: glyph_order[gid] for code, gid in code_to_gid.items()}
    return LoadedFont(
        public={
            "resource": resource,
            "xref": int(reference.idnum),
            "base_font": base_font,
            "trace_font": _trace_font(base_font),
            "subtype": "/TrueType",
            "encoding": {"base": str(font.get("/Encoding", "/BuiltIn"))},
            "to_unicode": {
                f"0x{code:02x}": value for code, value in to_unicode.items()
            },
            "to_unicode_anomalies": to_unicode_anomalies,
            "embedded_font": {
                "subtype": "/TrueType",
                "bytes": len(font_bytes),
                "glyphs": len(glyph_order),
            },
            "math_glyph_evidence": _math_glyph_evidence(glyph_order),
            "math_unicode_evidence": _math_unicode_evidence(to_unicode),
        },
        code_bytes=1,
        encoding_names=encoding_names,
        source_unicode=to_unicode,
        to_unicode=to_unicode,
        glyph_ids={glyph_order[gid]: gid for gid in code_to_gid.values()},
    )


def load_font(resource: str, reference: Any) -> LoadedFont:
    font = reference.get_object()
    subtype = str(font.get("/Subtype"))
    if subtype == "/Type1":
        return _load_type1_font(resource, reference, font)
    if subtype == "/Type0":
        return _load_type0_font(resource, reference, font)
    if subtype == "/TrueType":
        return _load_true_type_font(resource, reference, font)
    require_supported(
        False,
        "embedded_font_type_unsupported",
        f"{resource}: type de police non supporté: {subtype}",
    )
    raise AssertionError("unreachable")
