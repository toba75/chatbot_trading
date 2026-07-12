"""Contexte de corrélation strict de la requête orchestratrice courante."""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any


_TRACE_ID: ContextVar[str] = ContextVar("orchestrator_trace_id")


def bind_trace_id(trace_id: str) -> Token[str]:
    """Lie un identifiant validé à l'exécution asynchrone courante."""

    return _TRACE_ID.set(_ensure_trace_id(trace_id))


def reset_trace_id(token: Token[str]) -> None:
    if not isinstance(token, Token):
        raise ValueError("trace token invalide")
    _TRACE_ID.reset(token)


def current_trace_id() -> str:
    try:
        return _TRACE_ID.get()
    except LookupError as exc:
        raise RuntimeError("TRACE_ID_CONTEXT_REQUIRED") from exc


def _ensure_trace_id(value: Any) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError("trace_id invalide")
    return value


__all__ = ["bind_trace_id", "current_trace_id", "reset_trace_id"]
