from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.paddle_formula_spike.picture_experiment import evaluate, prepare


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    for name in ("pdf", "docling", "corrections", "report", "output"):
        prepare_parser.add_argument(f"--{name}", type=Path, required=True)
    prepare_parser.add_argument("--dpi", type=int, default=300)
    evaluate_parser = subparsers.add_parser("evaluate")
    for name in ("manifest", "predictions", "output"):
        evaluate_parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "prepare":
        result = prepare(
            args.pdf,
            args.docling,
            args.corrections,
            args.report,
            args.output,
            dpi=args.dpi,
        )
        print(f"{len(result['pictures'])} pictures, {result['regions']} regions")
    else:
        result = evaluate(args.manifest, args.predictions, args.output)
        print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
