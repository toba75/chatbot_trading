"""Contrat non mutateur de la commande persistante development."""

from __future__ import annotations

import sys

import app.platform.environment_command as command


def test_validate_development_real_e2e_acceptance(monkeypatch) -> None:
    # Given development est un environnement de travail persistant.
    calls: list[str] = []
    monkeypatch.setattr(command, "_run_entrypoint", lambda profile: calls.append(profile) or 0)
    monkeypatch.setattr(sys, "argv", ["development"])

    # When l'opérateur démarre development.
    assert command.development() == 0

    # Then seule la pile development est supervisée : aucune qualification PDF
    # ni injection de fixture n'appartient à cette commande.
    assert calls == ["development"]
