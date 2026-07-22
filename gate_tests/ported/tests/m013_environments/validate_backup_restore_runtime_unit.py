from __future__ import annotations

from hashlib import sha256
import inspect
import json
from pathlib import Path

import pytest


_ARTIFACTS = (
    ("SP", "corpus_original", "SRC-ARCHIVE-001", True, True, False, False),
    ("SP", "canonical_versions", "CANON-ARCHIVE-001", True, True, False, False),
    ("KA", "qdrant_projection", "PROJ-ARCHIVE-001", False, False, True, False),
    ("EG", "claim_registry", "CLAIM-ARCHIVE-001", True, True, False, True),
    ("RA", "verified_answers", "ANSWER-ARCHIVE-001", True, True, False, True),
    ("CV", "conversation_turns", "TURN-ARCHIVE-001", True, True, False, False),
    ("SD", "strategy_snapshots", "STRATEGY-ARCHIVE-001", True, True, False, True),
    ("EX", "experiment_results", "EXPERIMENT-ARCHIVE-001", True, True, False, True),
    ("EV", "evaluation_reports", "EVALUATION-ARCHIVE-001", True, True, False, True),
    ("platform", "governance_artifacts", "GOVERNANCE-ARCHIVE-001", True, True, False, False),
)


def test_backup_restore_runtime_unit(tmp_path: Path) -> None:
    """Given une archive réelle, When elle est vérifiée/restaurée, Then aucun GREEN déclaratif n'est possible."""

    from app.platform.configured_datastore_identity import APPLICATION_FILE_ROOT_NAMES
    from ost_gate.operations import backup
    from ost_gate.operations.backup_manifest import read_backup_manifest
    from ost_gate.operations.encrypted_archive import (
        BackupArchiveEntry,
        archive_entry_sha256,
        build_encrypted_archive,
        load_archive_material,
        verify_encrypted_archive,
    )
    from ost_gate.operations.restore import restore_verified_archive

    assert APPLICATION_FILE_ROOT_NAMES == (
        "data_root",
        "corpus_root",
        "canonical_sources_root",
        "reports_root",
        "logs_root",
        "experiments_root",
        "cache_root",
    )
    assert "qdrant_storage_root" not in APPLICATION_FILE_ROOT_NAMES
    assert "postgres_data_root" not in APPLICATION_FILE_ROOT_NAMES

    entries = tuple(
        BackupArchiveEntry(
            entry_id=f"ENTRY-{index:02d}",
            context=context,
            artifact_kind=artifact_kind,
            stable_identifier=stable_identifier,
            authority=authority,
            immutable=immutable,
            regenerable_projection=regenerable_projection,
            retained_negative_or_superseded=retained,
            payload=f"octets-réels-{stable_identifier}".encode(),
        )
        for index, (
            context,
            artifact_kind,
            stable_identifier,
            authority,
            immutable,
            regenerable_projection,
            retained,
        ) in enumerate(_ARTIFACTS, start=1)
    )
    key = bytes(range(32))
    archive = build_encrypted_archive(
        entries=entries,
        encryption_key=key,
        nonce=bytes(range(12)),
    )
    archive_path = tmp_path / "backup.m013.aesgcm"
    key_path = tmp_path / "backup.key"
    archive_path.write_bytes(archive)
    key_path.write_bytes(key)
    manifest_path = _write_manifest(
        tmp_path / "manifest.json",
        archive=archive,
        entries=entries,
    )

    manifest = read_backup_manifest(manifest_path, "backup")
    material = load_archive_material(archive_path=archive_path, key_path=key_path)
    verified = verify_encrypted_archive(manifest=manifest, material=material)
    assert tuple(item.stable_identifier for item in verified.entries) == tuple(
        item.stable_identifier for item in entries
    )
    assert all(
        item.sha256 == archive_entry_sha256(expected)
        for item, expected in zip(verified.entries, entries, strict=True)
    )

    target = tmp_path / "restore-drills" / "unit"
    restore_verified_archive(manifest=manifest, verified_archive=verified, target=target)
    proof = json.loads((target / "restore-proof.json").read_text(encoding="utf-8"))
    assert proof["restore_test_result"] == "GREEN"
    assert proof["verified_hashes"] is True
    assert proof["stable_identifiers_preserved"] is True
    assert proof["immutable_artifacts_preserved"] is True
    assert proof["negative_and_superseded_available"] is True
    assert len(tuple((target / "entries").glob("*.json"))) == len(entries)

    altered_path = tmp_path / "altered.aesgcm"
    altered = bytearray(archive)
    altered[-1] ^= 1
    altered_path.write_bytes(altered)
    with pytest.raises(ValueError, match="ARCHIVE_CIPHERTEXT_HASH_MISMATCH"):
        verify_encrypted_archive(
            manifest=manifest,
            material=load_archive_material(archive_path=altered_path, key_path=key_path),
        )

    wrong_key_path = tmp_path / "wrong.key"
    wrong_key_path.write_bytes(bytes(reversed(range(32))))
    with pytest.raises(ValueError, match="ARCHIVE_DECRYPTION_FAILED"):
        verify_encrypted_archive(
            manifest=manifest,
            material=load_archive_material(archive_path=archive_path, key_path=wrong_key_path),
        )

    with pytest.raises(ValueError, match="ARCHIVE_REQUIRED"):
        load_archive_material(archive_path=tmp_path / "absent", key_path=key_path)
    with pytest.raises(ValueError, match="ARCHIVE_KEY_REQUIRED"):
        load_archive_material(archive_path=archive_path, key_path=tmp_path / "absent.key")

    # Le wrapper réutilise exactement le calcul de révision/schéma du lanceur et
    # transporte les trois fichiers sur stdin, sans valeur de clé dans argv/env.
    wrapper_source = inspect.getsource(backup.execute_compose_storage_command)
    assert "_technical_environment_from_repository" in wrapper_source
    assert "_compose_process_environment" in wrapper_source
    assert "encode_compose_payload" in wrapper_source
    assert '"run"' in wrapper_source
    assert '"--no-deps"' in wrapper_source
    assert "key_document" not in wrapper_source


def _write_manifest(
    path: Path,
    *,
    archive: bytes,
    entries: tuple[object, ...],
) -> Path:
    document = {
        "contract_version": "M013-BackupManifest-1.1",
        "manifest_id": "M013-BACKUP-ARCHIVE-UNIT",
        "environment": "test",
        "deployment_id": "ostrading-test-ci",
        "backup_command": "uv run backup-v1 --manifest manifest.json --archive backup.m013.aesgcm --key-file backup.key --config config/environments/test.yaml",
        "restore_command": "uv run restore-v1 --manifest manifest.json --archive backup.m013.aesgcm --key-file backup.key --target data/environments/test/reports/restore-drills/unit --config config/environments/test.yaml",
        "restore_target": "local_isolated",
        "archive_encrypted": True,
        "archive_format": "M013-AES256GCM-TAR-1.0",
        "ciphertext_sha256": sha256(archive).hexdigest(),
        "key_reference": "hors_depot://test/backup.key",
        "key_git_tracked": False,
        "complete": True,
        "entries": [
            {
                "entry_id": entry.entry_id,
                "context": entry.context,
                "artifact_kind": entry.artifact_kind,
                "stable_identifier": entry.stable_identifier,
                "archive_member": f"entries/{entry.entry_id}.json",
                "storage_host": "docker-local",
                "authority": entry.authority,
                "immutable": entry.immutable,
                "regenerable_projection": entry.regenerable_projection,
                "retained_negative_or_superseded": entry.retained_negative_or_superseded,
                "backup_sha256": archive_entry_sha256(entry),
                "contains_plain_secret": False,
                "git_tracked_key_material": False,
                "spark_business_storage": False,
                "destructive_restore": False,
            }
            for entry in entries
        ],
    }
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
