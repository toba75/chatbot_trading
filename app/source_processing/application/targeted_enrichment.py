"""Adjudication explicite de la route M-004 TARGETED_ENRICHMENT."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace

from app.source_processing.application.convert_routed_pages import (
    PageConversionRequest,
    PageConverter,
)
from app.source_processing.application.granite_gemma_recovery import (
    GEMMA_RECOVERY_GRANITE_ERROR_CODES,
    GraniteConversionFailure,
)
from app.source_processing.domain.document_processing_run import PageRouteName
from app.source_processing.domain.page_conversion import (
    ConversionToolName,
    PageConversionArtifact,
    TargetedEnrichmentAdjudicationTrace,
)


class TargetedEnrichmentPageConverter:
    """Compare Docling et Granite sans appeler la récupération Gemma."""

    def __init__(
        self,
        *,
        native_converter: PageConverter,
        granite_converter: PageConverter,
        policy_version: str,
    ) -> None:
        if not callable(getattr(native_converter, "convert_page", None)):
            raise ValueError("native_converter ciblé invalide")
        if not callable(getattr(granite_converter, "convert_page", None)):
            raise ValueError("granite_converter ciblé invalide")
        if not isinstance(policy_version, str) or policy_version.strip() == "" or policy_version != policy_version.strip():
            raise ValueError("version d'adjudication ciblée invalide")
        self._native_converter = native_converter
        self._granite_converter = granite_converter
        self._policy_version = policy_version

    def convert_page(self, request: PageConversionRequest) -> PageConversionArtifact:
        if not isinstance(request, PageConversionRequest):
            raise ValueError("requête d'enrichissement ciblé invalide")
        if request.route_name is not PageRouteName.TARGETED_ENRICHMENT:
            raise ValueError("route d'enrichissement ciblé invalide")

        native_request = replace(
            request,
            expected_output_artifact_ref=_candidate_ref(
                request.expected_output_artifact_ref,
                "native",
            ),
        )
        native_candidate = self._native_converter.convert_page(native_request)
        _ensure_candidate(
            native_candidate,
            request=native_request,
            expected_tool=ConversionToolName.DOCLING_STANDARD,
        )

        granite_request = replace(
            request,
            expected_output_artifact_ref=_candidate_ref(
                request.expected_output_artifact_ref,
                "granite",
            ),
        )
        try:
            granite_candidate = self._granite_converter.convert_page(granite_request)
        except GraniteConversionFailure as error:
            if error.code not in GEMMA_RECOVERY_GRANITE_ERROR_CODES:
                raise
            trace = TargetedEnrichmentAdjudicationTrace(
                policy_version=self._policy_version,
                selected_tool_name=ConversionToolName.DOCLING_STANDARD,
                native_candidate_artifact_hash=native_candidate.artifact_hash,
                native_candidate_artifact_ref=native_candidate.audit_artifact_ref,
                granite_candidate_artifact_hash=None,
                granite_candidate_artifact_ref=None,
                granite_error_code=error.code,
                justification=(
                    "Candidat Docling standard retenu après l'échec Granite "
                    f"explicitement autorisé {error.code}."
                ),
            )
            return _adjudicated_output(
                selected=native_candidate,
                final_artifact_ref=request.expected_output_artifact_ref,
                trace=trace,
            )

        _ensure_candidate(
            granite_candidate,
            request=granite_request,
            expected_tool=ConversionToolName.GRANITE_DOCLING,
        )
        trace = TargetedEnrichmentAdjudicationTrace(
            policy_version=self._policy_version,
            selected_tool_name=ConversionToolName.GRANITE_DOCLING,
            native_candidate_artifact_hash=native_candidate.artifact_hash,
            native_candidate_artifact_ref=native_candidate.audit_artifact_ref,
            granite_candidate_artifact_hash=granite_candidate.artifact_hash,
            granite_candidate_artifact_ref=granite_candidate.audit_artifact_ref,
            granite_error_code=None,
            justification="Candidat Granite retenu après enrichissement ciblé réussi.",
        )
        return _adjudicated_output(
            selected=granite_candidate,
            final_artifact_ref=request.expected_output_artifact_ref,
            trace=trace,
        )


def _candidate_ref(final_ref: str, candidate_name: str) -> str:
    if not final_ref.endswith(".json"):
        raise ValueError("référence finale d'enrichissement ciblé invalide")
    return f"{final_ref[:-5]}-{candidate_name}-candidate.json"


def _ensure_candidate(
    candidate: PageConversionArtifact,
    *,
    request: PageConversionRequest,
    expected_tool: ConversionToolName,
) -> None:
    if not isinstance(candidate, PageConversionArtifact):
        raise ValueError("candidat d'enrichissement ciblé invalide")
    if candidate.page_number != request.page_number or candidate.route_name != request.route_name:
        raise ValueError("candidat d'enrichissement ciblé incohérent")
    if candidate.tool_name is not expected_tool:
        raise ValueError("outil candidat d'enrichissement ciblé incohérent")
    if candidate.audit_artifact_ref != request.expected_output_artifact_ref:
        raise ValueError("référence candidate d'enrichissement ciblé incohérente")
    if candidate.fallback_trace is not None or candidate.adjudication_trace is not None:
        raise ValueError("trace candidate d'enrichissement ciblé interdite")


def _adjudicated_output(
    *,
    selected: PageConversionArtifact,
    final_artifact_ref: str,
    trace: TargetedEnrichmentAdjudicationTrace,
) -> PageConversionArtifact:
    payload = {
        "page_number": selected.page_number.value,
        "route_name": selected.route_name.value,
        "selected_tool_name": selected.tool_name.value,
        "selected_candidate_artifact_hash": selected.artifact_hash,
        "adjudication_trace": trace.to_payload(),
        "content_hashes": tuple(item.content_hash for item in selected.items),
    }
    return PageConversionArtifact(
        page_number=selected.page_number,
        route_name=selected.route_name,
        tool_name=selected.tool_name,
        tool_version=selected.tool_version,
        artifact_hash=hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        audit_artifact_ref=final_artifact_ref,
        items=selected.items,
        adjudication_trace=trace,
    )


__all__ = ["TargetedEnrichmentPageConverter"]
