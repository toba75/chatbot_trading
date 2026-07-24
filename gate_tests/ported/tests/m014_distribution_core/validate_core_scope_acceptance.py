"""Acceptation du périmètre strict de M14-distribution-core."""

from __future__ import annotations

from pathlib import Path
import tomllib

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def test_m014_core_ne_publie_aucune_operation_reservee_a_t009() -> None:
    # Given M14-distribution-core couvre uniquement T-001 à T-004.
    operations_module = REPOSITORY_ROOT / "app/platform/distribution_operations.py"
    pyproject = tomllib.loads(
        (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    gate = tomllib.loads((REPOSITORY_ROOT / "gate.toml").read_text(encoding="utf-8"))

    # When les surfaces publiques et les preuves du milestone sont inspectées.
    assert not operations_module.exists()
    assert "distribution-core" not in pyproject["project"]["scripts"]

    forbidden_tests = {
        "validate_distribution_operations_acceptance.py",
        "validate_distribution_rollout_acceptance.py",
        "validate_distribution_rollout_unit.py",
    }
    m014_nodes = [
        node for node in gate["nodes"] if node["scope"] == "m014_distribution_core"
    ]

    # Then aucune commande d'inspection, drainage ou redémarrage T-009 n'est publiée.
    assert forbidden_tests.isdisjoint(Path(node["path"]).name for node in m014_nodes)
    for filename in forbidden_tests:
        assert not (
            REPOSITORY_ROOT
            / "gate_tests/ported/tests/m014_distribution_core"
            / filename
        ).exists()


def test_runbook_reste_un_protocole_m14_core_sans_cli_t009() -> None:
    # Given les opérations publiques appartiennent à M14-local-qualification T-009.
    runbook = (REPOSITORY_ROOT / "docs/runbooks/distribution_locale.md").read_text(
        encoding="utf-8"
    )

    # When l'exploitant consulte le protocole M14-core.
    assert "M14-local-qualification" in runbook
    assert "T-009" in runbook
    assert "migration 022" in runbook
    assert "ascendante" in runbook

    # Then le runbook ne promet aucune commande prématurée et cible la gate canonique.
    assert "uv run --locked distribution-core" not in runbook
    assert "uv run --locked gate --scope config" not in runbook
    assert "uv run --locked gate --scope m013_config" in runbook


def test_configuration_compose_locale_exige_le_gpu() -> None:
    # Given la pile locale exécute Granite exclusivement sur cuda:0.
    configuration = yaml.safe_load(
        (
            REPOSITORY_ROOT / "deploy/local-compose/application.compose.yaml"
        ).read_text(encoding="utf-8")
    )

    # When la configuration versionnée de Compose est chargée.
    gpu_required = configuration["runtime"]["resource_limits"]["gpu_required"]

    # Then aucun démarrage CPU ou fallback matériel n'est autorisé.
    assert gpu_required is True
