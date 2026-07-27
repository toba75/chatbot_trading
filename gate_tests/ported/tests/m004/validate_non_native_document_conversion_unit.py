"""Invariants T-005 des routes Granite-Docling et OCRmyPDF (ADR-002/003/032)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.source_processing.application.granite_gemma_recovery import (
    GraniteConversionFailure,
)
from app.source_processing.application.targeted_enrichment import (
    TargetedEnrichmentPageConverter,
)
from app.source_processing.application.convert_routed_pages import (
    ConvertRoutedPagesHandler,
    PageConversionRequest,
    PagePreprocessingRequest,
)
from app.source_processing.domain.document_processing_run import (
    PageNumber,
    PageRouteName,
    ProcessingRunId,
    RoutingPolicyVersion,
)
from app.source_processing.domain.page_conversion import (
    ConversionToolName,
    PageConversionArtifact,
    PageConversionItem,
    PageConversionItemLabel,
    PageItemGeometry,
    PreprocessedPageArtifact,
)
from app.source_processing.domain.source_document import DocumentId


def _granite_runtime():
    try:
        from app.source_processing.adapters import docling_granite_conversion
    except ImportError as error:
        pytest.fail(
            "GRANITE_DOCLING_RUNTIME_ABSENT: T-005 doit livrer Granite-Docling scellé."
        )
        raise AssertionError("pytest.fail doit interrompre le test") from error
    return docling_granite_conversion


def _ocr_runtime():
    try:
        from app.source_processing.adapters import ocrmypdf_container
    except ImportError as error:
        pytest.fail(
            "OCRMYPDF_RUNTIME_ABSENT: T-005 doit livrer OCRmyPDF conteneurisé."
        )
        raise AssertionError("pytest.fail doit interrompre le test") from error
    return ocrmypdf_container


def _request(route_name: PageRouteName) -> PageConversionRequest:
    return PageConversionRequest(
        processing_run_id=ProcessingRunId.from_value("RUN-M004-T005-UNIT"),
        document_id=DocumentId.from_value("DOC-0000000000000001"),
        page_number=PageNumber.from_value(1),
        route_name=route_name,
        routing_policy_version=RoutingPolicyVersion.from_value("routing-v1"),
        source_artifact_ref=(
            "artifact:source_processing.original_sources/"
            "DOC-0000000000000001/original.pdf"
        ),
        expected_output_artifact_ref=(
            "artifact:source_processing.page_conversion/"
            "RUN-M004-T005-UNIT/page-001-route.json"
        ),
    )


def _preprocessing_request() -> PagePreprocessingRequest:
    request = _request(PageRouteName.PREPROCESS_GRANITE)
    return PagePreprocessingRequest(
        processing_run_id=request.processing_run_id,
        document_id=request.document_id,
        page_number=request.page_number,
        route_name=request.route_name,
        routing_policy_version=request.routing_policy_version,
        source_artifact_ref=request.source_artifact_ref,
        expected_output_artifact_ref=(
            "artifact:source_processing.page_conversion/"
            "RUN-M004-T005-UNIT/page-001-preprocessed.pdf"
        ),
    )


def _item(text: str) -> PageConversionItem:
    return PageConversionItem(
        label=PageConversionItemLabel.TEXT,
        text=text,
        geometry=PageItemGeometry(
            left=0.1,
            top=0.1,
            right=0.9,
            bottom=0.2,
            page_width=1.0,
            page_height=1.0,
        ),
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def _output(request: PageConversionRequest, tool_name: ConversionToolName) -> PageConversionArtifact:
    return PageConversionArtifact(
        page_number=request.page_number,
        route_name=request.route_name,
        tool_name=tool_name,
        tool_version="2.111.0",
        artifact_hash="a" * 64,
        audit_artifact_ref=request.expected_output_artifact_ref,
        items=(_item("Sortie réellement fournie par l'outil imposé."),),
    )


class _GraniteOnly:
    def convert_page(self, request: PageConversionRequest) -> PageConversionArtifact:
        return _output(request, ConversionToolName.GRANITE_DOCLING)


class _NativeOnly:
    def convert_page(self, request: PageConversionRequest) -> PageConversionArtifact:
        return _output(request, ConversionToolName.DOCLING_STANDARD)


class _UnavailableGranite:
    def __init__(self) -> None:
        self.requests: list[PageConversionRequest] = []

    def convert_page(self, request: PageConversionRequest) -> PageConversionArtifact:
        self.requests.append(request)
        raise GraniteConversionFailure("GRANITE_DOCLING_UNAVAILABLE")


class _RecordingNative:
    def __init__(self) -> None:
        self.requests: list[PageConversionRequest] = []

    def convert_page(self, request: PageConversionRequest) -> PageConversionArtifact:
        self.requests.append(request)
        return _output(request, ConversionToolName.DOCLING_STANDARD)


class _ConditionalOcr:
    def preprocess_page(self, request: PagePreprocessingRequest) -> PreprocessedPageArtifact:
        return PreprocessedPageArtifact(
            page_number=request.page_number,
            route_name=request.route_name,
            tool_name=ConversionToolName.OCRMYPDF,
            tool_version="17.8.0",
            artifact_hash="b" * 64,
            artifact_ref=request.expected_output_artifact_ref,
        )


def test_granite_manifest_is_sealed_to_the_required_model_and_revision(tmp_path: Path) -> None:
    # Given l'adaptateur Granite-Docling imposé par SCAN_GRANITE et ses routes sœurs.
    # When son manifeste d'actifs est chargé.
    # Then il refuse tout modèle, toute révision ou tout SHA-256 qui ne correspondent pas au scellement.
    runtime = _granite_runtime()
    assets_root = tmp_path / "assets"
    model_file = assets_root / "ibm-granite--granite-docling-258M" / "config.json"
    model_file.parent.mkdir(parents=True)
    model_file.write_text('{"model_type":"granite_docling"}', encoding="utf-8")
    digest = hashlib.sha256(model_file.read_bytes()).hexdigest()
    manifest_path = tmp_path / "granite-assets.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "tool": "granite_docling",
                "tool_version": "2.111.0",
                "model_repository": "ibm-granite/granite-docling-258M",
                "model_revision": runtime.GRANITE_DOCLING_MODEL_REVISION,
                "assets": [
                    {
                        "relative_path": "ibm-granite--granite-docling-258M/config.json",
                        "sha256": digest,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    manifest = runtime.GraniteDoclingAssetManifest.load(
        manifest_path=manifest_path,
        assets_root=assets_root,
    )
    assert manifest.model_repository == "ibm-granite/granite-docling-258M"
    assert manifest.model_revision == runtime.GRANITE_DOCLING_MODEL_REVISION

    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8").replace(
            "ibm-granite/granite-docling-258M", "another/model"
        ),
        encoding="utf-8",
    )
    with pytest.raises(runtime.GraniteDoclingAssetManifestError, match="CONVERSION_ASSET_MANIFEST_INVALID"):
        runtime.GraniteDoclingAssetManifest.load(
            manifest_path=manifest_path,
            assets_root=assets_root,
        )


def test_ocrmypdf_manifest_refuses_an_unpinned_image_and_no_network_command(tmp_path: Path) -> None:
    # Given PREPROCESS_GRANITE est explicitement admise par M-003.
    # When le préprocesseur OCRmyPDF est préparé.
    # Then seule une image Docker par digest est acceptée et le conteneur ne reçoit pas de réseau.
    runtime = _ocr_runtime()
    manifest_path = tmp_path / "ocrmypdf-image.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "tool": "ocrmypdf",
                "tool_version": "17.8.0",
                "image_reference": "jbarlow83/ocrmypdf:v17.8.0",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(runtime.OcrmyPdfImageManifestError, match="CONVERSION_ASSET_MANIFEST_INVALID"):
        runtime.OcrmyPdfImageManifest.load(manifest_path=manifest_path, require_local_image=False)

    image_reference = (
        "jbarlow83/ocrmypdf@sha256:"
        "88d50f2ce7c054e5aacfc48794eca50dbb8af9a6ef1d2a540456dcd9a4687e42"
    )
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "tool": "ocrmypdf",
                "tool_version": "17.8.0",
                "image_reference": image_reference,
            }
        ),
        encoding="utf-8",
    )
    manifest = runtime.OcrmyPdfImageManifest.load(
        manifest_path=manifest_path,
        require_local_image=False,
    )
    output_directory = tmp_path / "output"
    output_directory.mkdir()
    command = runtime.build_ocrmypdf_container_command(
        image_reference=manifest.image_reference,
        source_path=tmp_path / "source.pdf",
        output_path=output_directory / "preprocessed.pdf",
        page_number=1,
    )
    assert "--network" in command
    assert command[command.index("--network") + 1] == "none"
    assert "--read-only" in command
    assert "--user" in command
    output_identity = f"{output_directory.stat().st_uid}:{output_directory.stat().st_gid}"
    assert command[command.index("--user") + 1] == output_identity
    assert image_reference in command


def test_every_non_native_route_calls_granite_and_ocr_is_never_global() -> None:
    # Given chaque route M-003 est déjà publiée.
    # When ConvertRoutedPages délègue la page.
    # Then SCAN_GRANITE, BAD_OCR_TO_GRANITE et MIXED_PAGEWISE n'acceptent que
    #      GRANITE_DOCLING, tandis que seul PREPROCESS_GRANITE passe d'abord par OCRmyPDF.
    handler = ConvertRoutedPagesHandler(
        native_converter=_NativeOnly(),
        granite_converter=_GraniteOnly(),
        ocrmypdf_preprocessor=_ConditionalOcr(),
    )
    for route_name in (
        PageRouteName.SCAN_GRANITE,
        PageRouteName.BAD_OCR_TO_GRANITE,
        PageRouteName.MIXED_PAGEWISE,
    ):
        output = handler._granite_converter.convert_page(_request(route_name))
        assert output.tool_name is ConversionToolName.GRANITE_DOCLING

    preprocessed = handler._ocrmypdf_preprocessor.preprocess_page(_preprocessing_request())
    assert preprocessed.route_name is PageRouteName.PREPROCESS_GRANITE
    assert preprocessed.tool_name is ConversionToolName.OCRMYPDF


def test_targeted_enrichment_adjudicates_native_after_explicit_granite_unavailability() -> None:
    # Given TARGETED_ENRICHMENT possède un candidat Docling valide et Granite
    # termine avec un code d'indisponibilité explicitement autorisé.
    native = _RecordingNative()
    granite = _UnavailableGranite()
    converter = TargetedEnrichmentPageConverter(
        native_converter=native,
        granite_converter=granite,
        policy_version="targeted-enrichment-v1",
    )

    # When l'enrichissement ciblé est exécuté.
    request = _request(PageRouteName.TARGETED_ENRICHMENT)
    output = converter.convert_page(request)

    # Then Docling est l'autorité explicite, les tentatives sont distinctes et
    # aucune récupération Gemma n'appartient à cette chaîne.
    assert len(native.requests) == 1
    assert len(granite.requests) == 1
    assert native.requests[0].expected_output_artifact_ref.endswith("-native-candidate.json")
    assert granite.requests[0].expected_output_artifact_ref.endswith("-granite-candidate.json")
    assert output.audit_artifact_ref == request.expected_output_artifact_ref
    assert output.tool_name is ConversionToolName.DOCLING_STANDARD
    assert output.fallback_trace is None
    assert output.adjudication_trace is not None
    assert output.adjudication_trace.policy_version == "targeted-enrichment-v1"
    assert output.adjudication_trace.selected_tool_name is ConversionToolName.DOCLING_STANDARD
    assert output.adjudication_trace.granite_error_code == "GRANITE_DOCLING_UNAVAILABLE"
    assert output.adjudication_trace.native_candidate_artifact_ref == (
        native.requests[0].expected_output_artifact_ref
    )
    assert output.adjudication_trace.granite_candidate_artifact_ref is None
    assert output.adjudication_trace.to_payload()["justification"]
