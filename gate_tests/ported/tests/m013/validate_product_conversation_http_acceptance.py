from __future__ import annotations

import hashlib
from pathlib import Path
import sys


def test_validate_product_conversation_http_acceptance() -> None:
    repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    sys.path.insert(0, str(repository_root))

    from app.conversation.adapters.in_memory_conversation_repository import (
        InMemoryConversationRepository,
    )
    from app.conversation.adapters.in_memory_turn_repository import InMemoryTurnRepository
    from app.conversation.adapters.product_conversation_http import (
        HttpRequest,
        ProductConversationAnswer,
        ProductConversationHttpAdapter,
    )

    quoted_span = "Le momentum est documenté par le passage cité."
    quoted_span_hash = hashlib.sha256(quoted_span.encode("utf-8")).hexdigest()

    class SequenceIdFactory:
        def __init__(self, values: tuple[str, ...]) -> None:
            self._values = list(values)

        def next_id(self) -> str:
            return self._values.pop(0)

    class DocumentaryAnswerProvider:
        def answer(self, request: object) -> ProductConversationAnswer:
            assert getattr(request, "requested_mode") == "CHAT_DOCUMENTAIRE"
            assert getattr(request, "selected_document_ids") == ("DOC-M013-CHAT-001",)
            return ProductConversationAnswer(
                answer_id="ANS-M013-CHAT-001",
                answer_text="Le momentum est documenté par le passage cité.",
                citations=(
                    {
                        "citation_id": "CIT-M013-CHAT-001",
                        "evidence_id": "EVS-M013-CHAT-001",
                        "quoted_span": quoted_span,
                        "quoted_span_hash": quoted_span_hash,
                        "source_locator": {
                            "schema_version": "1.0",
                            "canonical_version_id": "CVER-M013-CHAT-001",
                            "document_id": "DOC-M013-CHAT-001",
                            "page_pdf": 7,
                            "item_id": "ITEM-M013-CHAT-001",
                            "bbox": (0.1, 0.2, 0.3, 0.4),
                            "content_hash": "b" * 64,
                        },
                    },
                ),
                support_status="SUPPORTED",
                knowledge_gaps=(),
                unresolved_conflicts=(),
            )

    adapter = ProductConversationHttpAdapter(
        conversation_repository=InMemoryConversationRepository.empty(),
        turn_repository=InMemoryTurnRepository.empty(),
        conversation_id_factory=SequenceIdFactory(("CONV-M013-CHAT-001",)),
        turn_id_factory=SequenceIdFactory(("TURN-M013-CHAT-001",)),
        answer_provider=DocumentaryAnswerProvider(),
        retention_policy_version="conversation-retention-m013-v1",
    )

    # Given une conversation CV active et un document réellement sélectionné.
    created = adapter.handle(
        HttpRequest(
            method="POST",
            path="/v1/conversations",
            body={
                "title": "Momentum",
                "default_mandate": {"allowed_universe": ["document sélectionné"]},
                "presentation_preferences": {"language": "fr"},
                "occurred_at": "2026-07-15T10:00:00Z",
            },
        )
    )
    assert created.status_code == 201

    # When l'UI envoie un tour par le contrat CV natif, avec mode explicite.
    # Then CV conserve le tour, délègue à RA et publie question, mode,
    # support et citation sans exposer le stockage KA ou le transport LLM.
    response = adapter.handle(
        HttpRequest(
            method="POST",
            path="/v1/conversations/CONV-M013-CHAT-001/messages",
            body={
                "message": "Explique le momentum.",
                "idempotency_key": "idem-m013-chat-001",
                "occurred_at": "2026-07-15T10:01:00Z",
                "requested_mode": "CHAT_DOCUMENTAIRE",
                "selected_documents": ["DOC-M013-CHAT-001"],
            },
        )
    )
    assert response.status_code == 200
    assert response.body["turn_id"] == "TURN-M013-CHAT-001"
    assert response.body["resolved_question"] == "Explique le momentum."
    assert response.body["mode"] == "CHAT_DOCUMENTAIRE"
    assert response.body["support_status"] == "SUPPORTED"
    assert response.body["citations"][0]["source_locator"]["page_pdf"] == 7
    serialized = repr(response.body).lower()
    assert "qdrant" not in serialized
    assert "vllm" not in serialized
    assert "prompt" not in serialized

    replay = adapter.handle(
        HttpRequest(
            method="POST",
            path="/v1/conversations/CONV-M013-CHAT-001/messages",
            body={
                "message": "Explique le momentum.",
                "idempotency_key": "idem-m013-chat-001",
                "occurred_at": "2026-07-15T10:01:00Z",
                "requested_mode": "CHAT_DOCUMENTAIRE",
                "selected_documents": ["DOC-M013-CHAT-001"],
            },
        )
    )
    assert replay == response
