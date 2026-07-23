"""Scénarios RED de gouvernance issus de la quatrième revue."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


def _assert_traceabilite_attend_preuve_test_et_relit_adr_047_048_050() -> None:
    """Given des rapports STALE, When offline valide, Then aucun statut GREEN n'est publié."""

    from ost_gate.environment_governance import validate_repository_environment_governance

    document = json.loads(
        (ROOT / "docs/governance/m013_environments_traceability.json").read_text(
            encoding="utf-8"
        )
    )
    assert document["submilestone_status"] == "AWAITING_LIVE_EVIDENCE"
    records = {record["requirement_id"]: record for record in document["records"]}
    assert all(
        record["status"] in {"COVERED_OFFLINE", "AWAITING_LIVE_EVIDENCE"}
        for record in records.values()
    )
    assert all(record["status"] != "GREEN" for record in records.values())
    adr_047 = "docs/adr/ADR-047-archive-chiffree-verifiee-avant-preuve-restauration.md"
    adr_048 = "docs/adr/ADR-048-progression-et-parallelisme-dans-profils-explicites.md"
    adr_050 = "docs/adr/ADR-050-separer-qualification-fonctionnelle-et-isolation.md"
    assert adr_047 in records["REQ-M013-ENV-008"]["adrs"]
    for requirement_id in (
        "REQ-M013-ENV-007",
        "REQ-M013-ENV-010",
        "REQ-M013-ENV-012",
    ):
        assert adr_048 in records[requirement_id]["adrs"]
    for requirement_id in (
        "REQ-M013-ENV-003",
        "REQ-M013-ENV-009",
        "REQ-M013-ENV-010",
        "REQ-M013-ENV-011",
        "REQ-M013-ENV-012",
    ):
        assert adr_050 in records[requirement_id]["adrs"]
    evidence = validate_repository_environment_governance(
        repository_root=ROOT,
        require_live_sources=False,
    )
    assert evidence.source == "offline-awaiting-live-evidence"
    assert evidence.execution_count == 0


def _assert_readme_compose_historique_est_deprecie_et_gouverne() -> None:
    """Given l'ancien Compose, When sa documentation est lue, Then elle redirige sans ambiguïté."""

    readme = (ROOT / "deploy/local-compose/README.md").read_text(encoding="utf-8")
    governance = (ROOT / "ost_gate/environment_governance.py").read_text(encoding="utf-8")
    assert "DÉPRÉCIÉ" in readme.upper()
    assert "uv run development" in readme
    assert "uv run test" in readme
    assert "uv run production" in readme
    assert "docs/runbooks/environnements_explicites.md" in readme
    assert "deploy/local-compose/README.md" in governance


def _assert_index_documentation_reference_contrat_backup_1_1_reel() -> None:
    """Given ADR-047, When l'index est lu, Then les vraies commandes et tests sont indexés."""

    index = (ROOT / "docs/governance/m013_documentation_index.md").read_text(
        encoding="utf-8"
    )
    backup_row = next(
        line
        for line in index.splitlines()
        if line.startswith("| docs/runbooks/sauvegarde_restauration.md ")
    )
    for token in (
        "backup-v1",
        "restore-v1",
        "M013-BackupManifest-1.1",
        "validate_backup_restore_runtime_unit.py",
        "validate_backup_restore_compose_live.py",
    ):
        assert token in backup_row
    assert "scripts\\backup_v1" not in backup_row
    assert "m013_backup_restore_drill.md" not in backup_row


def _assert_prochaine_adr_est_051() -> None:
    """Given ADR-050 présente, When l'index réserve le suivant, Then il annonce ADR-051."""

    index = (ROOT / "docs/adr/index.md").read_text(encoding="utf-8")
    assert "Prochaine ADR technique: ADR-051" in index
    assert "Prochaine ADR technique: ADR-050" not in index


def _assert_runbook_documente_import_ca_windows_explicite_et_reversible() -> None:
    """Given une CA Caddy exportée, When Windows lui fait confiance, Then le retrait est documenté."""

    runbook = (ROOT / "docs/runbooks/environnements_explicites.md").read_text(
        encoding="utf-8"
    )
    for token in (
        "Import-Certificate",
        "Cert:\\CurrentUser\\Root",
        "Thumbprint",
        "Remove-Item",
        "jamais automatiquement",
        "révocation",
    ):
        assert token in runbook


def _assert_tests_revue4_sont_enroles_dans_la_gate() -> None:
    """Given les garde-fous revue 4, When la gate est lue, Then ils sont obligatoires offline."""

    manifest = (ROOT / "gate.toml").read_text(encoding="utf-8")
    for path in (
        "gate_tests/ported/tests/m013_environments/validate_review4_runtime_integrity_unit.py",
        "gate_tests/ported/tests/m013_environments/validate_review4_governance_unit.py",
    ):
        assert manifest.count(f'path = "{path}"') == 1


def test_gouvernance_de_la_revue4() -> None:
    """Given les findings revue 4, When la gouvernance est lue, Then ils sont fermés."""

    _assert_traceabilite_attend_preuve_test_et_relit_adr_047_048_050()
    _assert_readme_compose_historique_est_deprecie_et_gouverne()
    _assert_index_documentation_reference_contrat_backup_1_1_reel()
    _assert_prochaine_adr_est_051()
    _assert_runbook_documente_import_ca_windows_explicite_et_reversible()
    _assert_tests_revue4_sont_enroles_dans_la_gate()
