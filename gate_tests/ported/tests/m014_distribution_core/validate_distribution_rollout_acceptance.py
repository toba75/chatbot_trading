"""Acceptation exécutable de l'exploitation finale M14-distribution-core."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest
import yaml

from app.platform.configuration import (
    ApplicationConfigurationError,
    load_application_configuration,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def test_configuration_cli_runbook_et_gouvernance_sont_coherents(tmp_path: Path) -> None:
    # Given les quatre configurations distribuées, CUDA est obligatoire partout.
    configuration_paths = (
        "config/application.example.yaml",
        "config/environments/development.yaml",
        "config/environments/test.yaml",
        "config/environments/production.yaml",
    )
    for relative_path in configuration_paths:
        payload = yaml.safe_load(
            (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        )
        assert payload["runtime"]["resource_limits"]["gpu_required"] is True
        assert payload["services"]["workers"]["local_distribution"][
            "granite_device"
        ] == "cuda:0"

    invalid_payload = yaml.safe_load(
        (REPOSITORY_ROOT / "config/environments/test.yaml").read_text(
            encoding="utf-8"
        )
    )
    invalid_payload["runtime"]["resource_limits"]["gpu_required"] = False
    invalid_path = tmp_path / "test-gpu-false.yaml"
    invalid_path.write_text(
        yaml.safe_dump(invalid_payload, sort_keys=False), encoding="utf-8"
    )
    with pytest.raises(ApplicationConfigurationError, match="CONFIG_SCHEMA_INVALID"):
        load_application_configuration(invalid_path, {})

    # When le CLI public est exécuté sans les deux variables techniques, il les
    # calcule depuis le commit et la migration canonique du dépôt.
    environment = dict(os.environ)
    environment.pop("OSTRADING_IMAGE_REVISION", None)
    environment.pop("OSTRADING_POSTGRES_SCHEMA_VERSION", None)
    process = subprocess.run(
        (
            "uv",
            "run",
            "--locked",
            "distribution-core",
            "identity",
            "--environment",
            "test",
        ),
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=False,
    )
    assert process.returncode == 0, process.stderr
    identity = json.loads(process.stdout)
    assert identity["schema_version"] == "022"
    assert identity["configuration_hash"] == load_application_configuration(
        REPOSITORY_ROOT / "config/environments/test.yaml", {}
    ).configuration_hash
    assert len(identity["revision"]) == 40

    # Then le code matérialise bien deux phases, un inventaire SQL atomique des
    # trois autorités et le rollback conservateur de la migration 022.
    source = (
        REPOSITORY_ROOT / "app/platform/distribution_operations.py"
    ).read_text(encoding="utf-8")
    for required in (
        "INTERNAL_SERVICE_IDS",
        'PUBLIC_SERVICE_IDS = ("ui", "edge-gateway")',
        "source_processing.job_outbox",
        "knowledge_access.job_outbox",
        "platform.technical_jobs",
        "status IN ('pending', 'relaying')",
        "platform.schema_migrations",
        "platform.document_workers",
        "presence_lease_until > CURRENT_TIMESTAMP",
        "platform.granite_slots",
        "DISTRIBUTION_READY_WORKERS_INVALID",
    ):
        assert required in source

    runbook = (REPOSITORY_ROOT / "docs/runbooks/distribution_locale.md").read_text(
        encoding="utf-8"
    )
    assert "docker compose" not in runbook
    for command in (
        "uv run --locked distribution-core gpu-preflight",
        "uv run --locked distribution-core prepare",
        "uv run --locked distribution-core activate",
        "uv run --locked distribution-core rollback",
        "uv run --locked gate --scope m014_distribution_core --live",
    ):
        assert command in runbook
    for required in (
        "SIGTERM",
        "DRAINING",
        "drain-deadline-seconds",
        "presence_lease_until",
        "port public reste fermé",
    ):
        assert required in runbook

    task = (
        REPOSITORY_ROOT
        / "docs/tasks/milestone_014-distribution-core/0004_migrer_quota_granite_fenced.md"
    ).read_text(encoding="utf-8")
    matrix = (REPOSITORY_ROOT / "docs/traceability/matrix.md").read_text(
        encoding="utf-8"
    )
    live_gate = "uv run --locked gate --scope m014_distribution_core --live"
    assert live_gate in task
    assert live_gate in runbook
    assert live_gate in matrix

    adr_051 = (
        REPOSITORY_ROOT / "docs/adr/ADR-051-execution-granite-cuda-stricte.md"
    ).read_text(encoding="utf-8")
    adr_index = (REPOSITORY_ROOT / "docs/adr/index.md").read_text(encoding="utf-8")
    assert "partiellement remplacée par ADR-052 pour M-014 uniquement" in adr_051
    assert "Partiellement par ADR-052 pour M-014 uniquement" in adr_index
