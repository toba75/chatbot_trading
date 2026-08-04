from __future__ import annotations


_STRUCTURAL_WRAPPERS = {
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
    "text",
    "underline",
    "vec",
}


def _expanded_command(text: str, start: int, end: int) -> tuple[int, int]:
    for position in {start, end - 1}:
        if 0 <= position < len(text) and text[position] == "\\":
            command_end = position + 1
            while command_end < len(text) and text[command_end].isalpha():
                command_end += 1
            end = max(end, command_end)
    balance = text[start:end].count("{") - text[start:end].count("}")
    while balance > 0 and end < len(text):
        if text[end] == "{":
            balance += 1
        elif text[end] == "}":
            balance -= 1
        end += 1
    return start, end


def _expanded_wrapper(text: str, start: int, end: int) -> tuple[int, int]:
    while start > 0:
        opening = start - 1
        while opening >= 0 and text[opening].isspace():
            opening -= 1
        if opening < 0 or text[opening] != "{":
            break
        command_end = opening
        while command_end > 0 and text[command_end - 1].isspace():
            command_end -= 1
        command_start = command_end
        while command_start > 0 and text[command_start - 1].isalpha():
            command_start -= 1
        if command_start == 0 or text[command_start - 1] != "\\":
            break
        command_start -= 1
        if text[command_start + 1 : command_end] not in _STRUCTURAL_WRAPPERS:
            break

        depth = 1
        closing = opening + 1
        while closing < len(text) and depth:
            if text[closing] == "{":
                depth += 1
            elif text[closing] == "}":
                depth -= 1
            closing += 1
        if depth:
            break
        start, end = command_start, max(end, closing)
    return start, end


def _expanded_delimiters(
    text: str, start: int, end: int, source_text: str
) -> tuple[int, int]:
    if text[:start].count("$") % 2:
        start = text.rfind("$", 0, start)
    if text[start:end].count("$") % 2:
        closing = text.find("$", end)
        if closing >= 0:
            end = closing + 1
    pairs = {"{": "}", "[": "]"}
    if source_text[:1] in pairs:
        before = start - 1
        while before >= 0 and text[before].isspace():
            before -= 1
        if before >= 0 and text[before] == source_text[0]:
            start = before
    if source_text[-1:] in pairs.values():
        after = end
        while after < len(text) and text[after].isspace():
            after += 1
        if after < len(text) and text[after] == source_text[-1]:
            end = after + 1
    return start, end


def _expanded_left_right(text: str, start: int, end: int) -> tuple[int, int]:
    fragment = text[start:end]
    left_count = fragment.count(r"\left")
    right_count = fragment.count(r"\right")
    while right_count > left_count:
        opening = text.rfind(r"\left", 0, start)
        if opening < 0:
            break
        start = opening
        fragment = text[start:end]
        left_count = fragment.count(r"\left")
        right_count = fragment.count(r"\right")
    while left_count > right_count:
        closing = text.find(r"\right", end)
        if closing < 0:
            break
        delimiter = closing + len(r"\right")
        while delimiter < len(text) and text[delimiter].isspace():
            delimiter += 1
        if delimiter < len(text) and text[delimiter] == "\\":
            delimiter += 1
            while delimiter < len(text) and text[delimiter].isalpha():
                delimiter += 1
        else:
            delimiter = min(delimiter + 1, len(text))
        end = delimiter
        fragment = text[start:end]
        left_count = fragment.count(r"\left")
        right_count = fragment.count(r"\right")
    return start, end


def _expanded_trailing_scripts(text: str, end: int) -> int:
    while True:
        position = end
        while position < len(text) and text[position].isspace():
            position += 1
        if position >= len(text) or text[position] not in "_^":
            return end
        position += 1
        while position < len(text) and text[position].isspace():
            position += 1
        if position >= len(text):
            return end
        if text[position] == "{":
            depth = 1
            position += 1
            while position < len(text) and depth:
                if text[position] == "{":
                    depth += 1
                elif text[position] == "}":
                    depth -= 1
                position += 1
            if depth:
                return end
        elif text[position] == "\\":
            position += 1
            while position < len(text) and text[position].isalpha():
                position += 1
        else:
            position += 1
        end = position


def expanded_latex_locus(
    text: str, start: int, end: int, source_text: str
) -> tuple[int, int]:
    start, end = _expanded_command(text, start, end)
    start, end = _expanded_wrapper(text, start, end)
    start, end = _expanded_left_right(text, start, end)
    end = _expanded_trailing_scripts(text, end)
    return _expanded_delimiters(text, start, end, source_text)
