from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
from collections import Counter, defaultdict
from io import BytesIO
from pathlib import Path
from typing import Any

import fitz
import fontTools
import pypdf
from fontTools import agl
from fontTools.cffLib import CFFFontSet
from fontTools.encodings.MacRoman import MacRoman
from fontTools.encodings.StandardEncoding import StandardEncoding
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen
from pypdf import PdfReader
from pypdf.generic import ContentStream


EXPECTED_SHA256 = "219c2064ba9292d286f4b3bcc65eb9e94b418705c51b9f98f54f2ad70321ddf1"
SUPPORTED_BASE_ENCODINGS = {
    "/MacRomanEncoding": MacRoman,
    "/StandardEncoding": StandardEncoding,
}


class ProofError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProofError(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def number_list(values: Any) -> list[float]:
    return [float(value) for value in values]


def codepoints(value: str | None) -> list[str]:
    return [] if value is None else [f"U+{ord(char):04X}" for char in value]


def original_bytes(value: Any) -> bytes | None:
    raw = getattr(value, "original_bytes", None)
    if raw is not None:
        return bytes(raw)
    return bytes(value) if isinstance(value, (bytes, bytearray)) else None


def text_chunks(operands: list[Any], operator: bytes) -> list[bytes]:
    if operator == b"Tj":
        raw = original_bytes(operands[-1])
        return [] if raw is None else [raw]
    if operator == b"TJ":
        return [raw for item in operands[0] if (raw := original_bytes(item)) is not None]
    return []


def parse_to_unicode(font: Any) -> dict[int, str]:
    stream = font.get("/ToUnicode")
    if stream is None:
        return {}
    lines = stream.get_object().get_data().decode("latin-1").replace("\r", "").splitlines()
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
            require(len(tokens) == 2, f"ToUnicode bfchar non supporté: {line}")
            source, destination = tokens
            require(len(source) == 2, f"Code ToUnicode non monooctet: {source}")
            result[int(source, 16)] = bytes.fromhex(destination).decode("utf-16-be")
            continue
        require(len(tokens) == 3 and "[" not in line, f"ToUnicode bfrange non supporté: {line}")
        start, end, destination = tokens
        require(len(start) == len(end) == 2, f"Plage ToUnicode non monooctet: {line}")
        base = bytes.fromhex(destination).decode("utf-16-be")
        require(len(base) == 1, f"Destination ToUnicode complexe: {destination}")
        for offset, source in enumerate(range(int(start, 16), int(end, 16) + 1)):
            result[source] = chr(ord(base) + offset)
    return result


def font_encoding(font: Any) -> tuple[list[str], dict[str, Any]]:
    encoding = font.get("/Encoding", "/StandardEncoding")
    encoding = encoding.get_object() if hasattr(encoding, "get_object") else encoding
    differences: list[dict[str, Any]] = []
    if isinstance(encoding, str):
        base_name = str(encoding)
        raw_differences: list[Any] = []
    else:
        base_name = str(encoding.get("/BaseEncoding", "/StandardEncoding"))
        raw_differences = list(encoding.get("/Differences", []))
    require(base_name in SUPPORTED_BASE_ENCODINGS, f"Encodage non supporté: {base_name}")
    names = list(SUPPORTED_BASE_ENCODINGS[base_name])
    code: int | None = None
    for item in raw_differences:
        if isinstance(item, int):
            code = int(item)
            continue
        require(code is not None and 0 <= code <= 255, "Differences sans code valide")
        glyph_name = str(item).removeprefix("/")
        names[code] = glyph_name
        differences.append({"code": code, "code_hex": f"0x{code:02x}", "glyph_name": glyph_name})
        code += 1
    return names, {"base": base_name, "differences": differences}


def load_font(resource: str, reference: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    font = reference.get_object()
    require(str(font.get("/Subtype")) == "/Type1", f"{resource}: seule une police Type1 est supportée")
    descriptor = font.get("/FontDescriptor")
    require(descriptor is not None, f"{resource}: FontDescriptor absent")
    font_file = descriptor.get_object().get("/FontFile3")
    require(font_file is not None, f"{resource}: FontFile3 embarqué absent")
    font_stream = font_file.get_object()
    require(str(font_stream.get("/Subtype")) == "/Type1C", f"{resource}: FontFile3 non Type1C")
    cff_bytes = font_stream.get_data()
    cff = CFFFontSet()
    cff.decompile(BytesIO(cff_bytes), None)
    require(len(cff.fontNames) == 1, f"{resource}: plusieurs polices CFF")
    top = cff[cff.fontNames[0]]
    charset = list(top.charset)
    names, encoding = font_encoding(font)
    base_font = str(font.get("/BaseFont"))
    trace_font = base_font.removeprefix("/").split("+", 1)[-1]
    to_unicode = parse_to_unicode(font)
    public = {
        "resource": resource,
        "xref": int(reference.idnum),
        "base_font": base_font,
        "trace_font": trace_font,
        "subtype": "/Type1",
        "encoding": encoding,
        "to_unicode": {f"0x{code:02x}": value for code, value in to_unicode.items()},
        "embedded_font": {"subtype": "/Type1C", "bytes": len(cff_bytes), "charset": charset},
    }
    runtime = {
        "public": public,
        "encoding_names": names,
        "to_unicode": to_unicode,
        "glyph_ids": {name: index for index, name in enumerate(charset)},
        "top": top,
    }
    return public, runtime


def source_glyphs(page: Any, reader: PdfReader, fonts: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], Counter[str]]:
    resources = page["/Resources"]
    require("/XObject" not in resources, "Les Form/Image XObjects ne sont pas supportés")
    operations = ContentStream(page.get_contents(), reader).operations
    counts = Counter(operator.decode("latin-1") for _, operator in operations)
    require(counts["Do"] == counts["Tr"] == 0, "Do et Tr ne sont pas supportés")
    require(counts["'"] == counts['"'] == 0, "Les opérateurs texte ' et \" ne sont pas supportés")
    current_font: str | None = None
    current_matrix: list[float] | None = None
    glyphs: list[dict[str, Any]] = []
    for operation_index, (operands, operator) in enumerate(operations):
        if operator == b"Tf":
            current_font = str(operands[0])
            require(current_font in fonts, f"Ressource de police inconnue: {current_font}")
        elif operator == b"Tm":
            current_matrix = number_list(operands)
        for chunk in text_chunks(operands, operator):
            require(current_font is not None, f"Texte sans police à l'opération {operation_index}")
            font = fonts[current_font]
            for code in chunk:
                glyph_name = font["encoding_names"][code]
                require(glyph_name != ".notdef", f"{current_font} 0x{code:02x}: glyphe non défini")
                require(glyph_name in font["glyph_ids"], f"{current_font} 0x{code:02x}: CharString /{glyph_name} absent")
                unicode_value = agl.toUnicode(glyph_name)
                require(bool(unicode_value), f"{current_font} /{glyph_name}: aucun Unicode AGL")
                glyphs.append({
                    "sequence_index": len(glyphs),
                    "operation_index": operation_index,
                    "font_resource": current_font,
                    "code": code,
                    "code_hex": f"0x{code:02x}",
                    "glyph_name": glyph_name,
                    "agl_unicode": unicode_value,
                    "agl_codepoints": codepoints(unicode_value),
                    "cff_gid": font["glyph_ids"][glyph_name],
                    "text_matrix": current_matrix,
                })
    return glyphs, counts


def attach_render_and_blocks(page: fitz.Page, glyphs: list[dict[str, Any]], fonts: dict[str, dict[str, Any]]) -> dict[str, int]:
    trace = [
        {"font": span["font"], "size": span["size"], "seqno": span["seqno"], "unicode": value,
         "gid": gid, "origin": number_list(origin), "bbox": number_list(bbox)}
        for span in page.get_texttrace()
        for value, gid, origin, bbox in span["chars"]
    ]
    require(len(trace) == len(glyphs), f"Source/trace: {len(glyphs)} != {len(trace)}")
    trace_unicode_matches = 0
    trace_unicode_mismatches = 0
    for source, rendered in zip(glyphs, trace, strict=True):
        font = fonts[source["font_resource"]]
        require(rendered["font"] == font["public"]["trace_font"], f"Police trace divergente à {source['sequence_index']}")
        require(rendered["gid"] == source["cff_gid"], f"GID divergent à {source['sequence_index']}")
        rendered_unicode = chr(rendered["unicode"])
        rendered["unicode_text"] = rendered_unicode
        rendered["unicode_codepoints"] = codepoints(rendered_unicode)
        rendered["unicode_matches_agl"] = rendered_unicode == source["agl_unicode"]
        if rendered["unicode_matches_agl"]:
            trace_unicode_matches += 1
        else:
            trace_unicode_mismatches += 1
        source["rendered"] = rendered

    rawdict = page.get_text("rawdict", sort=False)
    block_index: defaultdict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    rawdict_characters = 0
    for block_id, block in enumerate(rawdict["blocks"]):
        if block.get("type") != 0:
            continue
        for line_id, line in enumerate(block["lines"]):
            for span_id, span in enumerate(line["spans"]):
                for char_id, char in enumerate(span["chars"]):
                    rawdict_characters += 1
                    key = (span["font"], round(char["origin"][0], 3), round(char["origin"][1], 3), ord(char["c"]))
                    block_index[key].append({"block": block_id, "line": line_id, "span": span_id, "char": char_id,
                                             "block_bbox": number_list(block["bbox"]), "line_bbox": number_list(line["bbox"])})
    claimed_rawdict: set[tuple[int, int, int, int]] = set()
    for source in glyphs:
        rendered = source["rendered"]
        key = (rendered["font"], round(rendered["origin"][0], 3), round(rendered["origin"][1], 3), rendered["unicode"])
        matches = block_index.get(key, [])
        require(len(matches) == 1, f"Association rawdict non univoque à {source['sequence_index']}: {len(matches)}")
        match = matches[0]
        identity = (match["block"], match["line"], match["span"], match["char"])
        require(identity not in claimed_rawdict, f"Association rawdict réutilisée à {source['sequence_index']}")
        claimed_rawdict.add(identity)
        source["rawdict"] = match
    return {"trace_characters": len(trace), "rawdict_characters": rawdict_characters,
            "rawdict_text_blocks": sum(block.get("type") == 0 for block in rawdict["blocks"]),
            "trace_unicode_matches": trace_unicode_matches,
            "trace_unicode_mismatches": trace_unicode_mismatches}


def compact_glyph(glyph: dict[str, Any]) -> dict[str, Any]:
    return {key: glyph[key] for key in (
        "sequence_index", "operation_index", "font_resource", "code", "code_hex", "glyph_name",
        "agl_unicode", "agl_codepoints", "cff_gid", "text_matrix", "rendered", "rawdict"
    )}


def sequence_digest(glyphs: list[dict[str, Any]]) -> str:
    values = [[g["font_resource"], g["code"], g["glyph_name"], g["cff_gid"], g["rendered"]["gid"],
               g["rendered"]["origin"], g["rawdict"]["block"], g["rawdict"]["line"]] for g in glyphs]
    return sha256_bytes(json.dumps(values, separators=(",", ":"), ensure_ascii=False).encode())


def page_report(page_number: int, pypdf_page: Any, fitz_page: fitz.Page, reader: PdfReader) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    require(fitz_page.rotation == 0, f"Page {page_number}: rotation non supportée")
    font_public: dict[str, Any] = {}
    font_runtime: dict[str, dict[str, Any]] = {}
    for resource, reference in pypdf_page["/Resources"]["/Font"].items():
        public, runtime = load_font(str(resource), reference)
        font_public[str(resource)] = public
        font_runtime[str(resource)] = runtime
    glyphs, operations = source_glyphs(pypdf_page, reader, font_runtime)
    layout = attach_render_and_blocks(fitz_page, glyphs, font_runtime)
    conflicts: dict[tuple[str, int, str, str], dict[str, Any]] = {}
    to_unicode_present = 0
    to_unicode_matches = 0
    for glyph in glyphs:
        declared = font_runtime[glyph["font_resource"]]["to_unicode"].get(glyph["code"])
        if declared is None:
            continue
        to_unicode_present += 1
        if declared == glyph["agl_unicode"]:
            to_unicode_matches += 1
            continue
        key = (glyph["font_resource"], glyph["code"], declared, glyph["agl_unicode"])
        conflict = conflicts.setdefault(key, {
            "page": page_number, "font_resource": glyph["font_resource"], "code": glyph["code"],
            "code_hex": glyph["code_hex"], "glyph_name": glyph["glyph_name"],
            "to_unicode": declared, "to_unicode_codepoints": codepoints(declared),
            "agl_unicode": glyph["agl_unicode"], "agl_codepoints": glyph["agl_codepoints"],
            "occurrences": 0, "operation_indices": [],
        })
        conflict["occurrences"] += 1
        if glyph["operation_index"] not in conflict["operation_indices"]:
            conflict["operation_indices"].append(glyph["operation_index"])
    total = len(glyphs)
    coverage = {"source_codes": total, "encoding_named": total, "cff_charstrings": total,
                "agl_mapped": total, "trace_glyphs": layout["trace_characters"],
                "gid_matches": total, "rawdict_assignments": total,
                "gid_mismatches": 0, "rawdict_missing": 0, "rawdict_ambiguous": 0,
                "trace_unicode_matches": layout["trace_unicode_matches"],
                "trace_unicode_mismatches": layout["trace_unicode_mismatches"],
                "to_unicode_present": to_unicode_present,
                "to_unicode_matches": to_unicode_matches,
                "to_unicode_conflicts": to_unicode_present - to_unicode_matches,
                "to_unicode_absent": total - to_unicode_present}
    report = {
        "page": page_number, "box": number_list(fitz_page.rect), "rotation": fitz_page.rotation,
        "coverage": coverage, "sequence_sha256": sequence_digest(glyphs), "layout": layout,
        "operation_counts": [
            {"operator": operator, "count": count}
            for operator, count in sorted(operations.items())
        ],
        "font_usage": dict(sorted(Counter(g["font_resource"] for g in glyphs).items())),
        "fonts": font_public, "to_unicode_conflicts": list(conflicts.values()),
    }
    return report, glyphs, font_runtime


def exact_proofs(pages: list[list[dict[str, Any]]], reports: list[dict[str, Any]], fonts: list[dict[str, dict[str, Any]]]) -> dict[str, Any]:
    xk_candidates = [g for g in pages[0] if g["font_resource"] == "/Ty10" and g["code"] == 0x6B]
    require(len(xk_candidates) == 2, f"Deux indices k attendus, obtenu {len(xk_candidates)}")
    xk = next(g for g in xk_candidates if abs(g["rendered"]["origin"][0] - 322.861) < 0.001)
    base_x = pages[0][xk["sequence_index"] - 1]
    require((base_x["font_resource"], base_x["code"], base_x["glyph_name"]) == ("/Ty9", 0x78, "x"), "Base x de x_k absente")
    require(abs(base_x["rendered"]["bbox"][2] - xk["rendered"]["origin"][0]) < 0.01, "x et k ne sont pas adjacents")
    require(xk["rendered"]["origin"][1] > base_x["rendered"]["origin"][1], "k n'est pas en indice")
    require(xk["operation_index"] == 425 and xk["cff_gid"] == 5, "Preuve x_k inattendue")

    minus_occurrences = [g for g in pages[1] if g["font_resource"] == "/Ty18" and g["code"] == 0x21]
    require(len(minus_occurrences) == 10, f"Dix signes moins attendus, obtenu {len(minus_occurrences)}")
    minus = minus_occurrences[0]
    require(minus["operation_index"] == 107 and minus["glyph_name"] == "minus" and minus["cff_gid"] == 1,
            "Première preuve /minus inattendue")
    minus_font = fonts[1]["/Ty18"]
    require(minus_font["to_unicode"].get(0x21) == "≠", "Conflit ToUnicode /minus absent")
    charstring = minus_font["top"].CharStrings["minus"]
    bounds_pen = BoundsPen(None)
    charstring.draw(bounds_pen)
    recording_pen = RecordingPen()
    charstring.draw(recording_pen)
    require(bounds_pen.bounds == (83, 230, 694, 270), f"Tracé /minus inattendu: {bounds_pen.bounds}")
    path = [{"operator": operator, "points": [list(point) for point in points]} for operator, points in recording_pen.value]
    return {
        "x_k": {"page": 1, "base_x": compact_glyph(base_x), "subscript_k": compact_glyph(xk),
                "font": reports[0]["fonts"]["/Ty10"],
                "geometric_relation": {"x_end_minus_k_start": base_x["rendered"]["bbox"][2] - xk["rendered"]["origin"][0],
                                       "k_baseline_below_x": xk["rendered"]["origin"][1] - base_x["rendered"]["origin"][1]}},
        "minus": {"page": 2, "first_occurrence": compact_glyph(minus), "occurrences": len(minus_occurrences),
                  "font": reports[1]["fonts"]["/Ty18"], "cff_outline": {"bounds": list(bounds_pen.bounds), "path": path,
                  "interpretation": "une barre horizontale sans diagonale"}},
    }


def markdown(report: dict[str, Any]) -> str:
    lines = ["# Traçabilité structurelle des glyphes texte PDF", "", f"- PDF : `{report['pdf']['filename']}`",
             f"- SHA-256 : `{report['pdf']['sha256']}`", f"- Verdict : **{report['verdict']}**", "",
             "Ce verdict signifie que chaque code texte sélectionne un CharString CFF et que MuPDF rend le même GID. Il ne signifie pas que l'Unicode ou l'apparence raster de chaque glyphe est prouvé.", "",
             "## Couverture", "", "| Page | Codes source | CFF | GID conformes | Unicode trace = AGL | Associations rawdict |",
             "|---:|---:|---:|---:|---:|---:|"]
    for page in report["pages"]:
        c = page["coverage"]
        lines.append(f"| {page['page']} | {c['source_codes']} | {c['cff_charstrings']} | {c['gid_matches']} | {c['trace_unicode_matches']}/{c['trace_glyphs']} | {c['rawdict_assignments']} |")
    total = report["coverage"]
    lines += [f"| **Total** | **{total['source_codes']}** | **{total['cff_charstrings']}** | **{total['gid_matches']}** | **{total['trace_unicode_matches']}/{total['trace_glyphs']}** | **{total['rawdict_assignments']}** |", "",
              "Les caractères supplémentaires de `rawdict` sont des espaces de regroupement synthétiques ; ils ne sont pas comptés comme codes PDF.", "",
              "## Bilan Unicode", "",
              f"- `ToUnicode` absent : **{total['to_unicode_absent']}** occurrences ;",
              f"- `ToUnicode` conforme à AGL : **{total['to_unicode_matches']}** occurrences ;",
              f"- `ToUnicode` en conflit avec AGL : **{total['to_unicode_conflicts']}** occurrences ;",
              f"- Unicode MuPDF en conflit avec AGL : **{total['trace_unicode_mismatches']}** occurrences.", "",
              "## Conflits ToUnicode", "", "| Page | Police | Code | Glyphe CFF | ToUnicode | AGL | Occurrences |", "|---:|---|---|---|---|---|---:|"]
    for conflict in report["to_unicode_conflicts"]:
        lines.append(f"| {conflict['page']} | `{conflict['font_resource']}` | `{conflict['code_hex']}` | `/{conflict['glyph_name']}` | {' '.join(conflict['to_unicode_codepoints'])} | {' '.join(conflict['agl_codepoints'])} | {conflict['occurrences']} |")
    xk, minus = report["proofs"]["x_k"], report["proofs"]["minus"]
    lines += ["", "## Preuve `x_k`", "", f"Le `k` est le code `{xk['subscript_k']['code_hex']}` de `/Ty10`, mappé sur `/k`, GID `{xk['subscript_k']['cff_gid']}`. Son origine est `{xk['subscript_k']['rendered']['origin']}` et sa ligne de base est plus basse de `{xk['geometric_relation']['k_baseline_below_x']:.3f}` point que celle du `x`.", "",
              "## Preuve ciblée `/minus`", "", f"Les {minus['occurrences']} codes `0x21` de `/Ty18` sélectionnent `/minus`, GID `1`. `ToUnicode` annonce U+2260 ; le nom CFF `/minus`, l'AGL U+2212 et le tracé en barre horizontale étayent l'interprétation comme signe moins. Le tracé a les bornes `{minus['cff_outline']['bounds']}`.", "",
              "## Périmètre supporté", ""]
    lines.extend(f"- {item}" for item in report["support"]["supported"])
    lines += ["", "## Limites et rejets explicites", ""]
    lines.extend(f"- {item}" for item in report["support"]["rejected"])
    lines += ["", f"Commande : `{report['command']}`", ""]
    return "\n".join(lines)


def build_report(pdf_path: Path) -> dict[str, Any]:
    pdf_bytes = pdf_path.read_bytes()
    digest = sha256_bytes(pdf_bytes)
    require(digest == EXPECTED_SHA256, f"PDF inattendu: {digest}")
    reader = PdfReader(BytesIO(pdf_bytes))
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    require(len(reader.pages) == len(document) == 2, "Deux pages sont requises")
    page_reports: list[dict[str, Any]] = []
    page_glyphs: list[list[dict[str, Any]]] = []
    page_fonts: list[dict[str, dict[str, Any]]] = []
    try:
        for index in range(2):
            report, glyphs, font_runtime = page_report(
                index + 1, reader.pages[index], document.load_page(index), reader
            )
            page_reports.append(report)
            page_glyphs.append(glyphs)
            page_fonts.append(font_runtime)
        proofs = exact_proofs(page_glyphs, page_reports, page_fonts)
    finally:
        document.close()
    conflicts = [conflict for page in page_reports for conflict in page["to_unicode_conflicts"]]
    coverage = {key: sum(page["coverage"][key] for page in page_reports) for key in (
        "source_codes", "encoding_named", "cff_charstrings", "agl_mapped", "trace_glyphs",
        "gid_matches", "rawdict_assignments", "gid_mismatches", "rawdict_missing", "rawdict_ambiguous",
        "trace_unicode_matches", "trace_unicode_mismatches", "to_unicode_present",
        "to_unicode_matches", "to_unicode_conflicts", "to_unicode_absent")}
    require(coverage["source_codes"] == coverage["cff_charstrings"] == coverage["gid_matches"] == coverage["rawdict_assignments"] == 4088,
            f"Couverture totale inattendue: {coverage}")
    require(sum(item["occurrences"] for item in conflicts) == 21, "21 conflits ToUnicode étaient attendus")
    require(coverage["trace_unicode_mismatches"] == 20, "20 divergences Unicode trace/AGL étaient attendues")
    require(coverage["to_unicode_absent"] == 4067 and coverage["to_unicode_matches"] == 0,
            "Couverture ToUnicode inattendue")
    return {
        "schema_version": "1.1", "verdict": "TRAÇABILITÉ_STRUCTURELLE_COMPLÈTE",
        "runtime": {"python": platform.python_version(), "pymupdf": fitz.version[0],
                    "pypdf": pypdf.__version__, "fonttools": fontTools.__version__},
        "pdf": {"filename": pdf_path.name, "bytes": len(pdf_bytes), "sha256": digest, "pages": 2},
        "coverage": coverage, "pages": page_reports, "to_unicode_conflicts": conflicts, "proofs": proofs,
        "support": {
            "supported": ["contenus de page directs", "polices Type1 avec FontFile3 Type1C embarqué",
                          "codes monooctets MacRoman ou StandardEncoding avec Differences",
                          "ToUnicode bfchar et bfrange directs", "association source-rendu par ordre et GID CFF",
                          "association aux blocs MuPDF par police, origine et Unicode rendu"],
            "rejected": ["PDF dont le SHA-256 diffère", "Form XObjects ou opérateur Do", "mode de rendu Tr",
                         "polices Type0/CID, Type3, non embarquées ou non CFF", "CMap multioctet ou bfrange en tableau",
                         "rotation de page", "écart de longueur, de police, de GID ou association rawdict non univoque",
                         "dessins vectoriels et images sans glyphe texte"],
        },
        "command": "python source-render-proof/verify_all_glyphs.py",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prouve tous les glyphes texte du PDF source contre son rendu.")
    default_pdf = Path(__file__).resolve().parent.parent / "source-pages-7-10.pdf"
    parser.add_argument("pdf", nargs="?", type=Path, default=default_pdf)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    report = build_report(args.pdf.resolve())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "glyph-proof.json"
    markdown_path = args.output_dir / "glyph-proof.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(markdown(report), encoding="utf-8")
    print(f"{report['verdict']}: {report['coverage']['source_codes']}/4088 glyphes")
    print(json_path)
    print(markdown_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
