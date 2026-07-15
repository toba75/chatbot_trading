from __future__ import annotations

from pathlib import Path
import sys


def test_validate_product_conversation_router_acceptance() -> None:
    repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    sys.path.insert(0, str(repository_root))

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.conversation.adapters.in_memory_conversation_repository import (
        InMemoryConversationRepository,
    )
    from app.conversation.adapters.in_memory_turn_repository import InMemoryTurnRepository
    from app.conversation.adapters.product_conversation_http import (
        ProductConversationAnswer,
        ProductConversationHttpAdapter,
    )
    from app.platform.orchestrator_contract_routers import (
        build_product_conversation_router,
    )

    class IdFactory:
        def __init__(self, values: tuple[str, ...]) -> None:
            self.values = list(values)

        def next_id(self) -> str:
            return self.values.pop(0)

    class Provider:
        def answer(self, request: object) -> ProductConversationAnswer:
            return ProductConversationAnswer(
                answer_id="ANS-M013-ROUTER-001",
                answer_text="Réponse issue de RA.",
                citations=(
                    {
                        "citation_id": "CIT-M013-ROUTER-001",
                        "evidence_id": "EVS-M013-ROUTER-001",
                        "quoted_span_hash": "a" * 64,
                        "source_locator": {
                            "schema_version": "1.0",
                            "canonical_version_id": "CVER-M013-ROUTER-001",
                            "document_id": "DOC-M013-ROUTER-001",
                            "page_pdf": 2,
                            "item_id": "ITEM-M013-ROUTER-001",
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
        conversation_id_factory=IdFactory(("CONV-M013-ROUTER-001",)),
        turn_id_factory=IdFactory(("TURN-M013-ROUTER-001",)),
        answer_provider=Provider(),
        retention_policy_version="conversation-retention-m013-v1",
    )
    app = FastAPI()
    app.include_router(build_product_conversation_router(adapter))
    client = TestClient(app)

    # Given l'API est composée avec le contrat CV natif.
    # When le navigateur crée une conversation et poste une question.
    # Then FastAPI ne fait que valider et déléguer ; la réponse produit garde
    # les preuves CV/RA sans détour par /v1/chat/completions.
    created = client.post(
        "/v1/conversations",
        json={
            "title": "Momentum",
            "default_mandate": {"allowed_universe": ["document"]},
            "presentation_preferences": {"language": "fr"},
            "occurred_at": "2026-07-15T10:00:00Z",
        },
    )
    assert created.status_code == 201
    answered = client.post(
        "/v1/conversations/CONV-M013-ROUTER-001/messages",
        json={
            "message": "Explique le momentum.",
            "idempotency_key": "idem-m013-router-001",
            "occurred_at": "2026-07-15T10:01:00Z",
            "requested_mode": "CHAT_DOCUMENTAIRE",
            "selected_documents": ["DOC-M013-ROUTER-001"],
        },
    )
    assert answered.status_code == 200
    payload = answered.json()
    assert payload["mode"] == "CHAT_DOCUMENTAIRE"
    assert payload["citations"][0]["source_locator"]["document_id"] == "DOC-M013-ROUTER-001"
    history = client.get("/v1/conversations/CONV-M013-ROUTER-001/turns")
    assert history.status_code == 200
    assert history.json() == {
        "conversation_id": "CONV-M013-ROUTER-001",
        "next_page_token": None,
        "turns": [
            {
                "conversation_id": "CONV-M013-ROUTER-001",
                "turn_id": "TURN-M013-ROUTER-001",
                "sequence": 1,
                "role": "USER",
                "message": "Explique le momentum.",
                "occurred_at": "2026-07-15T10:01:00Z",
                "presentation": payload,
            }
        ],
    }
    assert client.post("/v1/chat/completions", json={}).status_code == 404
