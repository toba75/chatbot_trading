"""Acceptation des preuves opératoires et reproductibles M14-distribution-core."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
POSTGRES_DIGEST = (
    "postgres@sha256:7e5df973a74872482e320dcbdeb055e178d6f42de0558b083892c50cda833c96"
)


def test_distribution_locale_exploitable_reproductible_et_tracable() -> None:
    # Given M14 exige exactement deux workers 2 Gio/4 CPU et le seul GPU 0.
    for relative_path in (
        "deploy/environments/compose.base.yaml",
        "deploy/local-compose/compose.yaml",
    ):
        compose = yaml.safe_load(
            (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        )
        worker = compose["services"]["worker-documents"]
        deploy = worker["deploy"]
        limits = deploy["resources"]["limits"]
        reservations = deploy["resources"]["reservations"]
        assert deploy["replicas"] == 2
        assert str(limits["memory"]) == "2G"
        assert str(limits["cpus"]) == "4.0"
        assert worker.get("gpus") is None
        assert reservations["devices"] == [
            {
                "driver": "nvidia",
                "device_ids": ["0"],
                "capabilities": ["gpu"],
            }
        ]

    render_environment = dict(os.environ)
    render_environment.update(
        {
            "CADDY_ADMIN": "127.0.0.1:2019",
            "OST_EDGE_HTTPS_PORT": "18443",
            "OSTRADING_IMAGE_REVISION": "a" * 40,
            "OSTRADING_POSTGRES_SCHEMA_VERSION": "022",
        }
    )
    rendered_process = subprocess.run(
        (
            "docker",
            "compose",
            "--project-directory",
            str(REPOSITORY_ROOT / "deploy/local-compose"),
            "--file",
            str(REPOSITORY_ROOT / "deploy/local-compose/compose.yaml"),
            "config",
            "--format",
            "json",
        ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=False,
        cwd=REPOSITORY_ROOT,
        env=render_environment,
    )
    assert rendered_process.returncode == 0, rendered_process.stderr
    rendered_worker = json.loads(rendered_process.stdout)["services"][
        "worker-documents"
    ]
    rendered_deploy = rendered_worker["deploy"]
    assert rendered_deploy["replicas"] == 2
    assert rendered_deploy["resources"]["limits"] == {
        "cpus": 4,
        "memory": "2147483648",
        "pids": 256,
    }
    assert rendered_deploy["resources"]["reservations"]["devices"] == [
        {
            "capabilities": ["gpu"],
            "device_ids": ["0"],
            "driver": "nvidia",
        }
    ]

    # When l'image worker est reconstruite, ses paquets système sont immuables.
    dockerfile = (REPOSITORY_ROOT / "deploy/local-compose/Dockerfile").read_text(
        encoding="utf-8"
    )
    assert "snapshot.debian.org/archive/debian/20250203T000000Z" in dockerfile
    assert "snapshot.debian.org/archive/debian-security/20250203T000000Z" in dockerfile
    assert "gcc=4:12.2.0-3" in dockerfile
    assert "libc6-dev=2.36-9+deb12u9" in dockerfile
    assert "apt-get install -y --no-install-recommends gcc libc6-dev" not in dockerfile

    # Then la preuve PostgreSQL live réutilise la référence digérée centrale.
    central_images = (REPOSITORY_ROOT / "app/platform/ui_local_stack.py").read_text(
        encoding="utf-8"
    )
    live_support = (REPOSITORY_ROOT / "gate_tests/live_support.py").read_text(
        encoding="utf-8"
    )
    quota_live = (
        REPOSITORY_ROOT
        / "gate_tests/ported/tests/m014_distribution_core/validate_granite_quota_live.py"
    ).read_text(encoding="utf-8")
    assert "LOCAL_POSTGRES_IMAGE = (" in central_images
    assert POSTGRES_DIGEST in central_images
    assert (
        "from app.platform.ui_local_stack import LOCAL_POSTGRES_IMAGE" in live_support
    )
    assert "from app.platform.ui_local_stack import LOCAL_POSTGRES_IMAGE" in quota_live
    assert '"postgres:16-alpine"' not in quota_live

    # Le schéma porte seul les constantes fixes; Python conserve les invariants relationnels utiles.
    configuration_source = (
        REPOSITORY_ROOT / "app/platform/configuration/__init__.py"
    ).read_text(encoding="utf-8")
    assert (
        "la capacité Granite globale doit être le produit" not in configuration_source
    )

    # Le runbook bloque toute bascule tant que l'ancien hash possède un job actif.
    runbook_path = REPOSITORY_ROOT / "docs/runbooks/distribution_locale.md"
    assert runbook_path.is_file()
    runbook = runbook_path.read_text(encoding="utf-8")
    for required in (
        "arrêter les admissions",
        "configuration_hash",
        "status IN ('pending', 'running')",
        "zéro job",
        "WORKER_ENVIRONMENT_MISMATCH",
        "nvidia-smi",
        "cuda:0",
        "GRANITE_CUDA_UNAVAILABLE",
        "aucun fallback",
        "uv run --locked gate --scope m014_distribution_core --live",
        "Docker",
    ):
        assert required in runbook

    # La spécification M13 reflète la limite M14 et les quatre exigences sont reliées.
    m13_spec = (
        REPOSITORY_ROOT / "docs/specs/m013_environments_environnements_explicites.md"
    ).read_text(encoding="utf-8")
    assert "conservent une limite de 8 Gio" not in m13_spec
    assert m13_spec.count("2 Gio") >= 2
    assert "M14-distribution-core" in m13_spec

    matrix = (REPOSITORY_ROOT / "docs/traceability/matrix.md").read_text(
        encoding="utf-8"
    )
    for requirement in (
        "REQ-M014-CORE-001",
        "REQ-M014-CORE-002",
        "REQ-M014-CORE-003",
        "REQ-M014-CORE-004",
    ):
        assert matrix.count(f"| {requirement} |") == 1
    for required in (
        "docs/runbooks/distribution_locale.md",
        "docs/specs/m013_environments_environnements_explicites.md",
        "ADR-051",
        "ADR-052",
        "uv run --locked gate --scope m014_distribution_core --live",
    ):
        assert required in matrix
