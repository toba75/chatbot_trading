from __future__ import annotations

import json
from pathlib import Path
import sys


def test_validate_ui_conversation_screen_acceptance() -> None:
    """Given-When-Then : l'UI produit consomme le contrat CV documenté."""

    repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    sys.path.insert(0, str(repository_root))

    from app.platform.ui_conversation import render_conversation_page
    from app.platform.ui_conversation_api import (
        UiConversationApiClient,
        UiConversationApiResponse,
    )

    class RecordingTransport:
        def __init__(self) -> None:
            self.requests: list[tuple[str, str, dict[str, object] | None]] = []
            self.responses = [
                UiConversationApiResponse(
                    status_code=201,
                    content_type="application/json",
                    body=(
                        b'{"conversation_id":"CONV-M013-CHAT-001",'
                        b'"title":"Momentum",'
                        b'"status":"ACTIVE",'
                        b'"created_at":"2026-07-15T10:00:00Z",'
                        b'"updated_at":"2026-07-15T10:00:00Z"}'
                    ),
                ),
                UiConversationApiResponse(
                    status_code=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "conversation_id": "CONV-M013-CHAT-001",
                            "turn_id": "TURN-M013-CHAT-001",
                            "resolved_question": "Explique le momentum.",
                            "mode": "CHAT_DOCUMENTAIRE",
                            "mode_justification": "Question documentaire explicitement demandée.",
                            "support_status": "SUPPORTED",
                            "answer_id": "ANS-M013-CHAT-001",
                            "verified_answer_ref": "ANS-M013-CHAT-001@1",
                            "answer_text": "Le momentum est décrit dans le document sélectionné.",
                            "knowledge_gaps": [],
                            "unresolved_conflicts": [],
                            "abstention_reason": None,
                            "citations": [
                                {
                                    "citation_id": "CIT-M013-CHAT-001",
                                    "evidence_id": "EVS-M013-CHAT-001",
                                    "quoted_span_hash": "a" * 64,
                                    "source_locator": {
                                        "schema_version": "1.0",
                                        "canonical_version_id": "CVER-M013-CHAT-001",
                                        "document_id": "DOC-M013-CHAT-001",
                                        "page_pdf": 7,
                                        "item_id": "ITEM-M013-CHAT-001",
                                        "bbox": [0.1, 0.2, 0.3, 0.4],
                                        "content_hash": "b" * 64,
                                    },
                                }
                            ],
                        },
                        ensure_ascii=False,
                    ).encode("utf-8"),
                ),
                UiConversationApiResponse(
                    status_code=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "conversation_id": "CONV-M013-CHAT-001",
                            "next_page_token": None,
                            "turns": [
                                {
                                    "conversation_id": "CONV-M013-CHAT-001",
                                    "turn_id": "TURN-M013-CHAT-001",
                                    "sequence": 1,
                                    "role": "USER",
                                    "message": "Explique le momentum.",
                                    "occurred_at": "2026-07-15T10:01:00Z",
                                    "presentation": {
                                        "conversation_id": "CONV-M013-CHAT-001",
                                        "turn_id": "TURN-M013-CHAT-001",
                                        "resolved_question": "Explique le momentum.",
                                        "mode": "CHAT_DOCUMENTAIRE",
                                        "mode_justification": "Question documentaire explicitement demandée.",
                                        "support_status": "SUPPORTED",
                                        "answer_id": "ANS-M013-CHAT-001",
                                        "verified_answer_ref": "ANS-M013-CHAT-001@1",
                                        "answer_text": "Le momentum est documenté par le passage cité.",
                                        "knowledge_gaps": [],
                                        "unresolved_conflicts": [],
                                        "abstention_reason": None,
                                        "citations": [
                                            {
                                                "citation_id": "CIT-M013-CHAT-001",
                                                "evidence_id": "EVS-M013-CHAT-001",
                                                "quoted_span_hash": "a" * 64,
                                                "source_locator": {
                                                    "schema_version": "1.0",
                                                    "canonical_version_id": "CVER-M013-CHAT-001",
                                                    "document_id": "DOC-M013-CHAT-001",
                                                    "page_pdf": 7,
                                                    "item_id": "ITEM-M013-CHAT-001",
                                                    "bbox": [0.1, 0.2, 0.3, 0.4],
                                                    "content_hash": "b" * 64,
                                                },
                                            }
                                        ],
                                    },
                                }
                            ],
                        },
                        ensure_ascii=False,
                    ).encode("utf-8"),
                ),
            ]

        def request(
            self,
            *,
            method: str,
            path: str,
            body: bytes | None,
            content_type: str | None,
        ) -> UiConversationApiResponse:
            payload = None if body is None else json.loads(body.decode("utf-8"))
            self.requests.append((method, path, payload))
            assert content_type == "application/json; charset=utf-8"
            return self.responses.pop(0)

    transport = RecordingTransport()
    client = UiConversationApiClient(transport=transport)

    # Given un utilisateur a choisi explicitement un document SEARCHABLE et un mandat.
    # When il ouvre une conversation puis envoie une question documentaire autonome.
    # Then l'UI appelle exclusivement le contrat CV, affiche la réponse publique
    # complète et offre une citation ouvrable vers l'original local.
    conversation = client.create_conversation(
        title="Momentum",
        default_mandate={"allowed_universe": ["documents sélectionnés"]},
        presentation_preferences={"language": "fr"},
        occurred_at="2026-07-15T10:00:00Z",
    )
    answer = client.send_message(
        conversation_id=conversation.conversation_id,
        message="Explique le momentum.",
        idempotency_key="idem-m013-chat-001",
        occurred_at="2026-07-15T10:01:00Z",
        requested_mode="CHAT_DOCUMENTAIRE",
        selected_documents=("DOC-M013-CHAT-001",),
    )
    turns = client.read_turns(conversation.conversation_id)
    html = render_conversation_page(
        conversation=conversation,
        turns=turns,
        selectable_documents=(
            ("DOC-M013-CHAT-001", "Trading on Momentum"),
        ),
    )

    assert transport.requests == [
        (
            "POST",
            "/v1/conversations",
            {
                "title": "Momentum",
                "default_mandate": {"allowed_universe": ["documents sélectionnés"]},
                "presentation_preferences": {"language": "fr"},
                "occurred_at": "2026-07-15T10:00:00Z",
            },
        ),
        (
            "POST",
            "/v1/conversations/CONV-M013-CHAT-001/messages",
            {
                "message": "Explique le momentum.",
                "idempotency_key": "idem-m013-chat-001",
                "occurred_at": "2026-07-15T10:01:00Z",
                "requested_mode": "CHAT_DOCUMENTAIRE",
                "selected_documents": ["DOC-M013-CHAT-001"],
            },
        ),
        ("GET", "/v1/conversations/CONV-M013-CHAT-001/turns", None),
    ]
    assert turns[0].presentation == answer
    assert "Tour 1" in html
    assert "Question résolue" in html
    assert "CHAT_DOCUMENTAIRE" in html
    assert "SUPPORTED" in html
    assert "Le momentum est décrit" in html
    assert "/ui/documents/DOC-M013-CHAT-001/pdf" in html
    assert "qdrant" not in html.lower()
    assert "vllm" not in html.lower()


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
