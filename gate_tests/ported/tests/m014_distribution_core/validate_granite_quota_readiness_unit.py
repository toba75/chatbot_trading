"""Tests unitaires du harnais PostgreSQL réel de T-004."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
from types import ModuleType

import psycopg
import pytest


def _load_live_harness() -> ModuleType:
    module_path = Path(__file__).with_name("validate_granite_quota_live.py")
    specification = importlib.util.spec_from_file_location(
        "m014_granite_quota_live_harness",
        module_path,
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


granite_quota_live = _load_live_harness()


class _ReadyCursor:
    def __enter__(self) -> _ReadyCursor:
        return self

    def __exit__(self, *_arguments: object) -> None:
        return None

    def execute(self, statement: str, parameters: tuple[()]) -> None:
        assert statement == "SELECT 1"
        assert parameters == ()

    def fetchone(self) -> tuple[int]:
        return (1,)


class _ReadyConnection:
    def __enter__(self) -> _ReadyConnection:
        return self

    def __exit__(self, *_arguments: object) -> None:
        return None

    def cursor(self) -> _ReadyCursor:
        return _ReadyCursor()


class _TransientThenReadyFactory:
    def __init__(self) -> None:
        self.attempts = 0

    def connect(self) -> _ReadyConnection:
        self.attempts += 1
        if self.attempts == 1:
            raise psycopg.OperationalError("server closed the connection unexpectedly")
        return _ReadyConnection()


class _FatalOperationalError(psycopg.OperationalError):
    @property
    def sqlstate(self) -> str:
        return "28P01"


class _FatalFactory:
    def __init__(self) -> None:
        self.attempts = 0

    def connect(self) -> _ReadyConnection:
        self.attempts += 1
        raise _FatalOperationalError("authentification PostgreSQL refusée")


class _UnusedFactory:
    def __init__(self) -> None:
        self.attempts = 0

    def connect(self) -> _ReadyConnection:
        self.attempts += 1
        raise AssertionError("Aucune connexion ne doit suivre l'arrêt du conteneur")


def _container_state(*_arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=(),
        returncode=0,
        stdout="true|running|0\n",
        stderr="",
    )


def test_readiness_postgresql_utilise_le_chemin_publie_sans_masquer_les_pannes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Given Docker démarré, When le port publié oscille, Then seul le réseau transitoire est attendu."""

    monkeypatch.setattr(granite_quota_live, "_docker", _container_state)
    monkeypatch.setattr(granite_quota_live.time, "sleep", lambda _seconds: None)

    transient_factory = _TransientThenReadyFactory()
    granite_quota_live._wait_postgres(
        container="postgres-transitoire",
        connection_factory=transient_factory,
        timeout_seconds=1,
        poll_seconds=0.001,
    )
    assert transient_factory.attempts == 2

    def stopped_state(*_arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=(),
            returncode=0,
            stdout="false|exited|1\n",
            stderr="",
        )

    monkeypatch.setattr(granite_quota_live, "_docker", stopped_state)
    unused_factory = _UnusedFactory()
    with pytest.raises(AssertionError, match="arrêté"):
        granite_quota_live._wait_postgres(
            container="postgres-arrêté",
            connection_factory=unused_factory,
            timeout_seconds=1,
            poll_seconds=0.001,
        )
    assert unused_factory.attempts == 0

    monkeypatch.setattr(granite_quota_live, "_docker", _container_state)
    fatal_factory = _FatalFactory()
    with pytest.raises(_FatalOperationalError, match="authentification"):
        granite_quota_live._wait_postgres(
            container="postgres-erreur-serveur",
            connection_factory=fatal_factory,
            timeout_seconds=1,
            poll_seconds=0.001,
        )
    assert fatal_factory.attempts == 1
