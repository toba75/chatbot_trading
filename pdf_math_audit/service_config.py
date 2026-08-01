from __future__ import annotations

import os
from dataclasses import dataclass, fields


@dataclass(frozen=True)
class ServiceConfig:
    max_pdf_bytes: int
    max_docling_bytes: int
    timeout_seconds: int
    upload_timeout_seconds: int
    process_shutdown_seconds: int
    concurrency: int
    upload_chunk_bytes: int
    artifact_chunk_bytes: int
    max_form_field_bytes: int
    multipart_spool_bytes: int

    @classmethod
    def from_env(cls) -> ServiceConfig:
        names = {
            "max_pdf_bytes": "MATH_AUDIT_MAX_PDF_BYTES",
            "max_docling_bytes": "MATH_AUDIT_MAX_DOCLING_BYTES",
            "timeout_seconds": "MATH_AUDIT_TIMEOUT_SECONDS",
            "upload_timeout_seconds": "MATH_AUDIT_UPLOAD_TIMEOUT_SECONDS",
            "process_shutdown_seconds": "MATH_AUDIT_PROCESS_SHUTDOWN_SECONDS",
            "concurrency": "MATH_AUDIT_CONCURRENCY",
            "upload_chunk_bytes": "MATH_AUDIT_UPLOAD_CHUNK_BYTES",
            "artifact_chunk_bytes": "MATH_AUDIT_ARTIFACT_CHUNK_BYTES",
            "max_form_field_bytes": "MATH_AUDIT_MAX_FORM_FIELD_BYTES",
            "multipart_spool_bytes": "MATH_AUDIT_MULTIPART_SPOOL_BYTES",
        }
        return cls(
            **{field: int(os.environ[variable]) for field, variable in names.items()}
        )

    def validate(self) -> None:
        for field in fields(self):
            if getattr(self, field.name) <= 0:
                raise ValueError(f"{field.name} doit être strictement positif")
