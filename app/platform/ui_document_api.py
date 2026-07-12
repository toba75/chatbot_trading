"""Client HTTP strict de l'UI vers les contrats documentaires publics."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlsplit

from pydantic import ValidationError

from app.platform.orchestrator_api_models import (
    DocumentCorpusResponse,
    DocumentDiagnosticResponse,
    ProjectionResponse,
)
from app.platform.orchestrator_asgi import MAX_REQUEST_BODY_BYTES

from app.platform.ui_corpus import (
    CONVERSION_STATUSES,
    DIAGNOSTIC_STATUSES,
    PROJECTION_STATUSES,
    SOURCE_STATUSES,
    CorpusPdfDocument,
    CorpusPdfScreenState,
)


ORCHESTRATOR_API_UNAVAILABLE = "ORCHESTRATOR_API_UNAVAILABLE"
UI_DOCUMENT_PAGE_SIZE = 100
_DOCUMENT_ID_PATTERN = r"[^/]+"
_DIAGNOSE_PATH_PATTERN = re.compile(
    rf"^/v1/documents/(?P<document_id>{_DOCUMENT_ID_PATTERN})/diagnose$"
)
_PUBLIC_DOCUMENT_PATH_PATTERN = re.compile(r"^/v1/documents(?:/[^/]+(?:/[^/]+)?)?$")
_INTERNAL_FIELD_NAMES = frozenset(
    {
        "original_storage_ref",
        "storage_path",
        "qdrant_collection",
        "qdrant_point_id",
        "postgres_table",
        "sp_table",
    }
)


@dataclass(frozen=True, slots=True)
class UiDocumentApiResponse:
    """Réponse HTTP brute, bornée au transport UI/orchestrateur."""

    status_code: int
    content_type: str
    body: bytes

    def __post_init__(self) -> None:
        if (
            isinstance(self.status_code, bool)
            or not isinstance(self.status_code, int)
            or self.status_code < 100
            or self.status_code > 599
        ):
            raise ValueError("status_code HTTP invalide")
        _ensure_text(self.content_type, "content_type requis")
        if not isinstance(self.body, bytes):
            raise ValueError("body HTTP binaire requis")


@dataclass(frozen=True, slots=True)
class UiDocumentJsonResponse:
    """Réponse JSON publique validée avant affichage par l'UI."""

    status_code: int
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        if (
            isinstance(self.status_code, bool)
            or not isinstance(self.status_code, int)
            or self.status_code < 100
            or self.status_code > 599
        ):
            raise ValueError("status_code JSON invalide")
        if not isinstance(self.payload, Mapping):
            raise ValueError("payload JSON public invalide")
        _ensure_no_internal_fields(self.payload)
        object.__setattr__(self, "payload", dict(self.payload))


class UiDocumentApiUnavailableError(ConnectionError):
    """Indique explicitement que l'API orchestratrice ne répond pas."""


class UiDocumentApiPublicError(RuntimeError):
    """Porte une erreur HTTP publique retournée par l'orchestrateur."""

    def __init__(self, response: UiDocumentJsonResponse) -> None:
        if not isinstance(response, UiDocumentJsonResponse):
            raise TypeError("réponse d'erreur publique invalide")
        self.response = response
        super().__init__(str(response.payload["error_code"]))


class UiDocumentApiTransport(Protocol):
    """Port de transport recevant uniquement des chemins publics relatifs."""

    def request(
        self,
        *,
        method: str,
        path: str,
        body: bytes | None,
        content_type: str | None,
    ) -> UiDocumentApiResponse:
        """Exécute une requête HTTP vers l'unique origine orchestratrice."""


class UrllibUiDocumentApiTransport:
    """Transport réseau runtime sans backend alternatif ni cache."""

    def __init__(self, *, orchestrator_origin: str, timeout_seconds: int) -> None:
        self._orchestrator_origin = _ensure_origin(orchestrator_origin)
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, int)
            or timeout_seconds < 1
        ):
            raise ValueError("timeout_seconds UI invalide")
        self._timeout_seconds = timeout_seconds

    def request(
        self,
        *,
        method: str,
        path: str,
        body: bytes | None,
        content_type: str | None,
    ) -> UiDocumentApiResponse:
        parsed_method = _ensure_method(method)
        parsed_path = _ensure_public_relative_path(path)
        if body is not None and not isinstance(body, bytes):
            raise ValueError("body UI invalide")
        if content_type is not None:
            _ensure_text(content_type, "content_type UI invalide")
        headers = {} if content_type is None else {"Content-Type": content_type}
        request = urllib.request.Request(
            url=f"{self._orchestrator_origin}{parsed_path}",
            data=body,
            headers=headers,
            method=parsed_method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                return UiDocumentApiResponse(
                    status_code=response.status,
                    content_type=response.headers.get_content_type(),
                    body=response.read(),
                )
        except urllib.error.HTTPError as exc:
            try:
                error_body = exc.read()
            except (urllib.error.URLError, TimeoutError, OSError) as read_exc:
                raise UiDocumentApiUnavailableError(
                    ORCHESTRATOR_API_UNAVAILABLE
                ) from read_exc
            return UiDocumentApiResponse(
                status_code=exc.code,
                content_type=exc.headers.get_content_type(),
                body=error_body,
            )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise UiDocumentApiUnavailableError(ORCHESTRATOR_API_UNAVAILABLE) from exc


class UiDocumentApiClient:
    """Client UI sans propriété SP/KA et sans état documentaire local."""

    def __init__(self, *, transport: UiDocumentApiTransport) -> None:
        if not callable(getattr(transport, "request", None)):
            raise ValueError("transport API documentaire UI invalide")
        self._transport = transport

    def build_corpus_state(
        self,
        *,
        active_selected_document_ids: Sequence[str],
    ) -> CorpusPdfScreenState:
        selected_ids = tuple(active_selected_document_ids)
        documents: list[CorpusPdfDocument] = []
        cursor: str | None = None
        seen_cursors: set[str] = set()
        while True:
            path = f"/v1/documents?limit={UI_DOCUMENT_PAGE_SIZE}"
            if cursor is not None:
                path = f"{path}&cursor={cursor}"
            response = self._json_request(
                method="GET",
                path=path,
                body=None,
                content_type=None,
            )
            _require_success(response, expected_statuses=frozenset((200,)))
            try:
                page = DocumentCorpusResponse.model_validate(response.payload)
            except ValidationError as exc:
                raise ValueError("page de corpus publique incompatible") from exc
            for public_document in page.documents:
                document = _parse_corpus_document(public_document.model_dump())
                documents.append(
                    CorpusPdfDocument(
                        document_id=document["document_id"],
                        title=document["title"],
                        source_status=document["document_status"],
                        diagnostic_status=document["diagnostic_status"],
                        conversion_status=document["conversion_status"],
                        canonical_version_id=document["canonical_version_id"],
                        projection_status=document["projection_status"],
                        selected=document["document_id"] in selected_ids,
                    )
                )
            cursor = page.next_cursor
            if cursor is None:
                break
            _ensure_document_id(cursor)
            if cursor in seen_cursors:
                raise ValueError("curseur de corpus public cyclique")
            seen_cursors.add(cursor)
        return CorpusPdfScreenState(
            documents=tuple(documents),
            active_selected_document_ids=selected_ids,
            read_model_status="READ_MODEL_READY",
        )

    def read_diagnostic(self, document_id: str) -> UiDocumentJsonResponse:
        parsed_document_id = _ensure_document_id(document_id)
        response = self._json_request(
            method="GET",
            path=f"/v1/documents/{parsed_document_id}/diagnostic",
            body=None,
            content_type=None,
        )
        if response.status_code == 200:
            try:
                DocumentDiagnosticResponse.model_validate(response.payload)
            except ValidationError as exc:
                raise ValueError("diagnostic public incompatible") from exc
            _validate_diagnostic_payload(
                response.payload,
                expected_document_id=parsed_document_id,
            )
        return response

    def read_conversion(self, document_id: str) -> UiDocumentJsonResponse:
        response = self._json_request(
            method="GET",
            path=f"/v1/documents/{_ensure_document_id(document_id)}/conversion",
            body=None,
            content_type=None,
        )
        if response.status_code == 200:
            _require_exact_fields(
                response.payload,
                frozenset(
                    (
                        "document_id",
                        "conversion_status",
                        "qa_rejection_error_code",
                        "canonical_version_id",
                    )
                ),
                "conversion",
            )
            if response.payload["document_id"] != document_id:
                raise ValueError("conversion retournée pour un autre document")
            if response.payload["conversion_status"] not in CONVERSION_STATUSES:
                raise ValueError("statut conversion public invalide")
            _validate_conversion_nullability(response.payload)
        return response

    def read_projection(self, document_id: str) -> UiDocumentJsonResponse:
        response = self._json_request(
            method="GET",
            path=f"/v1/documents/{_ensure_document_id(document_id)}/projection",
            body=None,
            content_type=None,
        )
        if response.status_code == 200:
            try:
                ProjectionResponse.model_validate(response.payload)
            except ValidationError as exc:
                raise ValueError("projection publique incompatible") from exc
            _parse_projection_status(
                response.payload,
                expected_document_id=document_id,
            )
        return response

    def read_original_pdf(self, document_id: str) -> UiDocumentApiResponse:
        response = self._transport.request(
            method="GET",
            path=f"/v1/documents/{_ensure_document_id(document_id)}/original",
            body=None,
            content_type=None,
        )
        if not isinstance(response, UiDocumentApiResponse):
            raise TypeError("réponse transport UI invalide")
        if response.status_code == 200:
            if response.content_type != "application/pdf":
                raise ValueError("content_type PDF public invalide")
            if len(response.body) == 0:
                raise ValueError("contenu PDF public vide")
            return response
        parsed_error = _decode_json_response(response)
        _validate_public_error(parsed_error)
        return response

    def forward_document_command(
        self,
        *,
        path: str,
        body: bytes,
        content_type: str,
    ) -> UiDocumentJsonResponse:
        parsed_path = _ensure_document_command_path(path)
        if not isinstance(body, bytes):
            raise ValueError("body commande UI invalide")
        if len(body) > MAX_REQUEST_BODY_BYTES:
            raise ValueError("HTTP_REQUEST_TOO_LARGE")
        parsed_content_type = _ensure_text(content_type, "content_type commande UI invalide")
        response = self._json_request(
            method="POST",
            path=parsed_path,
            body=body,
            content_type=parsed_content_type,
        )
        if response.status_code < 400:
            if parsed_path == "/v1/documents":
                _validate_registration_response(response)
            else:
                _validate_diagnosis_response(response)
        return response

    def _json_request(
        self,
        *,
        method: str,
        path: str,
        body: bytes | None,
        content_type: str | None,
    ) -> UiDocumentJsonResponse:
        response = self._transport.request(
            method=method,
            path=_ensure_public_relative_path(path),
            body=body,
            content_type=content_type,
        )
        if not isinstance(response, UiDocumentApiResponse):
            raise TypeError("réponse transport UI invalide")
        parsed = _decode_json_response(response)
        if parsed.status_code >= 400:
            _validate_public_error(parsed)
        return parsed


def _parse_corpus_document(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("document public invalide")
    expected = frozenset(
        (
            "document_id",
            "title",
            "document_status",
            "diagnostic_status",
            "conversion_status",
            "canonical_version_id",
            "projection_status",
        )
    )
    _require_exact_fields(value, expected, "document corpus")
    _ensure_document_id(value["document_id"])
    _ensure_text(value["title"], "titre documentaire public invalide")
    if value["document_status"] not in SOURCE_STATUSES:
        raise ValueError("statut source public invalide")
    if value["diagnostic_status"] not in DIAGNOSTIC_STATUSES:
        raise ValueError("statut diagnostic public invalide")
    if value["conversion_status"] not in CONVERSION_STATUSES:
        raise ValueError("statut conversion public invalide")
    canonical_version_id = value["canonical_version_id"]
    if canonical_version_id is not None:
        _ensure_text(canonical_version_id, "canonical_version_id public invalide")
    if value["conversion_status"] == "CANONICAL_ACCEPTED":
        if canonical_version_id is None:
            raise ValueError("canonical_version_id requis pour conversion acceptée")
    elif canonical_version_id is not None:
        raise ValueError("canonical_version_id interdit avant conversion acceptée")
    if value["projection_status"] not in PROJECTION_STATUSES:
        raise ValueError("projection_status public invalide")
    return dict(value)


def _parse_projection_status(payload: Mapping[str, Any], *, expected_document_id: str) -> str:
    minimal_fields = frozenset(("document_id", "projection_status"))
    full_fields = frozenset(
        (
            "document_id",
            "projection_id",
            "canonical_version_id",
            "projection_status",
            "profile",
            "freshness",
            "chunk_count",
            "chunk_samples",
        )
    )
    actual_fields = frozenset(payload.keys())
    if actual_fields not in (minimal_fields, full_fields):
        raise ValueError(f"champs projection invalides: {sorted(actual_fields)}")
    if payload["document_id"] != expected_document_id:
        raise ValueError("projection retournée pour un autre document")
    status = payload["projection_status"]
    if not isinstance(status, str) or status not in PROJECTION_STATUSES:
        raise ValueError("projection_status public invalide")
    _ensure_no_internal_fields(payload)
    return status


def _validate_diagnostic_payload(
    payload: Mapping[str, Any],
    *,
    expected_document_id: str,
) -> None:
    _require_exact_fields(
        payload,
        frozenset(
            (
                "document_id",
                "diagnostic_status",
                "source_page_count",
                "diagnosed_page_count",
                "manual_review_reason",
                "manifest",
                "pages",
            )
        ),
        "diagnostic",
    )
    if payload["document_id"] != expected_document_id:
        raise ValueError("diagnostic retourné pour un autre document")
    if payload["diagnostic_status"] not in DIAGNOSTIC_STATUSES:
        raise ValueError("statut diagnostic public invalide")
    source_page_count = payload["source_page_count"]
    diagnosed_page_count = payload["diagnosed_page_count"]
    for count in (source_page_count, diagnosed_page_count):
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("comptage diagnostic public invalide")
    if source_page_count < 1 or diagnosed_page_count > source_page_count:
        raise ValueError("comptage diagnostic public incohérent")
    manifest = payload["manifest"]
    pages = payload["pages"]
    if not isinstance(manifest, list) or not isinstance(pages, list):
        raise ValueError("détails diagnostic publics invalides")
    expected_page_numbers = list(range(1, source_page_count + 1))
    manifest_numbers = []
    manifest_statuses: dict[int, str] = {}
    for entry in manifest:
        if not isinstance(entry, Mapping):
            raise ValueError("entrée manifeste publique invalide")
        _require_exact_fields(
            entry,
            frozenset(("page_number", "manifest_status")),
            "manifeste",
        )
        page_number = _positive_page_number(entry["page_number"])
        manifest_status = _ensure_text(
            entry["manifest_status"],
            "manifest_status public invalide",
        )
        manifest_numbers.append(page_number)
        manifest_statuses[page_number] = manifest_status
    if manifest_numbers != expected_page_numbers:
        raise ValueError("manifeste diagnostic incomplet, dupliqué ou désordonné")

    page_numbers = []
    diagnosed_pages = 0
    for page in pages:
        if not isinstance(page, Mapping):
            raise ValueError("page diagnostic publique invalide")
        _require_exact_fields(
            page,
            frozenset(
                (
                    "page_number",
                    "manifest_status",
                    "diagnostic",
                    "route",
                )
            ),
            "pages diagnostic",
        )
        page_number = _positive_page_number(page["page_number"])
        page_numbers.append(page_number)
        if page["manifest_status"] != manifest_statuses.get(page_number):
            raise ValueError("statut de page incohérent avec le manifeste")
        diagnostic = page["diagnostic"]
        route = page["route"]
        if diagnostic is not None:
            if not isinstance(diagnostic, Mapping):
                raise ValueError("diagnostic de page public invalide")
            diagnosed_pages += 1
        if route is not None and not isinstance(route, Mapping):
            raise ValueError("route de page publique invalide")
    if page_numbers != expected_page_numbers:
        raise ValueError("pages diagnostic incomplètes, dupliquées ou désordonnées")
    if diagnosed_pages != diagnosed_page_count:
        raise ValueError("comptage diagnostic public incohérent")

    manual_review_reason = payload["manual_review_reason"]
    if payload["diagnostic_status"] == "MANUAL_REVIEW":
        _ensure_text(manual_review_reason, "motif de revue manuelle requis")
    elif manual_review_reason is not None:
        raise ValueError("motif de revue manuelle interdit pour ce statut")


def _validate_conversion_nullability(payload: Mapping[str, Any]) -> None:
    status = payload["conversion_status"]
    rejection = payload["qa_rejection_error_code"]
    canonical_version_id = payload["canonical_version_id"]
    if status == "QA_REJECTED":
        _ensure_text(rejection, "qa_rejection_error_code requis")
        if canonical_version_id is not None:
            raise ValueError("canonical_version_id interdit pour QA_REJECTED")
        return
    if rejection is not None:
        raise ValueError("qa_rejection_error_code interdit pour ce statut")
    if status == "CANONICAL_ACCEPTED":
        _ensure_text(canonical_version_id, "canonical_version_id requis")
    elif canonical_version_id is not None:
        raise ValueError("canonical_version_id interdit avant acceptation")


def _positive_page_number(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("numéro de page public invalide")
    return value


def _validate_registration_response(response: UiDocumentJsonResponse) -> None:
    if response.status_code not in (200, 201):
        raise ValueError("statut enregistrement public invalide")
    expected = (
        frozenset(("document_id", "document_status"))
        if response.status_code == 201
        else frozenset(("document_id", "document_status", "duplicate"))
    )
    _require_exact_fields(response.payload, expected, "enregistrement")


def _validate_diagnosis_response(response: UiDocumentJsonResponse) -> None:
    if response.status_code != 202:
        raise ValueError("statut diagnostic public invalide")
    _require_exact_fields(
        response.payload,
        frozenset(("document_id", "diagnostic_status")),
        "commande diagnostic",
    )
    if response.payload["diagnostic_status"] != "DIAGNOSTIC_REQUESTED":
        raise ValueError("diagnostic_status de commande invalide")


def _require_success(
    response: UiDocumentJsonResponse,
    *,
    expected_statuses: frozenset[int],
) -> None:
    if response.status_code not in expected_statuses:
        raise UiDocumentApiPublicError(response)


def _decode_json_response(response: UiDocumentApiResponse) -> UiDocumentJsonResponse:
    if response.content_type.split(";", 1)[0].strip().lower() != "application/json":
        raise ValueError("content_type JSON public invalide")
    try:
        payload = json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("payload JSON public invalide") from exc
    if not isinstance(payload, dict):
        raise ValueError("payload JSON public non objet")
    return UiDocumentJsonResponse(status_code=response.status_code, payload=payload)


def _validate_public_error(response: UiDocumentJsonResponse) -> None:
    error_code = response.payload.get("error_code")
    _ensure_text(error_code, "error_code public requis")


def _require_exact_fields(
    value: Mapping[str, Any],
    expected_fields: frozenset[str],
    context: str,
) -> None:
    actual_fields = frozenset(value.keys())
    if actual_fields != expected_fields:
        unexpected = sorted(actual_fields - expected_fields)
        missing = sorted(expected_fields - actual_fields)
        detail = unexpected[0] if unexpected else missing[0]
        raise ValueError(f"champs {context} invalides: {detail}")
    _ensure_no_internal_fields(value)


def _ensure_no_internal_fields(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str) or key == "":
                raise ValueError("champ public invalide")
            if key in _INTERNAL_FIELD_NAMES:
                raise ValueError(f"champ interne interdit: {key}")
            _ensure_no_internal_fields(child)
    elif isinstance(value, list):
        for child in value:
            _ensure_no_internal_fields(child)


def _ensure_origin(value: str) -> str:
    origin = _ensure_text(value, "origine orchestratrice requise")
    parsed = urlsplit(origin)
    if parsed.scheme not in ("http", "https") or parsed.netloc == "":
        raise ValueError("origine orchestratrice invalide")
    if parsed.path not in ("", "/") or parsed.query != "" or parsed.fragment != "":
        raise ValueError("origine orchestratrice non bornée")
    return origin.rstrip("/")


def _ensure_public_relative_path(value: str) -> str:
    path = _ensure_text(value, "chemin public UI requis")
    parsed = urlsplit(path)
    if parsed.scheme != "" or parsed.netloc != "" or parsed.fragment != "":
        raise ValueError("chemin documentaire public invalide")
    if not _PUBLIC_DOCUMENT_PATH_PATTERN.fullmatch(parsed.path) or "://" in path:
        raise ValueError("chemin documentaire public invalide")
    if parsed.query != "" and re.fullmatch(
        r"limit=[1-9][0-9]{0,2}(?:&cursor=DOC-[A-Za-z0-9-]+)?",
        parsed.query,
    ) is None:
        raise ValueError("pagination documentaire publique invalide")
    return path


def _ensure_document_command_path(value: str) -> str:
    path = _ensure_public_relative_path(value)
    if path == "/v1/documents" or _DIAGNOSE_PATH_PATTERN.fullmatch(path) is not None:
        return path
    raise ValueError("commande documentaire UI interdite")


def _ensure_document_id(value: str) -> str:
    document_id = _ensure_text(value, "document_id requis")
    if "/" in document_id:
        raise ValueError("document_id invalide")
    return document_id


def _ensure_method(value: str) -> str:
    if value not in ("GET", "POST"):
        raise ValueError("méthode UI invalide")
    return value


def _ensure_text(value: Any, message: str) -> str:
    if not isinstance(value, str) or value == "" or value != value.strip():
        raise ValueError(message)
    return value


__all__ = [
    "ORCHESTRATOR_API_UNAVAILABLE",
    "UI_DOCUMENT_PAGE_SIZE",
    "UiDocumentApiClient",
    "UiDocumentApiPublicError",
    "UiDocumentApiResponse",
    "UiDocumentApiUnavailableError",
    "UiDocumentJsonResponse",
    "UrllibUiDocumentApiTransport",
]
