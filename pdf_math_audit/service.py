from __future__ import annotations

import asyncio
import hashlib
import re
import subprocess
import tempfile
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from starlette.datastructures import FormData, UploadFile
from starlette.formparsers import MultiPartException

from pdf_math_audit.bounded_multipart import BoundedMultiPartParser, UploadTooLarge
from pdf_math_audit.contract import CAPABILITY_PROFILE, CONTRACT_VERSION
from pdf_math_audit.service_config import ServiceConfig
from pdf_math_audit.service_process import (
    AnalysisSession,
    ProcessFactory,
    start_analysis,
    stream_analysis,
)
from pdf_math_audit.service_protocol import ndjson_line


async def _save_upload(
    upload: UploadFile,
    destination: Path,
    maximum: int,
    chunk_bytes: int,
    overflow_message: str,
) -> None:
    size = 0
    with destination.open("wb") as output:
        while chunk := await upload.read(chunk_bytes):
            size += len(chunk)
            if size > maximum:
                raise HTTPException(status_code=413, detail=overflow_message)
            output.write(chunk)


def _matches(path: Path, announced_sha256: str) -> bool:
    with path.open("rb") as content:
        return hashlib.file_digest(content, "sha256").hexdigest() == announced_sha256


def _field(form: FormData, name: str, expected_type: type) -> object:
    value = form[name]
    if not isinstance(value, expected_type):
        raise HTTPException(status_code=422, detail=f"Champ multipart invalide : {name}")
    return value


def _start_failure() -> StreamingResponse:
    event = ndjson_line(
        {
            "type": "error",
            "code": "analysis_start_failed",
            "message": "Le processus d’analyse n’a pas pu démarrer.",
        }
    )
    return StreamingResponse(iter([event]), media_type="application/x-ndjson")


def create_app(
    config: ServiceConfig,
    *,
    process_factory: ProcessFactory = subprocess.Popen,
) -> FastAPI:
    config.validate()
    semaphore = threading.BoundedSemaphore(config.concurrency)
    app = FastAPI(title="PDF Math Audit", version="1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/qualifications")
    async def qualify(request: Request) -> StreamingResponse:
        if not semaphore.acquire(blocking=False):
            raise HTTPException(status_code=429, detail="Capacité d’analyse saturée.")

        directory: tempfile.TemporaryDirectory[str] | None = None
        transferred = False
        try:
            try:
                async with asyncio.timeout(config.upload_timeout_seconds):
                    parser = BoundedMultiPartParser(
                        request.headers,
                        request.stream(),
                        part_limits={
                            "source_pdf": config.max_pdf_bytes,
                            "docling_document": config.max_docling_bytes,
                            "source_sha256": config.max_form_field_bytes,
                            "docling_document_sha256": config.max_form_field_bytes,
                            "contract_version": config.max_form_field_bytes,
                            "capability_profile": config.max_form_field_bytes,
                        },
                        spool_bytes=config.multipart_spool_bytes,
                    )
                    form = await parser.parse_exact()
                    try:
                        directory = tempfile.TemporaryDirectory(
                            prefix="pdf-math-audit-"
                        )
                        root = Path(directory.name)
                        source_pdf = _field(form, "source_pdf", UploadFile)
                        docling_document = _field(
                            form, "docling_document", UploadFile
                        )
                        source_sha256 = _field(form, "source_sha256", str)
                        document_sha256 = _field(
                            form, "docling_document_sha256", str
                        )
                        contract_version = _field(form, "contract_version", str)
                        capability_profile = _field(
                            form, "capability_profile", str
                        )
                        if (
                            re.fullmatch(r"[0-9a-f]{64}", source_sha256) is None
                            or re.fullmatch(r"[0-9a-f]{64}", document_sha256)
                            is None
                            or contract_version != CONTRACT_VERSION
                            or capability_profile != CAPABILITY_PROFILE
                        ):
                            raise HTTPException(
                                status_code=422,
                                detail="Contrat d’analyse invalide.",
                            )
                        await _save_upload(
                            source_pdf,
                            root / "source.pdf",
                            config.max_pdf_bytes,
                            config.upload_chunk_bytes,
                            "Le PDF source dépasse la taille autorisée.",
                        )
                        await _save_upload(
                            docling_document,
                            root / "document.json",
                            config.max_docling_bytes,
                            config.upload_chunk_bytes,
                            "Le DoclingDocument dépasse la taille autorisée.",
                        )
                        if not _matches(root / "source.pdf", source_sha256) or not _matches(
                            root / "document.json", document_sha256
                        ):
                            raise HTTPException(
                                status_code=422,
                                detail=(
                                    "Une empreinte SHA-256 annoncée ne correspond "
                                    "pas au fichier reçu."
                                ),
                            )
                    finally:
                        await form.close()
            except TimeoutError as error:
                raise HTTPException(
                    status_code=408,
                    detail="La durée maximale de réception est dépassée.",
                ) from error
            except UploadTooLarge as error:
                messages = {
                    "source_pdf": "Le PDF source dépasse la taille autorisée.",
                    "docling_document": (
                        "Le DoclingDocument dépasse la taille autorisée."
                    ),
                }
                raise HTTPException(
                    status_code=413,
                    detail=messages.get(
                        error.field_name,
                        "Un champ dépasse la taille autorisée.",
                    ),
                ) from error
            except MultiPartException as error:
                raise HTTPException(status_code=400, detail=str(error)) from error

            try:
                process = start_analysis(
                    directory=directory,
                    process_factory=process_factory,
                    source_sha256=source_sha256,
                    document_sha256=document_sha256,
                    config=config,
                )
            except OSError:
                return _start_failure()

            session = AnalysisSession(
                directory=directory,
                semaphore=semaphore,
                process=process,
                shutdown_seconds=config.process_shutdown_seconds,
            )
            response = StreamingResponse(
                stream_analysis(session, config=config),
                media_type="application/x-ndjson",
                background=BackgroundTask(session.close),
            )
            transferred = True
            return response
        finally:
            if not transferred:
                if directory is not None:
                    directory.cleanup()
                semaphore.release()

    return app
