from __future__ import annotations

import argparse
import importlib.metadata
import json
import time
from pathlib import Path
from typing import Any


def result_payload(result: Any) -> dict[str, Any]:
    payload = result.json
    if isinstance(payload, str):
        payload = json.loads(payload)
    return payload.get("res", payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="gpu:0")
    parser.add_argument("--orientation", action="store_true")
    args = parser.parse_args()

    import paddle
    from paddleocr import PPStructureV3

    if not args.device.startswith("gpu"):
        raise RuntimeError("Cette expérience exige explicitement CUDA")
    if (
        not paddle.device.is_compiled_with_cuda()
        or paddle.device.cuda.device_count() < 1
    ):
        raise RuntimeError("CUDA indisponible dans le conteneur Paddle")

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    started = time.perf_counter()
    pipeline = PPStructureV3(
        layout_detection_model_name="PP-DocLayout_plus-L",
        formula_recognition_model_name="PP-FormulaNet_plus-L",
        formula_recognition_batch_size=1,
        device=args.device,
        lang="en",
        use_doc_orientation_classify=args.orientation,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        use_seal_recognition=False,
        use_table_recognition=False,
        use_formula_recognition=True,
        use_chart_recognition=False,
        use_region_detection=False,
    )
    model_load_seconds = time.perf_counter() - started

    inference_started = time.perf_counter()
    pictures = []
    for picture in manifest["pictures"]:
        picture_started = time.perf_counter()
        outputs = pipeline.predict(str(args.manifest.parent / picture["image"]))
        payloads = [result_payload(output) for output in outputs]
        if len(payloads) != 1:
            raise RuntimeError(f"Résultat inattendu pour {picture['picture_ref']}")
        pictures.append(
            {
                "picture_ref": picture["picture_ref"],
                "page": picture["page"],
                "inference_seconds": time.perf_counter() - picture_started,
                "result": payloads[0],
            }
        )

    result = {
        "layout_model": "PP-DocLayout_plus-L",
        "formula_model": "PP-FormulaNet_plus-L",
        "device": args.device,
        "orientation": args.orientation,
        "paddle_version": paddle.__version__,
        "paddleocr_version": importlib.metadata.version("paddleocr"),
        "cuda_available": True,
        "model_load_seconds": model_load_seconds,
        "inference_seconds": time.perf_counter() - inference_started,
        "pictures": pictures,
    }
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps({key: value for key, value in result.items() if key != "pictures"})
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
