"""Décisions unitaires du superviseur de parcours réel test."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest


def test_test_real_e2e_unit(monkeypatch, tmp_path: Path) -> None:
    from app.platform.test_e2e import (
        TestEnvironmentCycle,
        _run_two_test_cycles,
        _verify_test_cleanup_target,
    )

    # Given un lanceur test possédant exactement deux cycles isolés.
    calls: list[int] = []

    def cycle_runner(*, run_number: int, **_kwargs):
        calls.append(run_number)
        return SimpleNamespace(run_number=run_number)

    # When le superviseur exécute la qualification.
    results = _run_two_test_cycles(
        repository_root=tmp_path,
        pdf_path=tmp_path / "fixture.pdf",
        cycle_runner=cycle_runner,
    )

    # Then les deux cycles sont obligatoires, ordonnés et sans fallback.
    assert calls == [1, 2]
    assert tuple(result.run_number for result in results) == (1, 2)

    # Et une cible de teardown étrangère est refusée avant tout effet.
    valid = TestEnvironmentCycle(
        environment="test",
        deployment_id="ostrading-test-ci",
        lifecycle_id="11111111-1111-4111-8111-111111111111",
    )
    assert _verify_test_cleanup_target(valid) is valid
    with pytest.raises(ValueError, match="ADMINISTRATIVE_OPERATION_FORBIDDEN"):
        _verify_test_cleanup_target(
            TestEnvironmentCycle(
                environment="production",
                deployment_id="ostrading-production-primary",
                lifecycle_id="22222222-2222-4222-8222-222222222222",
            )
        )

