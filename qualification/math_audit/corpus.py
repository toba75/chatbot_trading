from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import reportlab
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen.canvas import Canvas


WIDTH, HEIGHT = A4
FONT_PATH = Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"

def _top_left_bbox(
    x: float, baseline: float, width: float, *, ascent: float, descent: float
) -> list[float]:
    return [
        round(x, 2),
        round(HEIGHT - baseline - ascent, 2),
        round(x + width, 2),
        round(HEIGHT - baseline + descent, 2),
    ]

def _region(
    identifier: str,
    page: int,
    bbox: list[float],
    layout: str,
    text: str,
    assertions: list[dict[str, str]],
) -> dict[str, object]:
    return {
        "id": identifier,
        "page": page,
        "bbox": bbox,
        "bbox_coord_origin": "TOPLEFT",
        "layout": layout,
        "text": text,
        "semantic_assertions": assertions,
        "evidence": {
            "kind": "generator_geometry",
            "reference": f"qualification.math_audit.corpus:{identifier}",
        },
    }

def _draw_formula(
    canvas: Canvas,
    regions: list[dict[str, object]],
    *,
    identifier: str,
    page: int,
    x: float,
    baseline: float,
    text: str,
    font: str,
    size: float,
    layout: str,
    assertions: list[dict[str, str]],
    rotated: bool = False,
) -> None:
    canvas.setFont(font, size)
    canvas.drawString(x, baseline, text)
    width = pdfmetrics.stringWidth(text, font, size)
    bbox = _top_left_bbox(x, baseline, width, ascent=size, descent=size * 0.25)
    if rotated:
        bbox = [baseline - size * 0.25, x, baseline + size, x + width]
    regions.append(
        _region(
            identifier,
            page,
            [round(value, 2) for value in bbox],
            layout,
            text,
            assertions,
        )
    )

def _scan_image(path: Path) -> tuple[float, float, float, float]:
    scale = 2
    image = Image.new("RGB", (round(WIDTH * scale), round(HEIGHT * scale)), "white")
    draw = ImageDraw.Draw(image)
    body = ImageFont.truetype(str(FONT_PATH), 28)
    formula = ImageFont.truetype(str(FONT_PATH), 42)
    draw.text((110, 150), "Page rasterisee : aucun glyphe PDF.", fill="black", font=body)
    formula_xy = (210, 610)
    formula_text = "E = m c^2"
    draw.text(formula_xy, formula_text, fill="black", font=formula)
    pixel_bbox = draw.textbbox(formula_xy, formula_text, font=formula)
    image.save(path, format="PNG", optimize=False, compress_level=9)
    return tuple(value / scale for value in pixel_bbox)

def build_corpus(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / "math-regression.pdf"
    scan_path = output_dir / "scan-page.png"
    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiMin-W3"))

    regions: list[dict[str, object]] = []
    canvas = Canvas(
        str(pdf_path), pagesize=A4, invariant=1, pageCompression=0, bottomup=1
    )
    canvas.setTitle("Corpus de qualification mathematique")

    canvas.setFont("Helvetica", 12)
    canvas.drawString(54, 760, "Page 1 - police PDF Type 1")
    canvas.drawString(54, 700, "Une formule en ligne suit :")
    _draw_formula(
        canvas,
        regions,
        identifier="type1-inline",
        page=1,
        x=205,
        baseline=700,
        text="x_i = 3",
        font="Helvetica",
        size=12,
        layout="inline",
        assertions=[{"relation": "sequence", "expected": "x_i=3"}],
    )
    _draw_formula(
        canvas,
        regions,
        identifier="type1-display",
        page=1,
        x=205,
        baseline=590,
        text="w x - b = 0",
        font="Helvetica",
        size=20,
        layout="display",
        assertions=[{"relation": "sequence", "expected": "wx-b=0"}],
    )
    canvas.showPage()

    canvas.setFont("HeiseiMin-W3", 12)
    canvas.drawString(54, 760, "Page 2 - police Type 0/CID standard")
    canvas.drawString(54, 700, "Une formule en ligne suit :")
    _draw_formula(
        canvas,
        regions,
        identifier="cid-inline",
        page=2,
        x=230,
        baseline=700,
        text="y = x + 1",
        font="HeiseiMin-W3",
        size=12,
        layout="inline",
        assertions=[{"relation": "sequence", "expected": "y=x+1"}],
    )
    formula_x, formula_y = 220, 590
    base_text = "f(x) = x"
    canvas.setFont("HeiseiMin-W3", 20)
    canvas.drawString(formula_x, formula_y, base_text)
    base_width = pdfmetrics.stringWidth(base_text, "HeiseiMin-W3", 20)
    canvas.setFont("HeiseiMin-W3", 12)
    canvas.drawString(formula_x + base_width, formula_y + 10, "2")
    sup_width = pdfmetrics.stringWidth("2", "HeiseiMin-W3", 12)
    base_bbox = _top_left_bbox(formula_x, formula_y, base_width, ascent=20, descent=5)
    sup_bbox = _top_left_bbox(
        formula_x + base_width, formula_y + 10, sup_width, ascent=12, descent=3
    )
    regions.append(
        _region(
            "cid-display",
            2,
            [
                min(base_bbox[0], sup_bbox[0]),
                min(base_bbox[1], sup_bbox[1]),
                max(base_bbox[2], sup_bbox[2]),
                max(base_bbox[3], sup_bbox[3]),
            ],
            "display",
            "f(x) = x²",
            [
                {"relation": "sequence", "expected": "f(x)=x2"},
                {"relation": "superscript", "base": "x", "expected": "2"},
            ],
        )
    )
    canvas.showPage()

    canvas.setPageRotation(90)
    canvas.setFont("Helvetica", 12)
    canvas.drawString(54, 400, "Page 3 - contenu tourne de 90 degres")
    _draw_formula(
        canvas,
        regions,
        identifier="rotated-display",
        page=3,
        x=190,
        baseline=290,
        text="a^2 + b^2 = c^2",
        font="Helvetica",
        size=20,
        layout="display",
        assertions=[{"relation": "sequence", "expected": "a^2+b^2=c^2"}],
        rotated=True,
    )
    canvas.showPage()
    canvas.setPageRotation(0)

    scan_bbox = _scan_image(scan_path)
    canvas.drawImage(ImageReader(scan_path), 0, 0, width=WIDTH, height=HEIGHT)
    regions.append(
        _region(
            "scan-display",
            4,
            [round(value, 2) for value in scan_bbox],
            "display",
            "E = m c^2",
            [{"relation": "sequence", "expected": "E=mc^2"}],
        )
    )
    canvas.save()
    scan_path.unlink()

    oracle = {
        "schema_version": 1,
        "exhaustive": True,
        "representative": False,
        "coordinate_system": "PDF points, TOPLEFT",
        "pages": [
            {"page": 1, "source_kind": "born_digital_type1"},
            {"page": 2, "source_kind": "born_digital_type0_cid"},
            {"page": 3, "source_kind": "born_digital_rotated"},
            {"page": 4, "source_kind": "scanned_raster"},
        ],
        "regions": regions,
    }
    (output_dir / "oracle.json").write_text(
        json.dumps(oracle, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

def main() -> None:
    parser = argparse.ArgumentParser(description="Génère le corpus mathématique figé.")
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    build_corpus(args.output_dir)


if __name__ == "__main__":
    main()
