"""Routeur FastAPI strict des commandes documentaires publiques SP."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from fastapi import APIRouter, Request, UploadFile
from fastapi.responses import JSONResponse
from starlette.datastructures import FormData, UploadFile as StarletteUploadFile
from starlette.exceptions import HTTPException as StarletteHttpException
from starlette.concurrency import run_in_threadpool

from app.source_processing.adapters.document_http import HttpRequest, HttpResponse


class DocumentHttpAdapter(Protocol):
    """Port de transport déjà traduit vers le contrat public M-003."""

    def handle(self, request: HttpRequest) -> HttpResponse:
        """Traite une commande documentaire sans connaître FastAPI."""


MAX_TITLE_CHARACTERS = 512
MAX_AUTHOR_CHARACTERS = 256
MAX_AUTHORS = 16
MAX_EDITION_CHARACTERS = 64
MAX_PUBLICATION_YEAR = 9999


def build_document_command_router(
    *,
    document_http_adapter: DocumentHttpAdapter,
    max_pdf_bytes: int,
) -> APIRouter:
    """Construit les deux commandes documentaires et injecte leur adaptateur SP."""

    parsed_adapter = _ensure_document_http_adapter(document_http_adapter)
    parsed_max_pdf_bytes = _ensure_max_pdf_bytes(max_pdf_bytes)
    router = APIRouter()

    @router.post("/v1/documents")
    async def register_document(request: Request) -> JSONResponse:
        if not _is_multipart_request(request):
            return _invalid_request("body")
        try:
            async with request.form(
                max_files=1,
                max_fields=MAX_AUTHORS + 4,
                max_part_size=MAX_TITLE_CHARACTERS + 1,
            ) as form:
                return await _register_document(
                    form=form,
                    document_http_adapter=parsed_adapter,
                    max_pdf_bytes=parsed_max_pdf_bytes,
                )
        except StarletteHttpException:
            return _invalid_request("body")

    @router.post("/v1/documents/{document_id}/diagnose")
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
    allowed_fields = frozenset(
        {"original_content", "title", "authors", "publication_year", "edition"}
    )
    if any(field_name not in allowed_fields for field_name in field_names):
        return _invalid_request("body")

    files = form.getlist("original_content")
    if len(files) != 1 or not isinstance(files[0], StarletteUploadFile):
        return _invalid_request("original_content")
    upload: UploadFile | StarletteUploadFile = files[0]
    if upload.content_type != "application/pdf":
        return _invalid_request("original_content")

    metadata_or_error = _bibliographic_metadata(form)
    if isinstance(metadata_or_error, JSONResponse):
        return metadata_or_error

    original_content = await upload.read(max_pdf_bytes + 1)
    if len(original_content) == 0 or len(original_content) > max_pdf_bytes:
        return _invalid_request("original_content")

    response = await run_in_threadpool(
        document_http_adapter.handle,
        HttpRequest(
            method="POST",
            path="/v1/documents",
            body={
                "original_content": original_content,
                "bibliographic_metadata": metadata_or_error,
            },
        ),
    )
    return _json_response(response)


def _bibliographic_metadata(form: FormData) -> Mapping[str, Any] | JSONResponse:
    title = _single_text_field(form, "title")
    if title is None or len(title) > MAX_TITLE_CHARACTERS:
        return _invalid_request("title")
    authors = _repeated_text_field(form, "authors")
    if (
        authors is None
        or len(authors) > MAX_AUTHORS
        or any(len(author) > MAX_AUTHOR_CHARACTERS for author in authors)
    ):
        return _invalid_request("authors")
    publication_year_text = _single_text_field(form, "publication_year")
    if (
        publication_year_text is None
        or len(publication_year_text) > 4
        or not publication_year_text.isdecimal()
    ):
        return _invalid_request("publication_year")
    publication_year = int(publication_year_text)
    if publication_year < 1 or publication_year > MAX_PUBLICATION_YEAR:
        return _invalid_request("publication_year")
    edition = _single_text_field(form, "edition")
    if edition is None or len(edition) > MAX_EDITION_CHARACTERS:
        return _invalid_request("edition")
    return {
        "title": title,
        "authors": authors,
        "publication_year": publication_year,
        "edition": edition,
    }


def _single_text_field(form: FormData, field_name: str) -> str | None:
    values = form.getlist(field_name)
    if len(values) != 1:
        return None
    value = values[0]
    if not isinstance(value, str) or value == "" or value != value.strip():
        return None
    return value


def _repeated_text_field(form: FormData, field_name: str) -> tuple[str, ...] | None:
    values = form.getlist(field_name)
    if len(values) == 0:
        return None
    parsed: list[str] = []
    for value in values:
        if not isinstance(value, str) or value == "" or value != value.strip():
            return None
        parsed.append(value)
    return tuple(parsed)


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
    return value


def _ensure_max_pdf_bytes(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("max_pdf_bytes invalide")
    return value


__all__ = ["DocumentHttpAdapter", "build_document_command_router"]
