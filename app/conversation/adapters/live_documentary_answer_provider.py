"""Adaptateur CV vers le service RA documentaire live."""

from __future__ import annotations

from app.conversation.adapters.product_conversation_http import (
    ProductConversationAnswer,
    ProductConversationAnswerError,
    ProductConversationRequest,
)
from app.research_answering.application.live_documentary_answer import (
    LiveDocumentaryAnswerError,
    LiveDocumentaryAnswerRequest,
    LiveDocumentaryAnswerService,
)


class LiveDocumentaryConversationAnswerProvider:
    """Traduit le DTO CV en commande RA sans produire de réponse secondaire."""

    def __init__(self, *, answer_service: LiveDocumentaryAnswerService) -> None:
        if not isinstance(answer_service, LiveDocumentaryAnswerService):
            raise ValueError("answer_service documentaire invalide")
        self._answer_service = answer_service

    def answer(self, request: ProductConversationRequest) -> ProductConversationAnswer:
        if not isinstance(request, ProductConversationRequest):
            raise ValueError("requête conversation produit invalide")
        try:
            result = self._answer_service.answer(
                LiveDocumentaryAnswerRequest(
                    conversation_id=request.conversation_id,
                    turn_id=request.turn_id,
                    resolved_question=request.resolved_question,
                    selected_document_ids=request.selected_document_ids,
                    occurred_at=request.occurred_at,
                )
            )
        except LiveDocumentaryAnswerError as exc:
            raise ProductConversationAnswerError(exc.error_code) from exc
        return ProductConversationAnswer(
            answer_id=result.answer_id,
            answer_text=result.answer_text,
            citations=result.citations,
            support_status=result.support_status,
            knowledge_gaps=result.knowledge_gaps,
            unresolved_conflicts=result.unresolved_conflicts,
        )


__all__ = ["LiveDocumentaryConversationAnswerProvider"]
