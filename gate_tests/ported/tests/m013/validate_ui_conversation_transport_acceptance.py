from __future__ import annotations

from pathlib import Path
import sys


def test_validate_ui_conversation_transport_acceptance() -> None:
    """Given-When-Then : le transport UI autorise uniquement les routes CV publiques."""

    repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    sys.path.insert(0, str(repository_root))

    from app.platform.ui_document_api import _ensure_public_relative_path

    # Given l'UI utilise le transport réseau strict déjà composé avec l'orchestrateur.
    # When elle ouvre, lit et alimente une conversation documentaire.
    # Then chaque route CV native est acceptée, sans élargir le transport à une URL externe.
    assert _ensure_public_relative_path("/v1/conversations") == "/v1/conversations"
    assert (
        _ensure_public_relative_path("/v1/conversations/CONV-M013-CHAT-001")
        == "/v1/conversations/CONV-M013-CHAT-001"
    )
    assert (
        _ensure_public_relative_path("/v1/conversations/CONV-M013-CHAT-001/messages")
        == "/v1/conversations/CONV-M013-CHAT-001/messages"
    )
    assert (
        _ensure_public_relative_path("/v1/conversations/CONV-M013-CHAT-001/turns")
        == "/v1/conversations/CONV-M013-CHAT-001/turns"
    )

    try:
        _ensure_public_relative_path("https://example.invalid/v1/conversations")
    except ValueError:
        pass
    else:
        raise AssertionError("Une origine externe ne doit jamais traverser le transport UI.")
