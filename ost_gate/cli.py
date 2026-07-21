"""Point d’entrée de la commande canonique `gate`."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

from ost_gate.errors import GateError
from ost_gate.executor import execute_plan
from ost_gate.manifest import load_manifest
from ost_gate.planner import build_plan
from ost_gate.report import write_report


def main(argv: list[str] | None = None) -> int:
    """Exécute une gate complète, ciblée, hors ligne ou liste son plan."""

    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(prog="gate")
    parser.add_argument("--scope")
    activation = parser.add_mutually_exclusive_group()
    activation.add_argument("--offline", action="store_true")
    activation.add_argument("--live", action="store_true", dest="include_live")
    parser.add_argument("--list", action="store_true", dest="list_only")
    parser.add_argument("--manifest", type=Path, default=Path("gate.toml"))
    parser.add_argument("--report", type=Path)
    parser.add_argument("--workers", type=int, default=max(1, min(os.cpu_count() or 1, 8)))
    arguments = parser.parse_args(argv)
    try:
        manifest = load_manifest(arguments.manifest)
        plan = build_plan(
            manifest,
            arguments.scope,
            arguments.offline,
            include_live=arguments.include_live,
        )
        if arguments.list_only:
            for node in plan.nodes:
                print(f"{node.identifier}\t{node.scope}\t{node.phase}\t{node.path.relative_to(manifest.repository_root).as_posix()}")
            return 0
        report_path, transient = _report_path(arguments.report)
        results, exit_code = execute_plan(plan, arguments.workers)
        write_report(report_path, plan, results)
        print(report_path.read_text(encoding="utf-8"), end="")
        if transient:
            report_path.unlink(missing_ok=True)
        if exit_code != 0 or any(result.status != "GREEN" for result in results):
            print("Gate RED" if not plan.partial else "PARTIAL RED", file=sys.stderr)
            return exit_code or 1
        if plan.scope is not None:
            print(f"SCOPE GREEN: {plan.scope}")
        elif plan.offline:
            print("PARTIAL GREEN: offline")
        else:
            print("Gate GREEN")
        return 0
    except GateError as error:
        print(f"Gate RED: {error}", file=sys.stderr)
        return 2


def _report_path(path: Path | None) -> tuple[Path, bool]:
    if path is not None:
        return path.resolve(), False
    descriptor, temporary_name = tempfile.mkstemp(prefix="ost_gate_report_", suffix=".json")
    os.close(descriptor)
    return Path(temporary_name), True


if __name__ == "__main__":
    raise SystemExit(main())
