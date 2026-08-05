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
    parser.add_argument("--model", default="PP-FormulaNet_plus-L")
    parser.add_argument("--device", default="gpu:0")
    parser.add_argument("--batch-size", type=int, default=1)
    args = parser.parse_args()

    import paddle
    from paddleocr import FormulaRecognition

    if not args.device.startswith("gpu"):
        raise RuntimeError("Cette expérience exige explicitement CUDA")
    if not paddle.device.is_compiled_with_cuda() or paddle.device.cuda.device_count() < 1:
        raise RuntimeError("CUDA indisponible dans le conteneur Paddle")

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    paths = [args.manifest.parent / record["image"] for record in manifest["records"]]

    started = time.perf_counter()
    model = FormulaRecognition(model_name=args.model, device=args.device)
    model_load_seconds = time.perf_counter() - started

    inference_started = time.perf_counter()
    outputs = model.predict(input=[str(path) for path in paths], batch_size=args.batch_size)
    results = []
    for record, output in zip(manifest["records"], outputs, strict=True):
        payload = result_payload(output)
        results.append(
            {
                "region_id": record["region_id"],
                "rec_formula": payload["rec_formula"],
            }
        )
    inference_seconds = time.perf_counter() - inference_started

    result = {
        "model": args.model,
        "device": args.device,
        "batch_size": args.batch_size,
        "paddle_version": paddle.__version__,
        "paddleocr_version": importlib.metadata.version("paddleocr"),
        "cuda_available": True,
        "model_load_seconds": model_load_seconds,
        "inference_seconds": inference_seconds,
        "results": results,
    }
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({key: value for key, value in result.items() if key != "results"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
