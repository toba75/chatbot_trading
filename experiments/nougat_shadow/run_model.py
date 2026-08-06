from __future__ import annotations

import argparse
import hashlib
import io
import json
import time
from pathlib import Path


MODEL_ID = "facebook/nougat-base"
MODEL_REVISION = "abfecedbb34367c820e233f710fdc7f54e6ab249"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    import torch
    from PIL import Image
    from transformers import NougatProcessor, VisionEncoderDecoderModel

    if not torch.cuda.is_available():
        raise RuntimeError("Cette expérience exige explicitement CUDA")

    manifest_content = args.manifest.read_bytes()
    manifest = json.loads(manifest_content)
    started = time.perf_counter()
    processor = NougatProcessor.from_pretrained(MODEL_ID, revision=MODEL_REVISION)
    model = VisionEncoderDecoderModel.from_pretrained(
        MODEL_ID,
        revision=MODEL_REVISION,
        dtype=torch.float16,
        low_cpu_mem_usage=True,
    ).to("cuda")
    model.eval()
    model_load_seconds = time.perf_counter() - started

    mmd_dir = args.output.parent / "mmd"
    mmd_dir.mkdir(parents=True, exist_ok=True)
    pages = []
    inference_seconds = 0.0
    for page in manifest["pages"]:
        image_path = args.manifest.parent / page["image"]
        image_content = image_path.read_bytes()
        if hashlib.sha256(image_content).hexdigest() != page["image_sha256"]:
            raise ValueError(f"empreinte d'image invalide pour la page {page['page']}")
        with Image.open(io.BytesIO(image_content)) as source:
            pixel_values = processor(
                source.convert("RGB"),
                return_tensors="pt",
                do_crop_margin=True,
                do_resize=True,
                size={"height": 896, "width": 672},
                resample=2,
                do_thumbnail=True,
                do_align_long_axis=False,
                do_pad=True,
                do_rescale=True,
                rescale_factor=1 / 255,
                do_normalize=True,
                image_mean=[0.485, 0.456, 0.406],
                image_std=[0.229, 0.224, 0.225],
            ).pixel_values
        inference_started = time.perf_counter()
        with torch.inference_mode():
            output = model.generate(
                pixel_values.to(device="cuda", dtype=torch.float16),
                min_length=1,
                max_new_tokens=2048,
                bad_words_ids=[[processor.tokenizer.unk_token_id]],
            )
        duration = time.perf_counter() - inference_started
        inference_seconds += duration
        raw = processor.batch_decode(output, skip_special_tokens=True)[0]
        markdown = processor.post_process_generation(raw, fix_markdown=False)
        relative_path = Path("mmd") / f"page-{page['page']:03d}.mmd"
        content = markdown.encode("utf-8")
        (args.output.parent / relative_path).write_bytes(content)
        pages.append(
            {
                "page": page["page"],
                "mmd": relative_path.as_posix(),
                "mmd_sha256": hashlib.sha256(content).hexdigest(),
                "generated_tokens": int(output.shape[1]),
                "inference_seconds": duration,
            }
        )
    result = {
        "model": MODEL_ID,
        "revision": MODEL_REVISION,
        "manifest_sha256": hashlib.sha256(manifest_content).hexdigest(),
        "cuda": True,
        "model_load_seconds": model_load_seconds,
        "inference_seconds": inference_seconds,
        "pages": pages,
    }
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({key: value for key, value in result.items() if key != "pages"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
