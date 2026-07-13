from __future__ import annotations

from pathlib import Path

from ost_gate.errors import ManifestError
from ost_gate.manifest import load_manifest


def test_manifest_refuses_empty_duplicate_and_external_nodes(tmp_path: Path) -> None:
    node_file = tmp_path / "gate_tests" / "test_node.py"
    node_file.parent.mkdir()
    node_file.write_text("def test_node():\n    assert True\n", encoding="utf-8")
    (node_file.parent / "test_other.py").write_text(
        "def test_other():\n    assert True\n", encoding="utf-8"
    )
    manifest_path = tmp_path / "gate.toml"
    manifest_path.write_text("schema_version = 1\nnodes = []\n", encoding="utf-8")
    try:
        load_manifest(manifest_path)
    except ManifestError as error:
        assert str(error) == "GATE_MANIFEST_EMPTY"
    else:
        raise AssertionError("Un manifeste vide doit être refusé.")
    manifest_path.write_text(
        """schema_version = 1
[[nodes]]
id = "node.a"
path = "gate_tests/test_node.py"
kind = "test"
scope = "m001"
phase = "tests"
timeout_seconds = 10
serial_group = "parallel"
depends_on = []
live = false
[[nodes]]
id = "node.a"
path = "gate_tests/test_other.py"
kind = "test"
scope = "m001"
phase = "tests"
timeout_seconds = 10
serial_group = "parallel"
depends_on = []
live = false
""",
        encoding="utf-8",
    )
    try:
        load_manifest(manifest_path)
    except ManifestError as error:
        assert str(error) == "GATE_NODE_ID_DUPLICATE:node.a"
    else:
        raise AssertionError("Un identifiant dupliqué doit être refusé.")
    manifest_path.write_text(
        """schema_version = 1
[[nodes]]
id = "node.external"
path = "../hors_depot.py"
kind = "test"
scope = "m001"
phase = "tests"
timeout_seconds = 10
serial_group = "parallel"
depends_on = []
live = false
""",
        encoding="utf-8",
    )
    try:
        load_manifest(manifest_path)
    except ManifestError as error:
        assert str(error) == "GATE_NODE_PATH_OUTSIDE_REPOSITORY:node.external:../hors_depot.py"
    else:
        raise AssertionError("Un chemin hors dépôt doit être refusé.")
