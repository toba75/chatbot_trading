"""Ports et services publics injectés aux routeurs de l'orchestrateur."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.platform.application.public_contract_use_cases import (
    ConversationUseCase,
    EvaluationUseCase,
    IndexingUseCase,
    SearchUseCase,
)
from app.platform.configuration import ApplicationConfiguration


PublicResponse = tuple[int, dict[str, Any]]


class JsonCommandHandler(Protocol):
    def handle(self, body: dict[str, Any]) -> PublicResponse: ...


class IndexCommandHandler(Protocol):
    def handle(self, document_id: str, body: dict[str, Any]) -> PublicResponse: ...


@dataclass(frozen=True, slots=True)
class ConversationService:
    configuration: ApplicationConfiguration

    def handle(self, body: dict[str, Any]) -> PublicResponse:
        return ConversationUseCase(self.configuration).handle(body)


@dataclass(frozen=True, slots=True)
class EvaluationService:
    configuration: ApplicationConfiguration

    def handle(self, body: dict[str, Any]) -> PublicResponse:
        return EvaluationUseCase(self.configuration).handle(body)


@dataclass(frozen=True, slots=True)
class SearchService:
    def handle(self, body: dict[str, Any]) -> PublicResponse:
        return SearchUseCase().handle(body)


@dataclass(frozen=True, slots=True)
class IndexingService:
    def handle(self, document_id: str, body: dict[str, Any]) -> PublicResponse:
        return IndexingUseCase().handle(document_id, body)


@dataclass(frozen=True, slots=True)
class PublicContractServices:
    conversation: JsonCommandHandler
    evaluation: JsonCommandHandler
    search: JsonCommandHandler
    indexing: IndexCommandHandler


def build_public_contract_services(
    configuration: ApplicationConfiguration,
) -> PublicContractServices:
    if not isinstance(configuration, ApplicationConfiguration):
        raise TypeError("configuration applicative validée obligatoire")
    return PublicContractServices(
        conversation=ConversationService(configuration),
        evaluation=EvaluationService(configuration),
        search=SearchService(),
        indexing=IndexingService(),
    )


__all__ = [
    "IndexCommandHandler",
    "JsonCommandHandler",
    "PublicContractServices",
    "build_public_contract_services",
]
