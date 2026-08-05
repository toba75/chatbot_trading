from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import pdf_inspector


TARGET_KINDS = {"formula_insertion", "formula_replacement"}


def read_bytes(path: Path) -> bytes:
    content = path.read_bytes()
    return gzip.decompress(content) if path.suffix == ".gz" else content


def load_json(path: Path) -> dict:
    return json.loads(read_bytes(path))


def sha256(path: Path) -> str:
    return hashlib.sha256(read_bytes(path)).hexdigest()


def region_index(value: object) -> dict[str, dict]:
    regions: dict[str, dict] = {}
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            region_id = current.get("region_id")
            if region_id and "bbox" in current:
                if region_id in regions and regions[region_id] != current:
                    raise ValueError(f"Région dupliquée avec un contenu différent: {region_id}")
                regions[region_id] = current
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return regions


def normalized(text: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFC", text)
        if not character.isspace()
    )


def expand(bbox: list[float], padding: float, page_box: list[float]) -> list[float]:
    x0, y0, x1, y1 = bbox
    px0, py0, px1, py1 = page_box
    return [max(px0, x0 - padding), max(py0, y0 - padding), min(px1, x1 + padding), min(py1, y1 + padding)]


def overlaps(left: list[float], right: list[float]) -> bool:
    return left[0] < right[2] and right[0] < left[2] and left[1] < right[3] and right[1] < left[3]


def item_bbox(item, page_height: float) -> list[float]:
    return [item.x, page_height - item.y - item.height, item.x + item.width, page_height - item.y]


def serialize_item(item, bbox: list[float]) -> dict:
    return {
        "text": item.text,
        "bbox": bbox,
        "font": item.font,
        "font_size": item.font_size,
        "item_type": item.item_type,
    }


def extract_region_texts(pdf: Path, targets: list[dict], bbox_key: str) -> dict[str, dict]:
    grouped: dict[int, list[dict]] = defaultdict(list)
    for target in targets:
        grouped[target["page"] - 1].append(target)

    requests = [(page, [target[bbox_key] for target in page_targets]) for page, page_targets in grouped.items()]
    responses = pdf_inspector.extract_text_in_regions(str(pdf), requests)
    output: dict[str, dict] = {}
    if len(responses) != len(grouped):
        raise ValueError("Nombre de pages inattendu dans la réponse régionale")
    for response in responses:
        page_targets = grouped.get(response.page)
        if page_targets is None:
            raise ValueError(f"Page inattendue dans la réponse régionale: {response.page + 1}")
        if len(response.regions) != len(page_targets):
            raise ValueError(f"Nombre de régions inattendu pour la page {response.page + 1}")
        for target, region in zip(page_targets, response.regions, strict=True):
            output[target["target_id"]] = {"text": region.text, "needs_ocr": region.needs_ocr}
    return output


def summarize(records: list[dict]) -> dict:
    summary: dict[str, object] = {"targets": len(records), "by_kind": dict(Counter(r["kind"] for r in records))}
    for name, predicate in {
        "exact_text_nonempty": lambda r: bool(r["exact_region"]["text"].strip()),
        "needs_ocr_true": lambda r: r["exact_region"]["needs_ocr"],
        "exact_contains_source_glyph_text": lambda r: r["contains_source_glyph_text"],
        "replacement_character_present": lambda r: "�" in r["exact_region"]["text"],
        "replacement_character_but_needs_ocr_false": lambda r: "�" in r["exact_region"]["text"] and not r["exact_region"]["needs_ocr"],
        "position_overlap": lambda r: bool(r["position_overlaps"]),
        "no_position_overlap": lambda r: not r["position_overlaps"],
        "position_neighborhood": lambda r: bool(r["position_neighborhoods"]),
        "no_position_neighborhood": lambda r: not r["position_neighborhoods"],
    }.items():
        summary[name] = sum(predicate(record) for record in records)
    if len(summary["by_kind"]) > 1:
        summary["cohorts"] = {
            kind: summarize([record for record in records if record["kind"] == kind])
            for kind in summary["by_kind"]
        }
    return summary


def run(pdf: Path, report_path: Path, corrections_path: Path, padding: float) -> dict:
    report = load_json(report_path)
    corrections = load_json(corrections_path)
    regions = region_index(report)
    page_boxes = {index + 1: page["box"] for index, page in enumerate(report["pages"])}

    targets = []
    for correction in corrections["records"]:
        if correction.get("kind") not in TARGET_KINDS:
            continue
        region = regions.get(correction["region_id"])
        if region is None:
            raise ValueError(f"Région absente du rapport: {correction['region_id']}")
        bbox = region["bbox"]
        targets.append({
            "target_id": correction["target_id"],
            "kind": correction["kind"],
            "page": correction["page"],
            "region_id": correction["region_id"],
            "docling_ref": correction.get("docling_ref"),
            "bbox": bbox,
            "expanded_bbox": expand(bbox, padding, page_boxes[correction["page"]]),
            "source_glyph_text": region.get("source_glyph_text", ""),
            "source_tokens": region.get("source_tokens"),
        })

    exact = extract_region_texts(pdf, targets, "bbox")
    expanded = extract_region_texts(pdf, targets, "expanded_bbox")
    pages = sorted({target["page"] - 1 for target in targets})
    items_by_page: dict[int, list] = defaultdict(list)
    for item in pdf_inspector.extract_text_with_positions(str(pdf), pages):
        items_by_page[item.page + 1].append(item)

    records = []
    for target in targets:
        height = page_boxes[target["page"]][3] - page_boxes[target["page"]][1]
        position_overlaps = []
        position_neighborhoods = []
        for item in items_by_page[target["page"]]:
            bbox = item_bbox(item, height)
            if overlaps(bbox, target["bbox"]):
                position_overlaps.append(serialize_item(item, bbox))
            if overlaps(bbox, target["expanded_bbox"]):
                position_neighborhoods.append(serialize_item(item, bbox))

        exact_region = exact[target["target_id"]]
        source = normalized(target["source_glyph_text"])
        records.append({
            **target,
            "exact_region": exact_region,
            "expanded_region": expanded[target["target_id"]],
            "contains_source_glyph_text": bool(source) and source in normalized(exact_region["text"]),
            "position_overlaps": position_overlaps,
            "position_neighborhoods": position_neighborhoods,
        })

    return {
        "experiment": "pdf-inspector spatial candidate spike",
        "pdf_inspector_version": "0.2.6",
        "inputs": {
            "pdf_sha256": sha256(pdf),
            "report_sha256": sha256(report_path),
            "corrections_sha256": sha256(corrections_path),
        },
        "padding_points": padding,
        "summary": summarize(records),
        "records": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Évalue pdf-inspector comme source de voisinages spatiaux candidats.")
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--corrections", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--padding", type=float, default=36.0)
    args = parser.parse_args()

    result = run(args.pdf, args.report, args.corrections, args.padding)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
