"""Récupération Gemma explicitement autorisée après un échec Granite tracé."""

from __future__ import annotations

from typing import Protocol

from app.source_processing.application.convert_routed_pages import (
    PageConversionRequest,
    PageConverter,
)
from app.source_processing.domain.page_conversion import (
    ConversionToolName,
    PageConversionArtifact,
    PageConversionFallbackTrace,
)


GEMMA_RECOVERY_GRANITE_ERROR_CODES = frozenset(
    {
        "DOCLING_PROVENANCE_MISSING",
        "GRANITE_DOCLING_UNAVAILABLE",
    }
)


class GraniteConversionFailure(RuntimeError):
    """Échec Granite transmis au décideur de récupération M-004."""

    def __init__(self, code: str) -> None:
        if not isinstance(code, str) or code.strip() == "" or code != code.strip():
            raise ValueError("code d'échec Granite invalide")
        self.code = code
        super().__init__(code)


class GemmaRecoveryPageConverter(Protocol):
    """Port réservé à Gemma après un échec Granite explicitement admis."""

    def recover_page(
        self,
        request: PageConversionRequest,
        *,
        granite_error_code: str,
    ) -> PageConversionArtifact:
        """Produit une sortie Gemma VLM avec sa trace de récupération."""


class GraniteThenGemmaPageConverter:
    """Applique ADR-036 sans masquer la première tentative Granite."""

    def __init__(
        self,
        *,
        granite_converter: PageConverter,
        gemma_converter: GemmaRecoveryPageConverter,
    ) -> None:
        if not callable(getattr(granite_converter, "convert_page", None)):
            raise ValueError("granite_converter invalide")
        if not callable(getattr(gemma_converter, "recover_page", None)):
            raise ValueError("gemma_converter invalide")
        self._granite_converter = granite_converter
        self._gemma_converter = gemma_converter

    def convert_page(self, request: PageConversionRequest) -> PageConversionArtifact:
        if not isinstance(request, PageConversionRequest):
            raise ValueError("requête de récupération Granite/Gemma invalide")
        try:
            return self._granite_converter.convert_page(request)
        except GraniteConversionFailure as error:
            if error.code not in GEMMA_RECOVERY_GRANITE_ERROR_CODES:
                raise
            granite_error_code = error.code
            recovered = self._gemma_converter.recover_page(
                request,
                granite_error_code=granite_error_code,
            )
        _ensure_explicit_gemma_recovery(recovered, granite_error_code=granite_error_code)
        return recovered


def _ensure_explicit_gemma_recovery(
    page_output: PageConversionArtifact,
    *,
    granite_error_code: str,
) -> None:
    if not isinstance(page_output, PageConversionArtifact):
        raise ValueError("sortie de récupération Gemma invalide")
    if page_output.tool_name is not ConversionToolName.GEMMA_VISION:
        raise ValueError("outil de récupération Gemma incohérent")
    expected_trace = PageConversionFallbackTrace(
        triggering_tool_name=ConversionToolName.GRANITE_DOCLING,
        triggering_error_code=granite_error_code,
    )
    if page_output.fallback_trace != expected_trace:
        raise ValueError("trace de récupération Gemma incohérente")


__all__ = [
    "GEMMA_RECOVERY_GRANITE_ERROR_CODES",
    "GemmaRecoveryPageConverter",
    "GraniteConversionFailure",
    "GraniteThenGemmaPageConverter",
]
