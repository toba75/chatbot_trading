"""Handlers KA des contrats publics encore explicitement non configurés."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.contracts.identity import DomainIdentifier


PublicResponse = tuple[int, dict[str, object]]


@dataclass(frozen=True, slots=True)
class SearchUnavailableHandler:
    def handle(self, body: Mapping[str, object], *, trace_id: str) -> PublicResponse:
        del body
        _required_text(trace_id, "trace_id")
        return 503, {
            "error_code": "SERVICE_NOT_CONFIGURED",
            "endpoint": "POST /v1/search",
        }


@dataclass(frozen=True, slots=True)
class IndexingUnavailableHandler:
    def handle(
        self,
        document_id: str,
        body: Mapping[str, object],
        *,
        trace_id: str,
    ) -> PublicResponse:
        del body
        _required_text(trace_id, "trace_id")
        try:
            parsed = str(DomainIdentifier.parse_with_prefix(document_id, "DOC"))
        except ValueError:
            return 400, {"error_code": "HTTP_REQUEST_INVALID", "field": "document_id"}
        return 503, {
            "document_id": parsed,
            "error_code": "SERVICE_NOT_CONFIGURED",
            "endpoint": "POST /v1/documents/{document_id}/index",
        }


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(f"{field_name} invalide")
    return value


__all__ = ["IndexingUnavailableHandler", "SearchUnavailableHandler"]
