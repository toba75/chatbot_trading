"""Contrat non mutateur de la commande persistante production."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import app.platform.environment_command as command


def test_validate_production_real_e2e_acceptance(monkeypatch) -> None:
    # Given production est un environnement persistant sans données de test.
    calls: list[str] = []
    monkeypatch.setattr(command, "_run_entrypoint", lambda profile: calls.append(profile) or 0)
    monkeypatch.setattr(
        command,
        "run_production_environment_e2e",
        lambda **_: SimpleNamespace(to_mapping=lambda: {"environment": "production"}),
        raising=False,
    )
    monkeypatch.setattr(command, "_publish_production_report", lambda _: None, raising=False)
    monkeypatch.setattr(sys, "argv", ["production"])

    # When l'opérateur démarre production.
    assert command.production() == 0

    # Then seule la pile production est supervisée : aucune qualification PDF
    # ni injection de fixture n'appartient à cette commande.
    assert calls == ["production"]
