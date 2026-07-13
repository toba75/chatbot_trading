from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from ost_gate.historical_references import HistoricalReferenceError
from ost_gate.historical_references import validate_historical_references


def test_historical_references_are_closed_and_immutable() -> None:
    validate_historical_references(Path(__file__).resolve().parents[2])


def test_historical_allowlist_uses_index_content_across_crlf_and_rejects_semantic_edit(
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
    indexed_content = b"# Decision historique\n\nPowerShell reste une preuve historique.\n"

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
        b"# Decision historique\r\n\r\nPowerShell devient une preuve modifiee.\r\n"
    )

    with pytest.raises(
        HistoricalReferenceError,
        match="GATE_HISTORICAL_ALLOWLIST_HASH_MISMATCH:docs/adr/legacy.md",
    ):
        validate_historical_references(repository_root)


def _run_git(repository_root: Path, *arguments: str) -> None:
    subprocess.run(
        ("git", *arguments),
        cwd=repository_root,
        check=True,
        capture_output=True,
    )
