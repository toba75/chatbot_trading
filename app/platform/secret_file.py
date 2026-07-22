"""Lecture stricte des secrets montés depuis le profil sélectionné."""

from __future__ import annotations

from pathlib import Path


def read_required_secret(*, path: Path, error_code: str) -> str:
    if not isinstance(path, Path):
        raise TypeError("chemin de secret obligatoire")
    if not isinstance(error_code, str) or error_code.strip() == "":
        raise ValueError("code d'erreur secret invalide")
    try:
        value = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(error_code) from exc
    if len(value.encode("utf-8")) < 32:
        raise RuntimeError(error_code)
    return value


__all__ = ["read_required_secret"]
