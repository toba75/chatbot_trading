"""Composition des ports publics injectés aux routeurs de l'orchestrateur."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.contracts.llm_inference import JsonObject, JsonValue, LlmInferenceGateway
from app.platform.configuration import ApplicationConfiguration


PublicResponse = tuple[int, dict[str, JsonValue]]


class JsonCommandHandler(Protocol):
    def handle(self, body: JsonObject, *, trace_id: str) -> PublicResponse: ...


class IndexCommandHandler(Protocol):
    def handle(
        self,
        document_id: str,
        body: JsonObject,
        *,
        trace_id: str,
    ) -> PublicResponse: ...


@dataclass(frozen=True, slots=True)
class PublicContractServices:
    conversation: JsonCommandHandler
    evaluation: JsonCommandHandler
    search: JsonCommandHandler
    indexing: IndexCommandHandler

    def __post_init__(self) -> None:
        for field_name in ("conversation", "evaluation", "search", "indexing"):
            if not callable(getattr(getattr(self, field_name), "handle", None)):
                raise TypeError(f"service public {field_name} invalide")


def build_public_contract_services(
    configuration: ApplicationConfiguration,
    *,
    inference_gateway: LlmInferenceGateway,
) -> PublicContractServices:
    from app.platform.orchestrator_runtime import compose_public_contract_services

    return compose_public_contract_services(
        configuration,
        inference_gateway=inference_gateway,
    )


__all__ = [
    "IndexCommandHandler",
    "JsonCommandHandler",
    "PublicContractServices",
    "build_public_contract_services",
]
