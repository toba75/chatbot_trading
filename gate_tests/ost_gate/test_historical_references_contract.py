from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

import pytest

from ost_gate.historical_references import HistoricalReferenceError
from ost_gate.historical_references import reconcile_historical_allowlist
from ost_gate.historical_references import validate_historical_references


_CLOSED_HISTORICAL_CATALOGUE_SHA256 = (
    "50a8dce26ffe13a4bf1b18793671bb9631d3cf18644e48ec5c7a8955b42a52a6"
)


def test_historical_references_are_closed_and_immutable() -> None:
    repository_root = Path(__file__).resolve().parents[2]

    validate_historical_references(repository_root)
    _assert_historical_allowlist_catalogue_is_closed(repository_root)
    with TemporaryDirectory() as temporary_directory:
        _assert_allowlist_uses_index_content_across_crlf_and_rejects_semantic_edit(
            Path(temporary_directory)
        )
    with TemporaryDirectory() as temporary_directory:
        _assert_reconciliation_preserves_the_closed_catalogue(
            Path(temporary_directory)
        )


def test_local_runtime_assets_are_not_historical_sources(tmp_path: Path) -> None:
    repository_root = tmp_path / "repository"
    allowlist_path = (
        repository_root
        / "docs"
        / "governance"
        / "historical_reference_allowlist.json"
    )
    runtime_asset = (
        repository_root
        / "data"
        / "docling_assets"
        / "granite"
        / "tokenizer.json"
    )
    historical_source = repository_root / "docs" / "adr" / "legacy.md"
    historical_content = b"# Decision historique\n\nPowerShell reste archive.\n"
    allowlist_path.parent.mkdir(parents=True)
    runtime_asset.parent.mkdir(parents=True)
    historical_source.parent.mkdir(parents=True)
    historical_source.write_bytes(historical_content)
    allowlist_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "allowed_paths": [
                    {
                        "path": "docs/adr/legacy.md",
                        "reason": "preuve historique",
                        "sha256": hashlib.sha256(historical_content).hexdigest(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    runtime_asset.write_text(
        '{"metadata": "PowerShell runtime asset"}',
        encoding="utf-8",
    )
    _run_git(repository_root, "init", "--quiet")
    _run_git(repository_root, "config", "core.autocrlf", "false")
    _run_git(repository_root, "add", "docs")

    validate_historical_references(repository_root)


def _assert_allowlist_uses_index_content_across_crlf_and_rejects_semantic_edit(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repository"
    source_path = repository_root / "docs" / "adr" / "legacy.md"
    allowlist_path = (
        repository_root
        / "docs"
        / "governance"
        / "historical_reference_allowlist.json"
    )
    indexed_content = (
        b"# Decision historique\n\n"
        + b"Power"
        + b"Shell reste une preuve historique.\n"
    )

    source_path.parent.mkdir(parents=True)
    allowlist_path.parent.mkdir(parents=True)
    source_path.write_bytes(indexed_content)
    allowlist_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "allowed_paths": [
                    {
                        "path": "docs/adr/legacy.md",
                        "reason": "preuve historique",
                        "sha256": hashlib.sha256(indexed_content).hexdigest(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    _run_git(repository_root, "init", "--quiet")
    _run_git(repository_root, "config", "core.autocrlf", "false")
    _run_git(repository_root, "add", "docs")

    source_path.write_bytes(indexed_content.replace(b"\n", b"\r\n"))

    validate_historical_references(repository_root)

    source_path.write_bytes(
        b"# Decision historique\r\n\r\n"
        + b"Power"
        + b"Shell devient une preuve modifiee.\r\n"
    )

    with pytest.raises(
        HistoricalReferenceError,
        match="GATE_HISTORICAL_ALLOWLIST_HASH_MISMATCH:docs/adr/legacy.md",
    ):
        validate_historical_references(repository_root)


def _assert_reconciliation_preserves_the_closed_catalogue(tmp_path: Path) -> None:
    repository_root = tmp_path / "repository"
    source_path = repository_root / "docs" / "adr" / "legacy.md"
    allowlist_path = (
        repository_root
        / "docs"
        / "governance"
        / "historical_reference_allowlist.json"
    )
    indexed_content = (
        b"# Decision historique\n\n"
        + b"Power"
        + b"Shell reste une preuve historique.\n"
    )

    source_path.parent.mkdir(parents=True)
    allowlist_path.parent.mkdir(parents=True)
    source_path.write_bytes(indexed_content)
    allowlist_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "allowed_paths": [
                    {
                        "path": "docs/adr/legacy.md",
                        "reason": "preuve historique",
                        "sha256": "0" * 64,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    _run_git(repository_root, "init", "--quiet")
    _run_git(repository_root, "config", "core.autocrlf", "false")
    _run_git(repository_root, "add", "docs")

    before = _catalogue(repository_root)
    reconciled_count = reconcile_historical_allowlist(repository_root)

    assert reconciled_count == 1
    assert _catalogue(repository_root) == before
    validate_historical_references(repository_root)


def _assert_historical_allowlist_catalogue_is_closed(repository_root: Path) -> None:
    catalogue = _catalogue(repository_root)
    serialised_catalogue = json.dumps(
        catalogue,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    assert (
        hashlib.sha256(serialised_catalogue).hexdigest()
        == _CLOSED_HISTORICAL_CATALOGUE_SHA256
    )


def _catalogue(repository_root: Path) -> list[dict[str, str]]:
    allowlist_path = (
        repository_root
        / "docs"
        / "governance"
        / "historical_reference_allowlist.json"
    )
    document = json.loads(allowlist_path.read_text(encoding="utf-8"))
    return [
        {"path": record["path"], "reason": record["reason"]}
        for record in document["allowed_paths"]
    ]


def _run_git(repository_root: Path, *arguments: str) -> None:
    subprocess.run(
        ("git", *arguments),
        cwd=repository_root,
        check=True,
        capture_output=True,
    )
