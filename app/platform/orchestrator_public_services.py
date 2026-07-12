"""Ports et services publics injectés aux routeurs de l'orchestrateur."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.platform.configuration import ApplicationConfiguration
from app.platform import local_runtime


PublicResponse = tuple[int, dict[str, Any]]


class JsonCommandHandler(Protocol):
    def handle(self, body: dict[str, Any]) -> PublicResponse: ...


class IndexCommandHandler(Protocol):
    def handle(self, document_id: str, body: dict[str, Any]) -> PublicResponse: ...


@dataclass(frozen=True, slots=True)
class ConversationService:
    configuration: ApplicationConfiguration

    def handle(self, body: dict[str, Any]) -> PublicResponse:
        return local_runtime.product_chat_completions_post_response(
            body=body,
            application_configuration=self.configuration,
        )


@dataclass(frozen=True, slots=True)
class EvaluationService:
    configuration: ApplicationConfiguration

    def handle(self, body: dict[str, Any]) -> PublicResponse:
        return local_runtime.llm_real_path_benchmark_post_response(
            body=body,
            application_configuration=self.configuration,
        )


@dataclass(frozen=True, slots=True)
class SearchService:
    def handle(self, body: dict[str, Any]) -> PublicResponse:
        del body
        return local_runtime.search_post_response()


@dataclass(frozen=True, slots=True)
class IndexingService:
    def handle(self, document_id: str, body: dict[str, Any]) -> PublicResponse:
        del body
        return local_runtime.index_post_response(document_id=document_id)


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
