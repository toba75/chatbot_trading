from __future__ import annotations

import json

import pytest

from run_pipeline import _load_runtime_proof


def test_refuse_la_preuve_runtime_d_un_autre_bras(tmp_path) -> None:
    proof = tmp_path / "runtime.json"
    proof.write_text(
        json.dumps({"schema_version": 1, "effective_max_soft_tokens": 280}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="ne correspond pas au bras"):
        _load_runtime_proof(proof, 1120)


def test_accepte_la_preuve_runtime_du_bras(tmp_path) -> None:
    expected = {"schema_version": 1, "effective_max_soft_tokens": 1120}
    proof = tmp_path / "runtime.json"
    proof.write_text(json.dumps(expected), encoding="utf-8")

    content, observed = _load_runtime_proof(proof, 1120)

    assert json.loads(content) == expected
    assert observed == expected
