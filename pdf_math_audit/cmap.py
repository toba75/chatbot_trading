from __future__ import annotations

import re
from typing import Any

from pypdf._cmap import get_encoding

from pdf_math_audit.limitations import require_supported


HEX_STRING = re.compile(rb"(?<!<)<([^<>]*)>(?!>)")
BLOCKS = {
    "bfchar": (
        re.compile(rb"(\d+)\s+beginbfchar\b(.*?)\bendbfchar\b", re.DOTALL),
        2,
        (0,),
    ),
    "bfrange": (
        re.compile(rb"(\d+)\s+beginbfrange\b(.*?)\bendbfrange\b", re.DOTALL),
        3,
        (0, 1),
    ),
    "codespacerange": (
        re.compile(
            rb"(\d+)\s+begincodespacerange\b(.*?)\bendcodespacerange\b",
            re.DOTALL,
        ),
        2,
        (0, 1),
    ),
}


def _entries(name: str, cmap: bytes) -> list[list[bytes]]:
    pattern, arity, _source_offsets = BLOCKS[name]
    matches = list(pattern.finditer(cmap))
    require_supported(
        len(matches)
        == cmap.count(f"begin{name}".encode())
        == cmap.count(f"end{name}".encode()),
        "to_unicode_cmap_invalid",
        f"Bloc ToUnicode {name} incomplet",
    )
    entries = []
    for match in matches:
        body = match.group(2)
        require_supported(
            b"[" not in body and b"]" not in body,
            "to_unicode_cmap_unsupported",
            "Les destinations ToUnicode en tableau ne sont pas supportées",
        )
        tokens = HEX_STRING.findall(body)
        require_supported(
            len(tokens) == int(match.group(1)) * arity
            and not HEX_STRING.sub(b"", body).strip(),
            "to_unicode_cmap_invalid",
            f"Nombre d'opérandes ToUnicode {name} incohérent",
        )
        entries.extend(
            tokens[index : index + arity] for index in range(0, len(tokens), arity)
        )
    return entries


def _is_valid_utf16be(token: bytes) -> bool:
    try:
        value = bytes.fromhex(token.decode("ascii")).decode("utf-16-be")
    except UnicodeDecodeError:
        return False
    return bool(value)


def _validate_cmap(cmap: bytes) -> set[int]:
    operators = set(re.findall(rb"\bbegin([a-z]+(?:char|range))\b", cmap))
    require_supported(
        b"usecmap" not in cmap and operators <= {name.encode() for name in BLOCKS},
        "to_unicode_cmap_unsupported",
        "Construction ToUnicode non supportée",
    )
    mapped_codes: set[int] = set()
    code_spaces: list[tuple[int, int]] = []
    for name, (_pattern, _arity, source_offsets) in BLOCKS.items():
        for entry in _entries(name, cmap):
            sources = [entry[offset] for offset in source_offsets]
            require_supported(
                all(len(source) == 2 for source in sources),
                "to_unicode_cmap_unsupported",
                "Seules les sources ToUnicode monooctet sont supportées",
            )
            bounds = [int(source, 16) for source in sources]
            require_supported(
                len(bounds) == 1 or bounds[0] <= bounds[1],
                "to_unicode_cmap_invalid",
                f"Plage ToUnicode {name} décroissante",
            )
            if name == "codespacerange":
                code_spaces.append((bounds[0], bounds[1]))
                continue
            require_supported(
                _is_valid_utf16be(entry[-1]),
                "to_unicode_cmap_invalid",
                "Destination ToUnicode non UTF-16BE",
            )
            codes = (
                {bounds[0]}
                if len(bounds) == 1
                else set(range(bounds[0], bounds[1] + 1))
            )
            require_supported(
                mapped_codes.isdisjoint(codes),
                "to_unicode_cmap_invalid",
                "Code source ToUnicode défini plusieurs fois",
            )
            mapped_codes.update(codes)
    require_supported(
        not code_spaces
        or all(
            any(start <= code <= end for start, end in code_spaces)
            for code in mapped_codes
        ),
        "to_unicode_cmap_invalid",
        "Code source ToUnicode hors codespace",
    )
    return mapped_codes


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
    declared_codes = _validate_cmap(cmap)
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
        set(mappings) == declared_codes,
        "to_unicode_cmap_invalid",
        "Mappings ToUnicode décodés incomplets",
    )
    require_supported(
        len(mappings) == len(character_map) - 1,
        "to_unicode_cmap_unsupported",
        "Entrée ToUnicode non supportée",
    )
    return mappings
