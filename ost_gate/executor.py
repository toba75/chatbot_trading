"""Exécution Python des nœuds planifiés, sans shell externe."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from ost_gate.models import GateNode, GatePlan, NodeResult


def execute_plan(plan: GatePlan, parallel_workers: int) -> tuple[list[NodeResult], int]:
    """Exécute les niveaux DAG et retourne le premier code d’échec exact."""

    if parallel_workers <= 0:
        raise ValueError("GATE_PARALLEL_WORKERS_INVALID")
    results: list[NodeResult] = []
    first_exit_code = 0
    failed = False
    for level in plan.levels:
        if failed:
            results.extend(_not_run(node, "GATE_DEPENDENCY_PREVIOUSLY_RED") for node in level)
            continue
        parallel_nodes = [node for node in level if node.serial_group == "parallel"]
        serial_groups: dict[str, list[GateNode]] = defaultdict(list)
        for node in level:
            if node.serial_group != "parallel":
                serial_groups[node.serial_group].append(node)
        batches: list[tuple[list[GateNode], int]] = []
        if parallel_nodes:
            batches.append((parallel_nodes, parallel_workers))
        for group in sorted(serial_groups):
            batches.append((serial_groups[group], 1))
        for nodes, workers in batches:
            batch_results, exit_code = _run_batch(plan, nodes, workers)
            results.extend(batch_results)
            if exit_code != 0:
                failed = True
                if first_exit_code == 0:
                    first_exit_code = exit_code
                break
    executed = {result.identifier for result in results}
    for node in plan.nodes:
        if node.identifier not in executed:
            results.append(_not_run(node, "GATE_NOT_EXECUTED"))
    return results, first_exit_code


def _run_batch(
    plan: GatePlan, nodes: list[GateNode], workers: int
) -> tuple[list[NodeResult], int]:
    with tempfile.TemporaryDirectory(prefix="ost_gate_") as temporary_directory_name:
        temporary_directory = Path(temporary_directory_name)
        result_path = temporary_directory / "pytest-results.json"
        expected = {str(node.path): node.identifier for node in nodes}
        timeouts = {node.identifier: node.timeout_seconds for node in nodes}
        environment = os.environ.copy()
        environment["OST_GATE_EXPECTED_NODES"] = json.dumps(expected)
        environment["OST_GATE_TIMEOUTS"] = json.dumps(timeouts)
        environment["OST_GATE_PYTEST_REPORT"] = str(result_path)
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--disable-warnings",
            "--strict-config",
            "--strict-markers",
            "-p",
            "ost_gate.pytest_plugin",
        ]
        if workers > 1 and len(nodes) > 1:
            command.extend(("-n", str(workers)))
        command.extend(str(node.path) for node in nodes)
        completed = subprocess.run(
            command,
            cwd=plan.repository_root,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        detail = _command_detail(completed)
        if not result_path.is_file():
            return [
                NodeResult(
                    identifier=node.identifier,
                    scope=node.scope,
                    phase=node.phase,
                    status="RED",
                    duration_seconds=0.0,
                    executions=1,
                    detail=f"GATE_PYTEST_REPORT_REQUIRED:{detail}",
                )
                for node in nodes
            ], completed.returncode or 1
        try:
            report = json.loads(result_path.read_text(encoding="utf-8"))
            raw_results = report["results"]
        except (json.JSONDecodeError, KeyError, TypeError) as error:
            return [
                NodeResult(
                    identifier=node.identifier,
                    scope=node.scope,
                    phase=node.phase,
                    status="RED",
                    duration_seconds=0.0,
                    executions=1,
                    detail=f"GATE_PYTEST_REPORT_INVALID:{error}",
                )
                for node in nodes
            ], completed.returncode or 1
        results = []
        for node in nodes:
            raw_result = raw_results.get(node.identifier)
            if not isinstance(raw_result, dict):
                results.append(
                    NodeResult(
                        identifier=node.identifier,
                        scope=node.scope,
                        phase=node.phase,
                        status="RED",
                        duration_seconds=0.0,
                        executions=1,
                        detail="GATE_PYTEST_NODE_RESULT_REQUIRED",
                    )
                )
                continue
            status = raw_result.get("status")
            duration = raw_result.get("duration_seconds")
            raw_detail = raw_result.get("detail")
            results.append(
                NodeResult(
                    identifier=node.identifier,
                    scope=node.scope,
                    phase=node.phase,
                    status="GREEN" if status == "GREEN" else "RED",
                    duration_seconds=float(duration) if isinstance(duration, (int, float)) else 0.0,
                    executions=1,
                    detail=None if status == "GREEN" else str(raw_detail or detail),
                )
            )
        return results, completed.returncode


def _not_run(node: GateNode, detail: str) -> NodeResult:
    return NodeResult(
        identifier=node.identifier,
        scope=node.scope,
        phase=node.phase,
        status="NOT_RUN",
        duration_seconds=0.0,
        executions=0,
        detail=detail,
    )


def _command_detail(completed: subprocess.CompletedProcess[str]) -> str:
    output = completed.stderr.strip() or completed.stdout.strip()
    return output[-2000:] if output else f"GATE_PYTEST_EXIT:{completed.returncode}"
