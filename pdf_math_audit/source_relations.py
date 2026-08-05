from __future__ import annotations

import unicodedata
from statistics import median
from typing import Any

import fitz

from pdf_math_audit.geometry import (
    rule_covers_horizontal_span,
    rule_fits_horizontal_span,
)
from pdf_math_audit.math_unicode import is_mathematical_bold, normalize_bold_variants
from pdf_math_audit.relation_signature import normalize_relation_signature


def _is_bold(glyph: dict[str, Any]) -> bool:
    return bool(glyph["rawdict"]["span_flags"] & fitz.TEXT_FONT_BOLD) or any(
        is_mathematical_bold(character) for character in glyph["unicode"]
    )


def _logical_token(glyph: dict[str, Any]) -> str:
    return normalize_bold_variants(glyph["unicode"])


def _signature_token(glyph: dict[str, Any]) -> list[str]:
    token = _logical_token(glyph)
    if _is_bold(glyph):
        return ["<bold>", token, "</bold>"]
    return [token]


def _baseline_cluster(
    glyphs: list[dict[str, Any]], largest_size: float
) -> list[dict[str, Any]] | None:
    clusters: list[list[dict[str, Any]]] = []
    tolerance = largest_size * 0.10
    baseline_sized = [
        glyph for glyph in glyphs if glyph["rendered_size"] >= largest_size * 0.8
    ]
    for glyph in sorted(baseline_sized, key=lambda item: item["rendered_origin_y"]):
        if (
            not clusters
            or abs(
                glyph["rendered_origin_y"]
                - median(item["rendered_origin_y"] for item in clusters[-1])
            )
            > tolerance
        ):
            clusters.append([glyph])
        else:
            clusters[-1].append(glyph)
    winners = [
        cluster
        for cluster in clusters
        if any(item["rendered_size"] == largest_size for item in cluster)
    ]
    return winners[0] if len(winners) == 1 else None


def _canonical_linear(
    glyphs: list[dict[str, Any]],
) -> tuple[list[str] | None, list[str] | None, list[dict[str, Any]], str | None]:
    glyphs = [glyph for glyph in glyphs if not glyph["unicode"].isspace()]
    if not glyphs:
        return [], [], [], None
    required = {"rendered_origin_x", "rendered_origin_y", "rendered_size"}
    if any(
        not required.issubset(glyph) or "span_flags" not in glyph.get("rawdict", {})
        for glyph in glyphs
    ):
        return None, None, [], "source_relation_geometry_missing"

    largest_size = max(glyph["rendered_size"] for glyph in glyphs)
    baseline = _baseline_cluster(glyphs, largest_size)
    if baseline is None:
        return None, None, [], "source_baseline_ambiguous"

    baseline_y = median(glyph["rendered_origin_y"] for glyph in baseline)
    baseline_by_x = sorted(baseline, key=lambda glyph: glyph["rendered_origin_x"])
    tolerance = largest_size * 0.10
    attachments: dict[tuple[int, str], list[dict[str, Any]]] = {}
    over_attachments: dict[int, list[dict[str, Any]]] = {}
    for operator in baseline_by_x:
        if operator["unicode"] not in {"=", "≈", "≝"}:
            continue
        operator_bbox = operator["bbox"]
        operator_width = operator_bbox[2] - operator_bbox[0]
        annotations = [
            glyph
            for glyph in glyphs
            if glyph not in baseline
            and glyph["rawdict"]["block"] == operator["rawdict"]["block"]
            and glyph["rendered_origin_y"] < baseline_y - tolerance
            and baseline_y - glyph["rendered_origin_y"] <= operator["rendered_size"]
            and operator_bbox[0] - operator_width * 0.25
            <= (glyph["bbox"][0] + glyph["bbox"][2]) / 2
            <= operator_bbox[2] + operator_width * 0.25
        ]
        if annotations:
            over_attachments[operator["sequence_index"]] = annotations
    over_sequences = {
        glyph["sequence_index"]
        for annotations in over_attachments.values()
        for glyph in annotations
    }

    for glyph in glyphs:
        if glyph in baseline or glyph["sequence_index"] in over_sequences:
            continue
        vertical_delta = glyph["rendered_origin_y"] - baseline_y
        reduced_script = (
            glyph["rendered_size"] < largest_size * 0.8
            and abs(vertical_delta) >= largest_size * 0.05
        )
        if not (
            (reduced_script or abs(vertical_delta) >= tolerance)
            and abs(vertical_delta) <= largest_size * 1.5
        ):
            return None, None, [], "source_script_position_ambiguous"
        role = "subscript" if vertical_delta > 0 else "superscript"
        anchors = [
            candidate
            for candidate in baseline_by_x
            if candidate["rendered_origin_x"] <= glyph["rendered_origin_x"]
            and glyph["bbox"][0] - candidate["bbox"][2] <= largest_size * 2.0
        ]
        if not anchors:
            return None, None, [], "source_script_anchor_missing"
        anchor = anchors[-1]
        attachments.setdefault((anchor["sequence_index"], role), []).append(glyph)

    canonical = []
    signature = []
    relations: list[dict[str, Any]] = []
    for glyph in baseline_by_x:
        token = _logical_token(glyph)
        canonical.append(token)
        signature.extend(_signature_token(glyph))
        overscript = sorted(
            over_attachments.get(glyph["sequence_index"], []),
            key=lambda item: item["rendered_origin_x"],
        )
        if overscript:
            over_tokens, over_signature, over_relations, reason = _canonical_linear(
                overscript
            )
            if reason is not None or over_tokens is None or over_signature is None:
                return None, None, [], reason
            canonical.extend(over_tokens)
            signature.extend(["<over>", *over_signature, "</over>"])
            relations.extend(
                {
                    "sequence_index": item["sequence_index"],
                    "token": item["unicode"],
                    "role": "overscript",
                    "anchor_sequence_index": glyph["sequence_index"],
                }
                for item in overscript
            )
            relations.extend(over_relations)
        for role in ("subscript", "superscript"):
            scripts = sorted(
                attachments.get((glyph["sequence_index"], role), []),
                key=lambda item: item["rendered_origin_x"],
            )
            if not scripts:
                continue
            script_tokens, script_signature, nested_relations, reason = (
                _canonical_linear(scripts)
            )
            if reason is not None or script_tokens is None or script_signature is None:
                return None, None, [], reason
            script_baseline = _baseline_cluster(
                scripts, max(script["rendered_size"] for script in scripts)
            )
            if script_baseline is None:
                return None, None, [], "source_baseline_ambiguous"
            relations.extend(
                {
                    "sequence_index": script["sequence_index"],
                    "token": script["unicode"],
                    "role": role,
                    "anchor_sequence_index": glyph["sequence_index"],
                }
                for script in script_baseline
            )
            relations.extend(nested_relations)
            canonical.extend(script_tokens)
            marker = "sub" if role == "subscript" else "sup"
            signature.extend([f"<{marker}>", *script_signature, f"</{marker}>"])
    canonical = list(unicodedata.normalize("NFC", "".join(canonical)))
    return (
        canonical,
        normalize_relation_signature(signature),
        sorted(relations, key=lambda relation: relation["sequence_index"]),
        None,
    )


def _stacked_radical_sum(
    glyphs: list[dict[str, Any]],
    radical: dict[str, Any],
    summation: dict[str, Any],
    rule: dict[str, float | int] | None,
) -> tuple[list[str] | None, list[str] | None, list[dict[str, Any]], str | None]:
    if rule is None:
        return None, None, [], "source_radical_rule_missing"
    content = [glyph for glyph in glyphs if glyph not in (radical, summation)]
    if not content or radical["rendered_origin_x"] >= summation["rendered_origin_x"]:
        return None, None, [], "source_stacked_operator_ambiguous"

    endpoint = float(rule["x1"])
    endpoint_tolerance = float(rule["width"]) + 0.5
    if any(
        glyph["bbox"][0] < endpoint < glyph["bbox"][2] - endpoint_tolerance
        for glyph in content
    ):
        return None, None, [], "source_radical_scope_ambiguous"
    radicand = [glyph for glyph in content if glyph["bbox"][0] < endpoint]
    trailing = [glyph for glyph in content if glyph not in radicand]
    if not radicand:
        return None, None, [], "source_radical_scope_ambiguous"

    largest_size = max(glyph["rendered_size"] for glyph in radicand)
    baseline = _baseline_cluster(radicand, largest_size)
    if baseline is None:
        return None, None, [], "source_baseline_ambiguous"
    baseline_y = median(glyph["rendered_origin_y"] for glyph in baseline)
    first_content_x = min(glyph["rendered_origin_x"] for glyph in baseline)
    bounds = [
        glyph for glyph in radicand if glyph["rendered_origin_x"] < first_content_x
    ]
    expression = [glyph for glyph in radicand if glyph not in bounds]
    rule_y = float(rule["y"])
    rule_tolerance = max(0.5, float(rule["width"]))
    expression_top = min(glyph["bbox"][1] for glyph in expression)
    if (
        abs(rule_y - radical["rendered_origin_y"]) > rule_tolerance
        or not 0 <= expression_top - rule_y <= largest_size * 0.6
    ):
        return None, None, [], "source_radical_rule_position_invalid"
    tolerance = largest_size * 0.10
    lower = sorted(
        (
            glyph
            for glyph in bounds
            if glyph["rendered_origin_y"] > baseline_y + tolerance
        ),
        key=lambda glyph: glyph["rendered_origin_x"],
    )
    upper = sorted(
        (
            glyph
            for glyph in bounds
            if glyph["rendered_origin_y"] < baseline_y - tolerance
        ),
        key=lambda glyph: glyph["rendered_origin_x"],
    )
    if len(lower) + len(upper) != len(bounds) or not lower or not upper:
        return None, None, [], "source_stacked_operator_ambiguous"

    expression_tokens, expression_signature, relations, reason = _canonical_linear(
        expression
    )
    if reason is not None or expression_tokens is None or expression_signature is None:
        return None, None, [], reason
    trailing_tokens, trailing_signature, trailing_relations, trailing_reason = (
        _canonical_linear(trailing)
    )
    if (
        trailing_reason is not None
        or trailing_tokens is None
        or trailing_signature is None
    ):
        return None, None, [], trailing_reason

    lower_tokens = [_logical_token(glyph) for glyph in lower]
    upper_tokens = [_logical_token(glyph) for glyph in upper]
    lower_signature = [token for glyph in lower for token in _signature_token(glyph)]
    upper_signature = [token for glyph in upper for token in _signature_token(glyph)]
    bound_relations = [
        {
            "sequence_index": glyph["sequence_index"],
            "token": glyph["unicode"],
            "role": role,
            "anchor_sequence_index": summation["sequence_index"],
        }
        for role, scripts in (("subscript", lower), ("superscript", upper))
        for glyph in scripts
    ]
    canonical = [
        _logical_token(radical),
        _logical_token(summation),
        *lower_tokens,
        *upper_tokens,
        *expression_tokens,
        *trailing_tokens,
    ]
    signature = [
        *_signature_token(radical),
        "<radicand>",
        *_signature_token(summation),
        "<sub>",
        *lower_signature,
        "</sub>",
        "<sup>",
        *upper_signature,
        "</sup>",
        *expression_signature,
        "</radicand>",
        *trailing_signature,
    ]
    return (
        list(unicodedata.normalize("NFC", "".join(canonical))),
        normalize_relation_signature(signature),
        [*bound_relations, *relations, *trailing_relations],
        None,
    )


def _stacked_fraction(
    glyphs: list[dict[str, Any]], rule: dict[str, float | int]
) -> tuple[list[str] | None, list[str] | None, list[dict[str, Any]], str | None]:
    y = float(rule["y"])
    vertical_tolerance = max(0.5, float(rule["width"]))
    horizontal_tolerance = max(0.5, float(rule["width"]))
    within_rule = [
        glyph
        for glyph in glyphs
        if float(rule["x0"]) - horizontal_tolerance
        <= (glyph["bbox"][0] + glyph["bbox"][2]) / 2
        <= float(rule["x1"]) + horizontal_tolerance
    ]
    numerator = [
        glyph for glyph in within_rule if glyph["bbox"][3] <= y + vertical_tolerance
    ]
    denominator = [
        glyph for glyph in within_rule if glyph["bbox"][1] >= y - vertical_tolerance
    ]
    if (
        not numerator
        or not denominator
        or len(numerator) + len(denominator) != len(within_rule)
    ):
        return None, None, [], "source_fraction_rule_ambiguous"
    operands = [*numerator, *denominator]
    if not rule_covers_horizontal_span(rule, operands):
        return None, None, [], "source_fraction_rule_too_short"
    if not rule_fits_horizontal_span(rule, operands):
        return None, None, [], "source_fraction_rule_too_long"
    numerator_tokens, numerator_signature, numerator_relations, numerator_reason = (
        _canonical_expression(numerator)
    )
    (
        denominator_tokens,
        denominator_signature,
        denominator_relations,
        denominator_reason,
    ) = _canonical_expression(denominator)
    reason = numerator_reason or denominator_reason
    if (
        reason is not None
        or numerator_tokens is None
        or numerator_signature is None
        or denominator_tokens is None
        or denominator_signature is None
    ):
        return None, None, [], reason
    fraction_signature = [
        "<fraction>",
        "<numerator>",
        *numerator_signature,
        "</numerator>",
        "<denominator>",
        *denominator_signature,
        "</denominator>",
        "</fraction>",
    ]
    remaining = [glyph for glyph in glyphs if glyph not in operands]
    left = [
        glyph
        for glyph in remaining
        if (glyph["bbox"][0] + glyph["bbox"][2]) / 2 < float(rule["x0"])
    ]
    right = [glyph for glyph in remaining if glyph not in left]
    if any(
        (glyph["bbox"][0] + glyph["bbox"][2]) / 2 <= float(rule["x1"])
        for glyph in right
    ):
        return None, None, [], "source_fraction_scope_ambiguous"
    left_tokens, left_signature, left_relations, left_reason = _canonical_expression(
        left
    )
    right_tokens, right_signature, right_relations, right_reason = (
        _canonical_expression(right)
    )
    reason = left_reason or right_reason
    if (
        reason is not None
        or left_tokens is None
        or left_signature is None
        or right_tokens is None
        or right_signature is None
    ):
        return None, None, [], reason
    return (
        [*left_tokens, *numerator_tokens, *denominator_tokens, *right_tokens],
        normalize_relation_signature(
            [*left_signature, *fraction_signature, *right_signature]
        ),
        [
            *left_relations,
            *numerator_relations,
            *denominator_relations,
            *right_relations,
        ],
        None,
    )


_STACKED_OPERATOR_NAMES = {
    "productdisplay",
    "producttext",
    "summationdisplay",
    "summationtext",
}


def _baseline_groups(
    glyphs: list[dict[str, Any]], tolerance: float
) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    for glyph in sorted(glyphs, key=lambda item: item["rendered_origin_y"]):
        matching = next(
            (
                group
                for group in groups
                if abs(
                    glyph["rendered_origin_y"]
                    - median(item["rendered_origin_y"] for item in group)
                )
                <= tolerance
            ),
            None,
        )
        if matching is None:
            groups.append([glyph])
        else:
            matching.append(glyph)
    return groups


def _stacked_operator(
    glyphs: list[dict[str, Any]], operator: dict[str, Any]
) -> tuple[list[str] | None, list[str] | None, list[dict[str, Any]], str | None]:
    others = [glyph for glyph in glyphs if glyph is not operator]
    operator_bbox = operator["bbox"]
    operator_center_x = (operator_bbox[0] + operator_bbox[2]) / 2
    tolerance = max(0.5, operator["rendered_size"] * 0.12)
    groups = _baseline_groups(others, tolerance)
    largest_other_size = max(
        (glyph["rendered_size"] for glyph in others), default=operator["rendered_size"]
    )
    expression_baseline = _baseline_cluster(others, largest_other_size)
    expression_baseline_y = (
        median(glyph["rendered_origin_y"] for glyph in expression_baseline)
        if expression_baseline is not None
        else None
    )
    first_operand_x = min(
        (
            glyph["bbox"][0]
            for glyph in expression_baseline or []
            if glyph["bbox"][0] >= operator_bbox[2]
        ),
        default=None,
    )

    left: list[dict[str, Any]] = []
    lower: list[dict[str, Any]] = []
    upper: list[dict[str, Any]] = []
    right: list[dict[str, Any]] = []
    for group in groups:
        group_bbox = [
            min(glyph["bbox"][0] for glyph in group),
            min(glyph["bbox"][1] for glyph in group),
            max(glyph["bbox"][2] for glyph in group),
            max(glyph["bbox"][3] for glyph in group),
        ]
        horizontal_gap = max(
            float(operator_bbox[0]) - group_bbox[2],
            group_bbox[0] - float(operator_bbox[2]),
            0.0,
        )
        group_y = median(glyph["rendered_origin_y"] for glyph in group)
        is_near_small_group = (
            expression_baseline_y is not None
            and all(
                glyph["rendered_size"] < largest_other_size for glyph in group
            )
            and horizontal_gap <= operator["rendered_size"] * 1.5
            and (first_operand_x is None or group_bbox[0] < first_operand_x)
        )
        if is_near_small_group and group_y > expression_baseline_y + tolerance:
            lower.extend(group)
        elif is_near_small_group and group_y < expression_baseline_y - tolerance:
            upper.extend(group)
        elif (
            group_bbox[0] <= operator_center_x <= group_bbox[2]
            and group_bbox[1] >= operator_bbox[3] - tolerance
        ):
            lower.extend(group)
        elif (
            group_bbox[0] <= operator_center_x <= group_bbox[2]
            and group_bbox[3] <= operator_bbox[1] + tolerance
        ):
            upper.extend(group)
        elif group_bbox[2] < operator_center_x:
            left.extend(group)
        elif group_bbox[0] > operator_center_x:
            right.extend(group)
        else:
            for glyph in group:
                if glyph["bbox"][2] <= operator_center_x:
                    left.append(glyph)
                elif glyph["bbox"][0] >= operator_center_x:
                    right.append(glyph)
                else:
                    return None, None, [], "source_stacked_operator_ambiguous"

    if not lower and not upper and not right:
        return None, None, [], "source_stacked_operator_bounds_missing"

    parts = {}
    for name, part in (
        ("left", left),
        ("lower", lower),
        ("upper", upper),
        ("right", right),
    ):
        tokens, signature, relations, reason = _canonical_linear(part)
        if reason is not None or tokens is None or signature is None:
            return None, None, [], reason
        parts[name] = (tokens, signature, relations)

    left_tokens, left_signature, left_relations = parts["left"]
    lower_tokens, lower_signature, lower_relations = parts["lower"]
    upper_tokens, upper_signature, upper_relations = parts["upper"]
    right_tokens, right_signature, right_relations = parts["right"]
    operator_sequence = operator["sequence_index"]
    bound_relations = [
        {
            "sequence_index": glyph["sequence_index"],
            "token": glyph["unicode"],
            "role": role,
            "anchor_sequence_index": operator_sequence,
        }
        for role, bound in (("subscript", lower), ("superscript", upper))
        for glyph in bound
    ]
    signature = [*left_signature, *_signature_token(operator)]
    if lower:
        signature.extend(["<sub>", *lower_signature, "</sub>"])
    if upper:
        signature.extend(["<sup>", *upper_signature, "</sup>"])
    signature.extend(right_signature)
    canonical = [
        *left_tokens,
        _logical_token(operator),
        *lower_tokens,
        *upper_tokens,
        *right_tokens,
    ]
    return (
        list(unicodedata.normalize("NFC", "".join(canonical))),
        normalize_relation_signature(signature),
        [
            *left_relations,
            *bound_relations,
            *lower_relations,
            *upper_relations,
            *right_relations,
        ],
        None,
    )


def _canonical_expression(
    glyphs: list[dict[str, Any]],
) -> tuple[list[str] | None, list[str] | None, list[dict[str, Any]], str | None]:
    operators = [
        glyph for glyph in glyphs if glyph["glyph_name"] in _STACKED_OPERATOR_NAMES
    ]
    if not operators:
        return _canonical_linear(glyphs)
    if len(operators) != 1:
        return None, None, [], "source_stacked_operator_ambiguous"
    return _stacked_operator(glyphs, operators[0])


def canonical_source_tokens(
    glyphs: list[dict[str, Any]],
    structural_rules: dict[str, dict[str, float | int]] | None = None,
) -> tuple[list[str] | None, list[str] | None, list[dict[str, Any]], str | None]:
    """Place les structures mathématiques prouvées dans l'ordre logique MathML."""
    structural_rules = structural_rules or {}
    if fraction := structural_rules.get("fraction"):
        return _stacked_fraction(glyphs, fraction)
    radical = [glyph for glyph in glyphs if glyph["glyph_name"] == "radicalBig"]
    summation = [
        glyph
        for glyph in glyphs
        if glyph["glyph_name"] in {"summationdisplay", "summationtext"}
    ]
    if len(radical) == 1 and len(summation) == 1:
        return _stacked_radical_sum(
            glyphs, radical[0], summation[0], structural_rules.get("radical")
        )
    return _canonical_expression(glyphs)
