"""Contrat unitaire des identifiants de tâches du pipeline M-013 réel."""

from __future__ import annotations

import pytest

from app.platform.local_runtime import _benchmark_marker_for_task


def test_validate_m013_reality_product_unit() -> None:
    assert _benchmark_marker_for_task("chat_produit") == "M013-REALITY-chat_produit"
    with pytest.raises(ValueError, match="task_name invalide"):
        _benchmark_marker_for_task("")
