from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pdfplumber
from PIL import Image, ImageOps, ImageDraw
from pdfminer.encodingdb import EncodingDB, name2unicode
from pypdf import PdfReader
from pypdf._cmap import get_encoding
from pypdf.generic import ContentStream, DictionaryObject, NameObject


@dataclass(frozen=True)
class Fact:
    identifier: str
    page: int
    description: str
    source_needle: str


@dataclass(frozen=True)
class Crop:
    identifier: str
    page: int
    box_points: tuple[float, float, float, float]
    facts: tuple[str, ...]
    output_kind: str


FACTS = (
    Fact("p1_i2", 1, "premier indice i avec exposant (2)", "x(2)i"),
    Fact("p1_k2", 1, "second indice k avec exposant (2)", "x(2)k"),
    Fact("p1_xk", 1, "exemple x_k puis k = 1,...,N", "examplexk,k=1,...,N"),
    Fact("p1_C", 1, "borne C de l’ensemble des classes", "{1,2,...,C}"),
    Fact("p2_hyper_minus", 2, "signe moins de wx-b=0", "wx−b=0"),
    Fact("p2_sign_minus", 2, "signe moins de y=sign(wx-b)", "y=sign(wx−b)"),
    Fact("p2_model_minus", 2, "étoiles et moins de f(x)=sign(w*x-b*)", "f(x)=sign(w∗x−b∗)"),
    Fact(
        "p2_negative_one",
        2,
        "valeur -1 retournée pour une entrée négative",
        "returns+1iftheinputisapositivenumberor−1if",
    ),
    Fact(
        "p2_constraints",
        2,
        "contraintes >=1 et <=-1",
        "wxi−b≥1ifyi=+1,and•wxi−b≤−1ifyi=−1",
    ),
)

CROPS = (
    Crop("p1_feature_indices", 1, (60, 385, 480, 442), ("p1_i2", "p1_k2", "p1_xk", "p1_C"), "markdown"),
    Crop("p2_hyperplane", 2, (225, 142, 315, 176), ("p2_hyper_minus",), "latex"),
    Crop("p2_sign_and_negative", 2, (60, 270, 480, 335), ("p2_sign_minus", "p2_negative_one"), "markdown"),
    Crop("p2_model", 2, (205, 378, 330, 412), ("p2_model_minus",), "latex"),
    Crop("p2_constraints", 2, (75, 538, 225, 582), ("p2_constraints",), "latex"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def font_maps(font: DictionaryObject) -> tuple[dict[int, str], dict[int, str], list[dict[str, object]]]:
    encoding = font.get("/Encoding")
    base_encoding = "StandardEncoding"
    differences: list[object] = []
    if isinstance(encoding, NameObject):
        base_encoding = str(encoding).lstrip("/")
    elif isinstance(encoding, DictionaryObject):
        base_encoding = str(encoding.get("/BaseEncoding", "/StandardEncoding")).lstrip("/")
        differences = list(encoding.get("/Differences", []))

    visual = dict(EncodingDB.get_encoding(base_encoding))
    difference_records: list[dict[str, object]] = []
    code = 0
    for item in differences:
        if isinstance(item, int):
            code = item
            continue
        glyph_name = str(item).lstrip("/")
        try:
            visual_character = name2unicode(glyph_name)
        except (KeyError, ValueError):
            visual_character = ""
        if visual_character:
            visual[code] = visual_character
        difference_records.append(
            {"code": code, "glyph_name": glyph_name, "visual_character": visual_character}
        )
        code += 1

    _, cmap = get_encoding(font)
    declared: dict[int, str] = {}
    for key, value in cmap.items():
        if isinstance(key, int):
            declared[key] = value
        elif isinstance(key, str) and len(key) == 1:
            declared[ord(key)] = value
    return visual, declared, difference_records


def extract_source_manifest(pdf_path: Path) -> dict[str, object]:
    reader = PdfReader(pdf_path)
    pages: list[dict[str, object]] = []
    with pdfplumber.open(pdf_path) as layout_pdf:
        for page_number, (page, layout_page) in enumerate(zip(reader.pages, layout_pdf.pages), 1):
            font_resources = page["/Resources"]["/Font"]
            fonts: dict[str, dict[str, object]] = {}
            decode_maps: dict[str, tuple[dict[int, str], dict[int, str]]] = {}
            base_font_by_resource: dict[str, str] = {}
            for resource_name, reference in font_resources.items():
                font = reference.get_object()
                visual, declared, differences = font_maps(font)
                name = str(resource_name)
                base_font = str(font.get("/BaseFont", ""))
                base_font_by_resource[name] = base_font
                decode_maps[name] = (visual, declared)
                fonts[name] = {
                    "base_font": base_font,
                    "subtype": str(font.get("/Subtype", "")),
                    "encoding": str(font.get("/Encoding", "")),
                    "has_to_unicode": bool(font.get("/ToUnicode")),
                    "differences": differences,
                }

            current_font: str | None = None
            visual_parts: list[str] = []
            declared_parts: list[str] = []
            events: list[dict[str, object]] = []
            conflicts: list[dict[str, object]] = []
            operations = ContentStream(page.get_contents(), reader).operations

            def append_bytes(raw: bytes, operation_index: int) -> None:
                if current_font is None or current_font not in decode_maps:
                    return
                visual_map, declared_map = decode_maps[current_font]
                visual_text = "".join(visual_map.get(code, "�") for code in raw)
                declared_text = "".join(
                    declared_map.get(code, visual_map.get(code, "�")) for code in raw
                )
                visual_parts.append(visual_text)
                declared_parts.append(declared_text)
                event = {
                    "operation_index": operation_index,
                    "font_resource": current_font,
                    "base_font": base_font_by_resource[current_font],
                    "raw_hex": raw.hex(),
                    "visual_text": visual_text,
                    "declared_text": declared_text,
                }
                events.append(event)
                for code in raw:
                    visual_character = visual_map.get(code, "�")
                    declared_character = declared_map.get(code, visual_character)
                    if visual_character != declared_character:
                        conflicts.append(
                            {
                                "operation_index": operation_index,
                                "font_resource": current_font,
                                "base_font": base_font_by_resource[current_font],
                                "code": code,
                                "visual_character": visual_character,
                                "declared_character": declared_character,
                            }
                        )

            for operation_index, (operands, operator) in enumerate(operations):
                if operator == b"Tf":
                    current_font = str(operands[0])
                elif operator in (b"Tj", b"'", b'"'):
                    raw = getattr(operands[-1], "original_bytes", None)
                    if raw is not None:
                        append_bytes(raw, operation_index)
                elif operator == b"TJ":
                    for item in operands[0]:
                        raw = getattr(item, "original_bytes", None)
                        if raw is not None:
                            append_bytes(raw, operation_index)

            critical_layout = []
            for character in layout_page.chars:
                font_name = str(character.get("fontname", ""))
                if "Math" in font_name or character.get("text") in {"≠", "Ø", "Æ", "ú", "k", "C"}:
                    critical_layout.append(
                        {
                            "text": character.get("text"),
                            "font_name": font_name,
                            "x0": character.get("x0"),
                            "top": character.get("top"),
                            "x1": character.get("x1"),
                            "bottom": character.get("bottom"),
                            "size": character.get("size"),
                        }
                    )

            unique_conflicts = list({json.dumps(item, sort_keys=True): item for item in conflicts}.values())
            pages.append(
                {
                    "page": page_number,
                    "fonts": fonts,
                    "visual_stream": "".join(visual_parts),
                    "declared_stream": "".join(declared_parts),
                    "events": events,
                    "encoding_conflicts": unique_conflicts,
                    "critical_layout_characters": critical_layout,
                }
            )
    return {"pdf": str(pdf_path), "sha256": sha256(pdf_path), "pages": pages}


def normalize_candidate(text: str) -> str:
    normalized = text.replace("−", "-").replace("–", "-").replace("≠", "!=")
    normalized = re.sub(r"\\(?:mathbf|mathrm|textit|text|operatorname)\s*", "", normalized)
    normalized = normalized.replace("\\left", "").replace("\\right", "").replace("\\_", "_")
    normalized = normalized.replace("\\dots", "...").replace("\\ldots", "...").replace(". . .", "...")
    normalized = normalized.replace("\\geq", "≥").replace("\\ge", "≥")
    normalized = normalized.replace("\\leq", "≤").replace("\\le", "≤")
    return re.sub(r"[\s${}]", "", normalized)


def fact_check(identifier: str, normalized: str) -> bool:
    checks: dict[str, Callable[[str], bool]] = {
        "p1_i2": lambda value: "x_i^(2)" in value or "x(2)i" in value,
        "p1_k2": lambda value: "x_k^(2)" in value or "x(2)k" in value,
        "p1_xk": lambda value: "examplex_k" in value or "examplexk,k=1,...,N" in value,
        "p1_C": lambda value: "1,2,...,C" in value,
        "p2_hyper_minus": lambda value: "wx-b=0" in value,
        "p2_sign_minus": lambda value: "y=sign(wx-b)" in value,
        "p2_model_minus": lambda value: "f(x)=sign(w^*x-b^*)" in value,
        "p2_negative_one": lambda value: "returns+1iftheinputisapositivenumberor-1if" in value,
        "p2_constraints": lambda value: "wx_i-b≥1" in value and "wx_i-b≤-1" in value,
    }
    return checks[identifier](normalized)


def evaluate_candidate(text: str, proven_facts: set[str]) -> dict[str, object]:
    normalized = normalize_candidate(text)
    facts = {
        fact.identifier: (
            "MATCH" if fact_check(fact.identifier, normalized) else "REJECTED_CONTRADICTION_OR_ABSENCE"
        )
        if fact.identifier in proven_facts
        else "SOURCE_NOT_PROVEN"
        for fact in FACTS
    }
    matched = sum(status == "MATCH" for status in facts.values())
    return {"matched": matched, "proven": len(proven_facts), "facts": facts}


def candidate_files(root: Path) -> dict[str, list[Path]]:
    return {
        "marker_force_ocr": [root / "marker-output-force-warm/source-pages-7-10/source-pages-7-10.md"],
        "gemma_200dpi": [root / "gemma4-output/page-1.md", root / "gemma4-output/page-2.md"],
        "gemma_300dpi": [root / "gemma4-output-300dpi/page-1.md", root / "gemma4-output-300dpi/page-2.md"],
        "gemma_200_300_reconciled": [
            root / "gemma4-output-reconciled-200-300dpi/page-1.md",
            root / "gemma4-output-reconciled-200-300dpi/page-2.md",
        ],
        "docling_granite": [root / "docling-subset.md"],
        "mineru": [root / "mineru-output-service-warm/source-pages-7-10/hybrid_auto/source-pages-7-10.md"],
    }


def load_candidates(root: Path) -> tuple[dict[str, str], dict[str, object]]:
    candidates: dict[str, str] = {}
    provenance: dict[str, object] = {}
    for name, files in candidate_files(root).items():
        missing = [str(path) for path in files if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"Entrées absentes pour {name}: {missing}")
        candidates[name] = "\n".join(path.read_text(encoding="utf-8") for path in files)
        provenance[name] = [
            {"path": str(path), "sha256": sha256(path), "bytes": path.stat().st_size} for path in files
        ]
    return candidates, provenance


def mutation_controls(marker_text: str, proven_facts: set[str]) -> dict[str, object]:
    replacements = {
        "p1_i2": ("x_i^{(2)}", "x_k^{(2)}"),
        "p1_k2": ("x_k^{(2)}", "x_i^{(2)}"),
        "p1_xk": ("\\mathbf{x}_k", "\\mathbf{x}_i"),
        "p1_C": ("\\dots, C", "\\dots"),
        "p2_hyper_minus": ("\\mathbf{w}\\mathbf{x} - b = 0", "\\mathbf{w}\\mathbf{x} \\ne b = 0"),
        "p2_sign_minus": ("y = \\text{sign}(\\mathbf{w}\\mathbf{x} - b)", "y = \\text{sign}(\\mathbf{w} - b)"),
        "p2_model_minus": ("\\mathbf{w}^*\\mathbf{x} - b^*", "\\mathbf{w}^*\\mathbf{x} + b^*"),
        "p2_negative_one": ("or  $-1$  if the input", "or  $1$  if the input"),
        "p2_constraints": ("\\leq -1", "\\leq 1"),
    }
    results: dict[str, object] = {}
    for fact_id, (before, after) in replacements.items():
        if before not in marker_text:
            raise ValueError(f"Mutation impossible, fragment absent pour {fact_id}: {before}")
        mutated = marker_text.replace(before, after, 1)
        evaluation = evaluate_candidate(mutated, proven_facts)
        rejected = evaluation["facts"][fact_id] != "MATCH"
        results[fact_id] = {"before": before, "after": after, "rejected": rejected}
    return results


def render_crops(pdf_path: Path, pdftoppm: Path, output_dir: Path, dpi: int) -> dict[str, dict[str, object]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    full_pages: dict[int, Path] = {}
    for page in sorted({crop.page for crop in CROPS}):
        prefix = output_dir / f"page-{page}-{dpi}dpi"
        subprocess.run(
            [
                str(pdftoppm), "-f", str(page), "-l", str(page), "-r", str(dpi),
                "-png", "-singlefile", str(pdf_path), str(prefix),
            ],
            check=True,
        )
        full_pages[page] = prefix.with_suffix(".png")

    rendered: dict[str, dict[str, object]] = {}
    scale = dpi / 72.0
    for crop in CROPS:
        x0, top, x1, bottom = crop.box_points
        pixel_box = tuple(round(value * scale) for value in (x0, top, x1, bottom))
        with Image.open(full_pages[crop.page]) as page_image:
            crop_image = page_image.crop(pixel_box)
            path = output_dir / f"{crop.identifier}-{dpi}dpi.png"
            crop_image.save(path)
        rendered[crop.identifier] = {
            "path": str(path),
            "sha256": sha256(path),
            "page": crop.page,
            "box_points": crop.box_points,
            "box_pixels": pixel_box,
            "width": crop_image.width,
            "height": crop_image.height,
        }

    thumbnails = []
    for crop in CROPS:
        with Image.open(rendered[crop.identifier]["path"]) as image:
            thumb = image.convert("RGB")
            thumb.thumbnail((1400, 260))
            bordered = ImageOps.expand(thumb, border=10, fill="white")
            canvas = Image.new("RGB", (bordered.width, bordered.height + 35), "white")
            canvas.paste(bordered, (0, 35))
            ImageDraw.Draw(canvas).text((10, 8), crop.identifier, fill="black")
            thumbnails.append(canvas)
    sheet_width = max(image.width for image in thumbnails)
    sheet_height = sum(image.height for image in thumbnails)
    sheet = Image.new("RGB", (sheet_width, sheet_height), "white")
    y = 0
    for image in thumbnails:
        sheet.paste(image, (0, y))
        y += image.height
    sheet_path = output_dir / "contact-sheet.png"
    sheet.save(sheet_path)
    rendered["contact_sheet"] = {"path": str(sheet_path), "sha256": sha256(sheet_path)}
    return rendered


def request_json(url: str, payload: dict[str, object] | None = None, timeout: int = 3600) -> dict[str, object]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def gemma_prompt(crop: Crop, facts_by_id: dict[str, Fact], include_source: bool) -> str:
    base = (
        "Transcribe exactly this crop from one PDF page. Preserve every visible symbol. "
        "Use valid LaTeX for mathematics. Do not summarize, correct the author, add commentary, "
        "or wrap the answer in a code fence. "
    )
    if crop.output_kind == "latex":
        base += "Return only the formula or formulas visible in the crop. "
    else:
        base += "Return the visible text as Markdown. "
    if not include_source:
        return base
    evidence = "; ".join(
        f"{facts_by_id[fact_id].description}: source drawing sequence `{facts_by_id[fact_id].source_needle}`"
        for fact_id in crop.facts
    )
    return (
        base
        + "A second channel extracted from the PDF drawing program accompanies the image. "
        + "It describes glyphs and order, not the author's original LaTeX. Use it only to resolve visual ambiguity. "
        + "If a Unicode text map conflicts with a font glyph, preserve the glyph actually drawn. "
        + f"Source evidence: {evidence}."
    )


def run_targeted_gemma(
    endpoint: str,
    model: str,
    crop_records: dict[str, dict[str, object]],
    output_dir: Path,
) -> tuple[dict[str, object], dict[str, str]]:
    models = request_json(f"{endpoint.rstrip('/')}/models", timeout=30)
    available = {item["id"] for item in models.get("data", [])}
    if model not in available:
        raise RuntimeError(f"Modèle requis absent: {model}; disponibles={sorted(available)}")

    facts_by_id = {fact.identifier: fact for fact in FACTS}
    records: dict[str, object] = {}
    combined: dict[str, list[str]] = {"image_only": [], "image_plus_source": []}
    for mode, include_source in (("image_only", False), ("image_plus_source", True)):
        mode_dir = output_dir / mode
        mode_dir.mkdir(parents=True, exist_ok=True)
        for crop in CROPS:
            image_path = Path(str(crop_records[crop.identifier]["path"]))
            data_url = "data:image/png;base64," + base64.b64encode(image_path.read_bytes()).decode("ascii")
            prompt = gemma_prompt(crop, facts_by_id, include_source)
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    }
                ],
                "temperature": 0,
                "max_tokens": 2048,
            }
            started = time.perf_counter()
            response = request_json(f"{endpoint.rstrip('/')}/chat/completions", payload=payload)
            elapsed = time.perf_counter() - started
            content = str(response["choices"][0]["message"]["content"])
            output_path = mode_dir / f"{crop.identifier}.md"
            output_path.write_text(content, encoding="utf-8", newline="\n")
            response_path = mode_dir / f"{crop.identifier}-response.json"
            response_path.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
            request_path = mode_dir / f"{crop.identifier}-request.json"
            request_path.write_text(
                json.dumps(
                    {
                        "model": model,
                        "temperature": 0,
                        "max_tokens": 2048,
                        "prompt": prompt,
                        "image": {"path": str(image_path), "sha256": sha256(image_path)},
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
                newline="\n",
            )
            evaluation = {
                fact_id: "MATCH" if fact_check(fact_id, normalize_candidate(content)) else "REJECTED_CONTRADICTION_OR_ABSENCE"
                for fact_id in crop.facts
            }
            records[f"{mode}/{crop.identifier}"] = {
                "elapsed_seconds": round(elapsed, 3),
                "prompt_tokens": response.get("usage", {}).get("prompt_tokens"),
                "completion_tokens": response.get("usage", {}).get("completion_tokens"),
                "response_id": response.get("id"),
                "system_fingerprint": response.get("system_fingerprint"),
                "output": str(output_path),
                "output_sha256": sha256(output_path),
                "facts": evaluation,
            }
            combined[mode].append(content)
    return records, {mode: "\n".join(parts) for mode, parts in combined.items()}


def markdown_report(report: dict[str, object]) -> str:
    lines = [
        "# Résultats — preuve PDF source + rendu",
        "",
        f"- PDF : `{report['input']['sha256']}`",
        f"- Faits prouvés par la source : **{report['metrics']['source_proven']}/{report['metrics']['facts_total']}**",
        f"- Mutations rejetées : **{report['metrics']['mutations_rejected']}/{report['metrics']['mutations_total']}**",
        "",
        "## Candidats existants",
        "",
        "| Candidat | Faits conformes | Faits prouvés |",
        "|---|---:|---:|",
    ]
    for name, result in report["existing_candidates"].items():
        lines.append(f"| {name} | {result['matched']} | {result['proven']} |")

    lines.extend(
        [
            "",
            "## Reconnaissance ciblée",
            "",
            "| Mode | Crop | Faits conformes | Faits ciblés | Durée (s) |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for key, result in report["targeted_gemma"].items():
        mode, crop = key.split("/", 1)
        matched = sum(status == "MATCH" for status in result["facts"].values())
        lines.append(f"| {mode} | {crop} | {matched} | {len(result['facts'])} | {result['elapsed_seconds']} |")

    lines.extend(
        [
            "",
            "## Verdict préenregistré",
            "",
            f"- Rejet de toutes les mutations : **{'OUI' if report['verdict']['all_mutations_rejected'] else 'NON'}**",
            f"- Aucune acceptation sans preuve source : **{'OUI' if report['verdict']['no_unproven_acceptance'] else 'NON'}**",
            f"- Source + crop non inférieur au contrôle : **{'OUI' if report['verdict']['source_not_worse'] else 'NON'}**",
            f"- Correction ciblée de `x_k` : **{'OUI' if report['verdict']['source_fixed_xk'] else 'NON'}**",
            "",
            "Une conformité porte uniquement sur les neuf faits préenregistrés. Elle ne prouve pas l’intégralité des pages.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--pdftoppm", type=Path, required=True)
    parser.add_argument("--gemma-endpoint", required=True)
    parser.add_argument("--gemma-model", required=True)
    parser.add_argument("--dpi", type=int, required=True)
    args = parser.parse_args()

    experiment_dir = args.output_dir.resolve()
    experiment_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = args.root / "source-pages-7-10.pdf"
    if not pdf_path.is_file() or not args.pdftoppm.is_file():
        raise FileNotFoundError("PDF ou pdftoppm absent")

    source_manifest = extract_source_manifest(pdf_path)
    manifest_path = experiment_dir / "source-manifest.json"
    manifest_path.write_text(json.dumps(source_manifest, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")

    page_streams = {page["page"]: page["visual_stream"] for page in source_manifest["pages"]}
    source_facts = {
        fact.identifier: {
            "page": fact.page,
            "description": fact.description,
            "source_needle": fact.source_needle,
            "status": "PROVEN" if fact.source_needle in page_streams[fact.page] else "NOT_PROVEN",
        }
        for fact in FACTS
    }
    proven_facts = {identifier for identifier, result in source_facts.items() if result["status"] == "PROVEN"}

    candidates, provenance = load_candidates(args.root)
    existing_results = {name: evaluate_candidate(text, proven_facts) for name, text in candidates.items()}
    mutations = mutation_controls(candidates["marker_force_ocr"], proven_facts)

    crop_records = render_crops(pdf_path, args.pdftoppm, experiment_dir / "crops", args.dpi)
    targeted_records, targeted_combined = run_targeted_gemma(
        args.gemma_endpoint, args.gemma_model, crop_records, experiment_dir / "targeted"
    )

    targeted_overall = {mode: evaluate_candidate(text, proven_facts) for mode, text in targeted_combined.items()}
    image_only_matches = sum(
        status == "MATCH"
        for key, result in targeted_records.items()
        if key.startswith("image_only/")
        for status in result["facts"].values()
    )
    source_matches = sum(
        status == "MATCH"
        for key, result in targeted_records.items()
        if key.startswith("image_plus_source/")
        for status in result["facts"].values()
    )
    p1_source = targeted_records["image_plus_source/p1_feature_indices"]["facts"]

    report: dict[str, object] = {
        "input": {"path": str(pdf_path), "sha256": sha256(pdf_path), "bytes": pdf_path.stat().st_size},
        "runtime": {
            "pdftoppm": str(args.pdftoppm),
            "dpi": args.dpi,
            "gemma_endpoint": args.gemma_endpoint,
            "gemma_model": args.gemma_model,
        },
        "source_manifest": {"path": str(manifest_path), "sha256": sha256(manifest_path)},
        "source_facts": source_facts,
        "candidate_provenance": provenance,
        "existing_candidates": existing_results,
        "mutation_controls": mutations,
        "crops": crop_records,
        "targeted_gemma": targeted_records,
        "targeted_overall": targeted_overall,
        "metrics": {
            "facts_total": len(FACTS),
            "source_proven": len(proven_facts),
            "mutations_total": len(mutations),
            "mutations_rejected": sum(bool(result["rejected"]) for result in mutations.values()),
            "targeted_image_only_matches": image_only_matches,
            "targeted_image_plus_source_matches": source_matches,
        },
        "verdict": {
            "all_mutations_rejected": all(bool(result["rejected"]) for result in mutations.values()),
            "no_unproven_acceptance": all(
                status != "MATCH"
                for result in existing_results.values()
                for identifier, status in result["facts"].items()
                if identifier not in proven_facts
            ),
            "source_not_worse": source_matches >= image_only_matches,
            "source_fixed_xk": p1_source["p1_k2"] == "MATCH" and p1_source["p1_xk"] == "MATCH",
        },
    }
    report_path = experiment_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    results_path = experiment_dir / "RESULTS.md"
    results_path.write_text(markdown_report(report), encoding="utf-8", newline="\n")
    print(results_path)
    print(json.dumps(report["metrics"], ensure_ascii=False))
    print(json.dumps(report["verdict"], ensure_ascii=False))


if __name__ == "__main__":
    main()
