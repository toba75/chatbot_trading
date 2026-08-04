from __future__ import annotations

import unicodedata


MARKERS = {
    "<bold>",
    "</bold>",
    "<sub>",
    "</sub>",
    "<sup>",
    "</sup>",
    "<over>",
    "</over>",
    "<radicand>",
    "</radicand>",
    "<fraction>",
    "</fraction>",
    "<numerator>",
    "</numerator>",
    "<denominator>",
    "</denominator>",
}


def normalize_relation_signature(tokens: list[str]) -> list[str]:
    normalized: list[str] = []
    text: list[str] = []
    for token in tokens:
        if token in MARKERS:
            normalized.extend(unicodedata.normalize("NFC", "".join(text)))
            text = []
            if token == "<bold>" and normalized[-1:] == ["</bold>"]:
                normalized.pop()
            else:
                normalized.append(token)
        else:
            text.append(token)
    normalized.extend(unicodedata.normalize("NFC", "".join(text)))
    return normalized
