"""Routeur FastAPI strict des commandes documentaires publiques SP."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import tempfile
from typing import Any, Protocol

from fastapi import APIRouter, Request, UploadFile
from fastapi.responses import JSONResponse
from starlette.datastructures import FormData, UploadFile as StarletteUploadFile
from starlette.exceptions import HTTPException as StarletteHttpException
from starlette.concurrency import run_in_threadpool

from app.source_processing.adapters.document_http import HttpRequest, HttpResponse
from app.platform.orchestrator_api_models import (
    ConversionAcceptedResponse,
    DiagnosticAcceptedResponse,
    DocumentDuplicateResponse,
    DocumentRegisteredResponse,
    DOCUMENT_MULTIPART_OPENAPI,
    PUBLIC_ERROR_RESPONSES,
)


class DocumentHttpAdapter(Protocol):
    """Port de transport déjà traduit vers le contrat public M-003."""

    def handle(self, request: HttpRequest) -> HttpResponse:
        """Traite une commande documentaire sans connaître FastAPI."""


    def handle_staged_registration(
        self,
        *,
        original_path: Path,
        bibliographic_metadata: Mapping[str, Any] | None,
    ) -> HttpResponse: ...


class DocumentConversionHttpAdapter(Protocol):
    """Port HTTP M-004 sans streaming d'original."""

    def handle(self, request: HttpRequest) -> HttpResponse:
        """Traite uniquement POST /v1/documents/{id}/convert."""


def build_document_command_router(
    *,
    document_http_adapter: DocumentHttpAdapter,
    document_conversion_http_adapter: DocumentConversionHttpAdapter,
    max_pdf_bytes: int,
) -> APIRouter:
    """Construit les deux commandes documentaires et injecte leur adaptateur SP."""

    parsed_adapter = _ensure_document_http_adapter(document_http_adapter)
    parsed_conversion_adapter = _ensure_document_conversion_http_adapter(
        document_conversion_http_adapter
    )
    parsed_max_pdf_bytes = _ensure_max_pdf_bytes(max_pdf_bytes)
    router = APIRouter()

    @router.post(
        "/v1/documents",
        response_model=DocumentRegisteredResponse,
        status_code=201,
        responses={
            200: {"model": DocumentDuplicateResponse, "description": "Binaire déjà enregistré."},
            **PUBLIC_ERROR_RESPONSES,
        },
        openapi_extra=DOCUMENT_MULTIPART_OPENAPI,
    )
    async def register_document(request: Request) -> JSONResponse:
        if not _is_multipart_request(request):
            return _invalid_request("body")
        try:
            async with request.form(
                max_files=1,
                max_fields=1,
                max_part_size=1024,
            ) as form:
                return await _register_document(
                    form=form,
                    document_http_adapter=parsed_adapter,
                    max_pdf_bytes=parsed_max_pdf_bytes,
                )
        except StarletteHttpException:
            return _invalid_request("body")

    @router.post(
        "/v1/documents/{document_id}/diagnose",
        response_model=DiagnosticAcceptedResponse,
        status_code=202,
        responses=PUBLIC_ERROR_RESPONSES,
    )
    def diagnose_document(document_id: str, request: Request) -> JSONResponse:
        if _request_has_body(request):
            return _invalid_request("body")
        response = parsed_adapter.handle(
            HttpRequest(
                method="POST",
                path=f"/v1/documents/{document_id}/diagnose",
                body={},
            )
        )
        return _json_response(response)

    @router.post(
        "/v1/documents/{document_id}/convert",
        response_model=ConversionAcceptedResponse,
        status_code=202,
        responses=PUBLIC_ERROR_RESPONSES,
    )
    def convert_document(document_id: str, request: Request) -> JSONResponse:
        if _request_has_body(request):
            return _invalid_request("body")
        response = parsed_conversion_adapter.handle(
            HttpRequest(
                method="POST",
                path=f"/v1/documents/{document_id}/convert",
                body={},
            )
        )
        return _json_response(response)

    return router


async def _register_document(
    *,
    form: FormData,
    document_http_adapter: DocumentHttpAdapter,
    max_pdf_bytes: int,
) -> JSONResponse:
    if not isinstance(form, FormData):
        raise TypeError("formulaire multipart invalide")
    field_names = tuple(key for key, _ in form.multi_items())
    allowed_fields = frozenset({"original_content"})
    if any(field_name not in allowed_fields for field_name in field_names):
        return _invalid_request("body")

    files = form.getlist("original_content")
    if len(files) != 1 or not isinstance(files[0], StarletteUploadFile):
        return _invalid_request("original_content")
    upload: UploadFile | StarletteUploadFile = files[0]
    if upload.content_type != "application/pdf":
        return _invalid_request("original_content")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as staged:
        staged_path = Path(staged.name)
        staged_size = 0
        while chunk := await upload.read(64 * 1024):
            staged_size += len(chunk)
            if staged_size > max_pdf_bytes:
                staged.close()
                staged_path.unlink(missing_ok=True)
                return JSONResponse(
                    status_code=413,
                    content={"error_code": "HTTP_REQUEST_TOO_LARGE", "max_pdf_bytes": max_pdf_bytes},
                )
            staged.write(chunk)
    try:
        if staged_size == 0:
            return _invalid_request("original_content")
        response = await run_in_threadpool(
            document_http_adapter.handle_staged_registration,
            original_path=staged_path,
            bibliographic_metadata=None,
        )
        return _json_response(response)
    finally:
        staged_path.unlink(missing_ok=True)


def _is_multipart_request(request: Request) -> bool:
    content_type = request.headers.get("content-type")
    if content_type is None:
        return False
    return content_type.lower().startswith("multipart/form-data;")


def _request_has_body(request: Request) -> bool:
    content_length = request.headers.get("content-length")
    if content_length is None:
        return False
    if not content_length.isdecimal():
        return True
    return int(content_length) != 0


def _json_response(response: HttpResponse) -> JSONResponse:
    if not isinstance(response, HttpResponse):
        raise TypeError("réponse de l'adaptateur documentaire invalide")
    return JSONResponse(status_code=response.status_code, content=dict(response.body))


def _invalid_request(field_name: str) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error_code": "HTTP_REQUEST_INVALID", "field": field_name},
    )


def _ensure_document_http_adapter(value: Any) -> DocumentHttpAdapter:
    if not callable(getattr(value, "handle", None)):
        raise ValueError("document_http_adapter invalide")
    if not callable(getattr(value, "handle_staged_registration", None)):
        raise ValueError("document_http_adapter sans streaming")
    return value


def _ensure_document_conversion_http_adapter(value: Any) -> DocumentConversionHttpAdapter:
    if not callable(getattr(value, "handle", None)):
        raise ValueError("document_conversion_http_adapter invalide")
    return value


def _ensure_max_pdf_bytes(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("max_pdf_bytes invalide")
    return value


__all__ = [
    "DocumentConversionHttpAdapter",
    "DocumentHttpAdapter",
    "build_document_command_router",
]
