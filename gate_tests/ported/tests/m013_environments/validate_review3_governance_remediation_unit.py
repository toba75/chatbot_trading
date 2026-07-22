"""Garde-fous de gouvernance issus de la troisième revue M13-environments."""

from __future__ import annotations

from copy import deepcopy
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def _repository_root() -> Path:
    return next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )


def test_review3_governance_remediation_unit(monkeypatch, tmp_path: Path) -> None:
    """Given les profils explicites, When la gouvernance est relue, Then aucune preuve obsolète ne devient GREEN."""

    from app.platform import environment_compose
    from app.platform.development_e2e import _public_client
    from ost_gate.environment_governance import (
        EXPECTED_LIVE_CONTAINER_COUNT,
        EXPECTED_LIVE_WORKER_IDENTITY_COUNT,
        assert_no_active_environment_entrypoint_contradictions,
        validate_execution_evidence,
        validate_repository_environment_governance,
    )

    root = _repository_root()
    assert EXPECTED_LIVE_WORKER_IDENTITY_COUNT == 4
    assert EXPECTED_LIVE_CONTAINER_COUNT == 14

    offline = validate_repository_environment_governance(
        repository_root=root,
        require_live_sources=False,
    )
    assert offline.execution_count == 0
    assert offline.source == "offline-awaiting-live-evidence"

    evidence = json.loads(
        (root / "docs/governance/m013_environments_execution_evidence.json").read_text(
            encoding="utf-8"
        )
    )
    assert evidence["schema_version"] == 2
    assert evidence["evidence_status"] == "STALE"
    assert evidence["evidence_kind"] == "HISTORICAL_STACK_EXECUTION"
    assert evidence["current_runtime"] == {
        "worker_identity_count": 4,
        "container_count": 14,
    }
    assert "reports" not in evidence
    assert set(evidence["historical_reports"]) == {"development", "test", "production"}

    reports = {"test": deepcopy(evidence["historical_reports"]["test"])}
    reports["test"]["source_pdf_path"] = (
        "data/corpus/ostrading-environment-qualification-5-pages.pdf"
    )
    for run in reports["test"]["runs"]:
        run["worker_identity_count"] = 4
        run["container_count"] = 14
        run["https_ca_verified"] = True
        run["caddy_ca_sha256"] = "c" * 64
        run["qualification_routes"] = [
            "NATIVE_STANDARD",
            "MIXED_PAGEWISE",
            "PREPROCESS_GRANITE",
            "TARGETED_ENRICHMENT",
            "SKIP_EMPTY",
        ]
    validate_execution_evidence(reports)
    reports["test"]["runs"][0]["container_count"] = 13
    with pytest.raises(ValueError, match="LIVE_EVIDENCE_CONTAINERS_INCOMPLETE"):
        validate_execution_evidence(reports)

    adr_031 = (root / "docs/adr/ADR-031-actions-ui-execution-et-progression-publique.md").read_text(encoding="utf-8")
    adr_037 = (root / "docs/adr/ADR-037-parallelisme-documentaire-projection.md").read_text(encoding="utf-8")
    adr_048 = (root / "docs/adr/ADR-048-progression-et-parallelisme-dans-profils-explicites.md").read_text(encoding="utf-8")
    assert "**Statut :** Remplacée" in adr_031
    assert "**Remplacée par :** ADR-048" in adr_031
    assert "**Statut :** Remplacée" in adr_037
    assert "**Remplacée par :** ADR-048" in adr_037
    assert "**Statut :** Acceptée" in adr_048
    assert "**Remplace :** ADR-031 ; ADR-037" in adr_048

    active_documents = {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in (
            root / "docs/runbooks/configuration_applicative.md",
            root / "docs/runbooks/api_orchestratrice.md",
            root / "docs/governance/m013_documentation_index.md",
            root / "docs/adr/index.md",
        )
    }
    assert_no_active_environment_entrypoint_contradictions(active_documents)
    contradicted = dict(active_documents)
    contradicted["docs/runbooks/actif.md"] = "Démarrer avec uv run ui"
    with pytest.raises(ValueError, match="ACTIVE_ENVIRONMENT_ENTRYPOINT_CONTRADICTION"):
        assert_no_active_environment_entrypoint_contradictions(contradicted)

    calls: list[tuple[str, ...]] = []

    def compose_copy(_definition, arguments, **_kwargs):
        calls.append(tuple(arguments))
        destination = Path(arguments[-1])
        destination.write_text(
            "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n",
            encoding="ascii",
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(environment_compose, "_run_compose", compose_copy)
    monkeypatch.setattr(
        environment_compose.x509,
        "load_pem_x509_certificate",
        lambda _content: object(),
    )
    exported = environment_compose.export_environment_caddy_ca(
        environment="development",
        repository_root=root,
        destination_path=tmp_path / "development-caddy-root.crt",
        technical_environment={
            "OSTRADING_IMAGE_REVISION": "a" * 40,
            "OSTRADING_POSTGRES_SCHEMA_VERSION": "021",
        },
    )
    assert exported == tmp_path / "development-caddy-root.crt"
    assert calls == [
        (
            "cp",
            "edge-gateway:/data/caddy/pki/authorities/local/root.crt",
            str(exported),
        )
    ]

    client_source = inspect.getsource(_public_client)
    assert "verify=False" not in client_source
    assert "ca_bundle_path" in inspect.signature(_public_client).parameters

    deploy_readme = (root / "deploy/environments/README.md").read_text(encoding="utf-8")
    assert "seul le cycle `test` propriétaire" in deploy_readme.casefold()
    assert "`development` et `production` conservent" in deploy_readme
