from __future__ import annotations

from pathlib import Path
import sys


def test_validate_live_documentary_answer_unit() -> None:
    repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    sys.path.insert(0, str(repository_root))

    from app.contracts.llm_inference import LlmInferenceResponse
    from app.research_answering.application.live_documentary_answer import (
        DocumentaryEvidence,
        LiveDocumentaryAnswerError,
        LiveDocumentaryAnswerRequest,
        LiveDocumentaryAnswerService,
    )

    class Retriever:
        def retrieve(self, *, question: str, selected_document_ids: tuple[str, ...]):
            assert question == "Explique le momentum."
            assert selected_document_ids == ("DOC-M013-LIVE-001",)
            return (
                DocumentaryEvidence(
                    excerpt="Sommaire\nMomentum\n12\nTendance\n18",
                    source_locators=(
                        {
                            "schema_version": "1.0",
                            "canonical_version_id": "CVER-M013-LIVE-001",
                            "document_id": "DOC-M013-LIVE-001",
                            "page_pdf": 1,
                            "item_id": "ITEM-M013-LIVE-001-TOC",
                            "bbox": (0.1, 0.2, 0.3, 0.4),
                            "content_hash": "0" * 64,
                        },
                    ),
                ),
                DocumentaryEvidence(
                    excerpt="Le momentum mesure la persistance d'un mouvement de prix.",
                    source_locators=(
                        {
                            "schema_version": "1.0",
                            "canonical_version_id": "CVER-M013-LIVE-001",
                            "document_id": "DOC-M013-LIVE-001",
                            "page_pdf": 12,
                            "item_id": "ITEM-M013-LIVE-001-A",
                            "bbox": (0.1, 0.2, 0.3, 0.4),
                            "content_hash": "a" * 64,
                        },
                        {
                            "schema_version": "1.0",
                            "canonical_version_id": "CVER-M013-LIVE-001",
                            "document_id": "DOC-M013-LIVE-001",
                            "page_pdf": 13,
                            "item_id": "ITEM-M013-LIVE-001-B",
                            "bbox": (0.1, 0.2, 0.3, 0.4),
                            "content_hash": "b" * 64,
                        },
                    ),
                ),
            )

    class Gateway:
        def __init__(self) -> None:
            self.request = None

        def infer(self, request):
            self.request = request
            return LlmInferenceResponse(
                status_code=200,
                payload={
                    "structured_output": {
                        "answer": "Le momentum décrit la persistance du mouvement de prix.",
                        "used_evidence_ordinals": [2],
                    },
                    "raw_response_id": "RAW-M013-LIVE-001",
                    "provenance": {"configuration_hash": "c" * 64},
                },
                latency_ms=2.0,
            )

    gateway = Gateway()
    service = LiveDocumentaryAnswerService(
        evidence_retriever=Retriever(),
        inference_gateway=gateway,
        configuration_hash="c" * 64,
    )

    # Given un extrait de document sélectionné et une passerelle LLM réelle.
    # When RA prépare une réponse à partir de cet extrait.
    # Then la réponse porte des citations résolubles et aucun texte de secours
    # n'est fabriqué si la récupération ou l'inférence échoue.
    answer = service.answer(
        LiveDocumentaryAnswerRequest(
            conversation_id="CONV-M013-LIVE-001",
            turn_id="TURN-M013-LIVE-001",
            resolved_question="Explique le momentum.",
            selected_document_ids=("DOC-M013-LIVE-001",),
            occurred_at="2026-07-15T10:01:00Z",
        )
    )
    assert answer.support_status == "PARTIALLY_SUPPORTED"
    assert tuple(citation["source_locator"]["page_pdf"] for citation in answer.citations) == (12,)
    assert tuple(citation["quoted_span"] for citation in answer.citations) == (
        "Le momentum mesure la persistance d'un mouvement de prix.",
    )
    assert "persistance" in answer.answer_text
    assert gateway.request is not None
    assert "used_evidence_ordinals" in gateway.request.messages[0].content
    assert gateway.request.prompt_version == "1.1"
    assert gateway.request.schema_version == "1.1"
    assert set(gateway.request.output_schema["properties"]) == {
        "answer",
        "used_evidence_ordinals",
    }
    assert "Le momentum mesure" in gateway.request.messages[1].content

    class UnsupportedGateway:
        def infer(self, request):
            return LlmInferenceResponse(
                status_code=200,
                payload={
                    "structured_output": {
                        "answer": "Les extraits ne soutiennent pas la réponse.",
                        "used_evidence_ordinals": [],
                    },
                    "raw_response_id": "RAW-M013-LIVE-UNSUPPORTED",
                    "provenance": {"configuration_hash": "c" * 64},
                },
                latency_ms=2.0,
            )

    unsupported = LiveDocumentaryAnswerService(
        evidence_retriever=Retriever(),
        inference_gateway=UnsupportedGateway(),
        configuration_hash="c" * 64,
    )
    try:
        unsupported.answer(
            LiveDocumentaryAnswerRequest(
                conversation_id="CONV-M013-LIVE-001",
                turn_id="TURN-M013-LIVE-UNSUPPORTED",
                resolved_question="Explique le momentum.",
                selected_document_ids=("DOC-M013-LIVE-001",),
                occurred_at="2026-07-15T10:01:00Z",
            )
        )
    except LiveDocumentaryAnswerError as error:
        assert error.error_code == "DOCUMENTARY_EVIDENCE_NOT_FOUND"
    else:
        raise AssertionError("Une sortie sans preuve utilisée doit produire un gap explicite.")

    class EmptyRetriever:
        def retrieve(self, *, question: str, selected_document_ids: tuple[str, ...]):
            return ()

    unavailable = LiveDocumentaryAnswerService(
        evidence_retriever=EmptyRetriever(),
        inference_gateway=gateway,
        configuration_hash="c" * 64,
    )
    try:
        unavailable.answer(
            LiveDocumentaryAnswerRequest(
                conversation_id="CONV-M013-LIVE-001",
                turn_id="TURN-M013-LIVE-001",
                resolved_question="Explique le momentum.",
                selected_document_ids=("DOC-M013-LIVE-001",),
                occurred_at="2026-07-15T10:01:00Z",
            )
        )
    except LiveDocumentaryAnswerError as error:
        assert error.error_code == "DOCUMENTARY_EVIDENCE_NOT_FOUND"
    else:
        raise AssertionError("Une absence de preuve ne peut pas produire une réponse de remplacement.")
