"""Contrats UI de la conversion native réellement exécutable (ADR-031)."""

from __future__ import annotations

from app.contracts.document_public_statuses import PublicActionPhase
from app.platform.orchestrator_api_models import DocumentActionProgressResponse
from app.platform.ui_corpus import (
    CorpusPdfDocument,
    CorpusPdfScreenState,
    render_corpus_pdf_screen,
    render_document_inspection,
)
from app.platform.ui_document_api import (
    UiDocumentApiClient,
    UiDocumentApiResponse,
)
from app.source_processing.application.document_queries import DocumentActionProgressView


class _Transport:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str]] = []

    def request(
        self,
        *,
        method: str,
        path: str,
        body: bytes | None,
        content_type: str | None,
    ) -> UiDocumentApiResponse:
        self.requests.append((method, path))
        return UiDocumentApiResponse(
            status_code=200,
            content_type="application/json",
            body=(
                b'{"action_name":"CONVERT_DOCUMENT","phase":"RUNNING",'
                b'"completed_units":0,"total_units":2,"failure_error_code":null}'
            ),
        )


def test_le_contrat_pydantic_accepte_la_progression_de_conversion() -> None:
    # Given une conversion native acceptée mais dont le worker travaille réellement.
    # When l'API publie sa progression persistée.
    # Then le DTO public admet CONVERT_DOCUMENT et ses unités sans statut synthétique.
    progress = DocumentActionProgressResponse.model_validate(
        {
            "action_name": "CONVERT_DOCUMENT",
            "phase": "RUNNING",
            "completed_units": 0,
            "total_units": 2,
            "failure_error_code": None,
        }
    )

    assert progress.action_name == "CONVERT_DOCUMENT"
    assert progress.phase is PublicActionPhase.RUNNING


def test_le_bouton_convertir_est_limite_a_la_route_native_disponible() -> None:
    # Given deux documents routés, dont seul le premier possède la capacité
    # publique de conversion native entièrement disponible.
    # When l'UI rend le corpus à partir du read-model public.
    # Then elle n'expose Convertir que pour ce premier document.
    native = CorpusPdfDocument(
        document_id="DOC-1111111111111111",
        title="PDF natif",
        source_status="REGISTERED",
        diagnostic_status="ROUTE_PLANNED",
        conversion_status="CONVERSION_NOT_REQUESTED",
        canonical_version_id=None,
        projection_status="PROJECTION_NOT_REQUESTED",
        selected=False,
        manual_review_reason=None,
        failure_error_code=None,
        conversion_action_available=True,
    )
    non_native = CorpusPdfDocument(
        document_id="DOC-2222222222222222",
        title="PDF Granite",
        source_status="REGISTERED",
        diagnostic_status="ROUTE_PLANNED",
        conversion_status="CONVERSION_NOT_REQUESTED",
        canonical_version_id=None,
        projection_status="PROJECTION_NOT_REQUESTED",
        selected=False,
        manual_review_reason=None,
        failure_error_code=None,
        conversion_action_available=False,
    )

    html = render_corpus_pdf_screen(
        CorpusPdfScreenState(
            documents=(native, non_native),
            active_selected_document_ids=(),
            read_model_status="READ_MODEL_READY",
            current_cursor=None,
            next_cursor=None,
            registration_notice=None,
        )
    )

    assert 'action="/v1/documents/DOC-1111111111111111/convert"' in html
    assert '>Convertir</button>' in html
    assert 'action="/v1/documents/DOC-2222222222222222/convert"' not in html


def test_la_conversion_en_cours_est_inspectable_et_se_rafraichit() -> None:
    # Given une progression CONVERT_DOCUMENT réellement persistée par le worker.
    # When l'utilisateur ouvre l'inspection de conversion.
    # Then l'UI rend phase, unités persistées et rafraîchit tant qu'elle est non terminale.
    progress = DocumentActionProgressView(
        action_name="CONVERT_DOCUMENT",
        phase=PublicActionPhase.RUNNING,
        completed_units=0,
        total_units=2,
        failure_error_code=None,
    )
    html = render_document_inspection(
        title="Conversion",
        response=type(
            "Response",
            (),
            {
                "status_code": 200,
                "payload": {
                    "document_id": "DOC-1111111111111111",
                    "conversion_status": "CONVERSION_REQUESTED",
                    "qa_rejection_error_code": None,
                    "canonical_version_id": None,
                },
            },
        )(),
        action_progress=progress,
    )

    assert "CONVERT_DOCUMENT" in html
    assert "RUNNING" in html
    assert "0 / 2" in html
    assert 'http-equiv="refresh"' in html


def test_le_client_ui_appelle_les_routes_publiques_de_conversion() -> None:
    # Given le client UI du seul contrat orchestrateur.
    # When il transmet Convertir puis lit la progression de conversion.
    # Then il n'utilise que POST /convert et GET /conversion/progress relatifs.
    transport = _Transport()
    client = UiDocumentApiClient(transport=transport)

    command = client.forward_document_command(
        path="/v1/documents/DOC-1111111111111111/convert",
        body=b"",
        content_type="application/octet-stream",
    )
    progress = client.read_document_action_progress(
        "DOC-1111111111111111",
        "CONVERT_DOCUMENT",
    )

    assert command.status_code == 200
    assert progress.payload["action_name"] == "CONVERT_DOCUMENT"
    assert transport.requests == [
        ("POST", "/v1/documents/DOC-1111111111111111/convert"),
        ("GET", "/v1/documents/DOC-1111111111111111/conversion/progress"),
    ]
