from __future__ import annotations

import unicodedata


def is_mathematical_bold(character: str) -> bool:
    name = unicodedata.name(character, "")
    return name.startswith("MATHEMATICAL ") and " BOLD " in f" {name} "


def normalize_bold_variants(text: str) -> str:
    return unicodedata.normalize(
        "NFC",
        "".join(
            unicodedata.normalize("NFKC", character)
            if is_mathematical_bold(character)
            else character
            for character in text
        ),
    )
