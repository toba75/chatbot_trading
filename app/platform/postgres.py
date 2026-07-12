"""Connexion PostgreSQL stricte pilotée par la configuration applicative."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class PostgresConnectionFactory(Protocol):
    """Port technique ouvrant une connexion transactionnelle PostgreSQL."""

    def connect(self) -> Any:
        """Ouvre une nouvelle connexion; aucun partage de connexion entre processus."""


@dataclass(frozen=True)
class PsycopgConnectionFactory:
    """Fabrique psycopg configurée par URL et fichier secret explicites."""

    connection_url: str
    password_path: Path
    connect_timeout_seconds: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "connection_url", _normalize_connection_url(self.connection_url))
        if not isinstance(self.password_path, Path):
            raise ValueError("postgres_password_path invalide")
        if (
            isinstance(self.connect_timeout_seconds, bool)
            or not isinstance(self.connect_timeout_seconds, int)
            or self.connect_timeout_seconds < 1
        ):
            raise ValueError("postgres_connect_timeout_seconds invalide")

    def connect(self) -> Any:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("PSYCOPG_DEPENDENCY_MISSING") from exc

        password = _read_password(self.password_path)
        return psycopg.connect(
            self.connection_url,
            password=password,
            connect_timeout=self.connect_timeout_seconds,
        )


def _normalize_connection_url(value: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError("postgres_url invalide")
    if value.startswith("postgresql+psycopg://"):
        return "postgresql://" + value.removeprefix("postgresql+psycopg://")
    if value.startswith("postgresql://"):
        return value
    raise ValueError("postgres_url invalide")


def _read_password(path: Path) -> str:
    try:
        password = path.read_text(encoding="utf-8").rstrip("\r\n")
    except OSError as exc:
        raise RuntimeError("POSTGRES_SECRET_UNREADABLE") from exc
    if password == "" or password.strip() == "" or password != password.strip():
        raise RuntimeError("POSTGRES_SECRET_INVALID")
    return password


__all__ = ["PostgresConnectionFactory", "PsycopgConnectionFactory"]
