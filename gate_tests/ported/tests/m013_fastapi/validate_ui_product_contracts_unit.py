from __future__ import annotations

import json
from pathlib import Path

from app.contracts.document_public_statuses import (
    PublicActionPhase,
    PublicConversionStatus,
    PublicDiagnosticStatus,
    PublicSourceStatus,
)
from app.platform.configuration import load_application_configuration
from app.platform.local_runtime import build_ui_orchestrator_origin
from app.platform.ui_corpus import render_document_inspection
from app.platform.ui_document_api import (
    UiDocumentApiClient,
    UiDocumentApiResponse,
    UiDocumentJsonResponse,
)


class QueueTransport:
    def __init__(self, responses: list[UiDocumentApiResponse]) -> None:
        self.responses = responses

    def request(self, *, method, path, body, content_type):
        del method, path, body, content_type
        return self.responses.pop(0)


def _response(payload: dict[str, object], status: int = 200) -> UiDocumentApiResponse:
    return UiDocumentApiResponse(
        status_code=status,
        content_type="application/json",
        body=json.dumps(payload).encode("utf-8"),
    )


def _assert_diagnostic_rejected(
    payload: dict[str, object],
    expected_fragment: str,
) -> None:
    client = UiDocumentApiClient(transport=QueueTransport([_response(payload)]))
    try:
        client.read_diagnostic("DOC-M013-UI-CONTRACT")
    except ValueError as exc:
        assert expected_fragment in str(exc), str(exc)
        return
    raise AssertionError(f"Diagnostic invalide accepté : {expected_fragment}")


def test_validate_ui_product_contracts_unit() -> None:
    # Given SP expose ses statuts réels et une progression générique.
    # When le client UI les parse et rend le diagnostic.
    # Then les phases partagées, les compteurs et le rafraîchissement restent
    # publics, stricts et sans état de remplacement.
    assert {status.value for status in PublicSourceStatus} == {"REGISTERED", "QUARANTINED"}
    assert "DIAGNOSING" in {status.value for status in PublicDiagnosticStatus}
    assert {status.value for status in PublicActionPhase} == {
        "NOT_REQUESTED", "QUEUED", "RUNNING", "SUCCEEDED", "FAILED"
    }
    assert PublicConversionStatus.CANONICAL_ACCEPTED.value == "CANONICAL_ACCEPTED"

    document_id = "DOC-M013-UI-CONTRACT"
    valid_diagnostic = {
        "document_id": document_id,
        "diagnostic_status": "DIAGNOSING",
        "source_page_count": 2,
        "diagnosed_page_count": 0,
        "manual_review_reason": None,
        "failure_error_code": None,
        "manifest": [
            {"page_number": 1, "manifest_status": "PRESENT"},
            {"page_number": 2, "manifest_status": "PRESENT"},
        ],
        "pages": [
            {"page_number": 1, "manifest_status": "PRESENT", "diagnostic": None, "route": None},
            {"page_number": 2, "manifest_status": "PRESENT", "diagnostic": None, "route": None},
        ],
    }
    client = UiDocumentApiClient(transport=QueueTransport([_response(valid_diagnostic)]))
    assert client.read_diagnostic(document_id).status_code == 200

    progress = UiDocumentJsonResponse(
        status_code=200,
        payload={
            "action_name": "DIAGNOSE",
            "phase": "RUNNING",
            "completed_units": 0,
            "total_units": 2,
            "failure_error_code": None,
        },
    )
    inspection = render_document_inspection(
        title="Diagnostic",
        response=UiDocumentJsonResponse(status_code=200, payload=valid_diagnostic),
        action_progress=progress,
    )
    assert 'aria-label="Progression de l’action"' in inspection
    assert "RUNNING" in inspection
    assert "Avancement : 0 % (0 / 2)" in inspection
    assert (
        '<progress aria-label="Avancement du diagnostic : 0 %" value="0" max="2">0 %</progress>'
        in inspection
    )
    assert 'http-equiv="refresh"' in inspection

    invalid_progress_client = UiDocumentApiClient(
        transport=QueueTransport([
            _response(
                {
                    "action_name": "DIAGNOSE",
                    "phase": "RUNNING",
                    "completed_units": 3,
                    "total_units": 2,
                    "failure_error_code": None,
                }
            )
        ])
    )
    try:
        invalid_progress_client.read_document_action_progress(document_id, "DIAGNOSE")
    except ValueError as exc:
        assert "progression publique incompatible" in str(exc)
    else:
        raise AssertionError("Une progression incohérente est acceptée")

    # Le contrat de diagnostic final, la conversion et l'origine API restent
    # couverts : l'ajout de la progression ne retire aucun garde-fou existant.
    completed_diagnostic = {
        **valid_diagnostic,
        "diagnostic_status": "ROUTE_PLANNED",
        "diagnosed_page_count": 2,
        "pages": [
            {
                "page_number": page_number,
                "manifest_status": "PRESENT",
                "diagnostic": {
                    "page_state": "NATIVE_OK",
                    "native_text_state": "RELIABLE",
                    "image_state": "NONE",
                    "existing_ocr_state": "NONE",
                    "layout_complexity": "SIMPLE",
                    "corruption_state": "NONE",
                    "mixed_content_detected": False,
                    "has_table": False,
                    "has_formula": False,
                    "diagnostic_version": "diag-v1",
                    "justification": f"Signaux réels page {page_number}.",
                },
                "route": {
                    "route_name": "NATIVE_STANDARD",
                    "decision_mode": "AUTO",
                    "confidence_score": 0.99,
                    "preprocessing_action": "NONE",
                    "routing_policy_version": "routing-v1",
                    "justification": f"Route réelle page {page_number}.",
                },
            }
            for page_number in (1, 2)
        ],
    }
    assert UiDocumentApiClient(
        transport=QueueTransport([_response(completed_diagnostic)])
    ).read_diagnostic(document_id).status_code == 200
    _assert_diagnostic_rejected(
        {**completed_diagnostic, "document_id": "DOC-OTHER"},
        "autre document",
    )
    _assert_diagnostic_rejected(
        {
            **completed_diagnostic,
            "pages": [completed_diagnostic["pages"][0], completed_diagnostic["pages"][0]],
        },
        "pages",
    )
    _assert_diagnostic_rejected(
        {**completed_diagnostic, "manifest": completed_diagnostic["manifest"][:1]},
        "manifeste",
    )
    _assert_diagnostic_rejected(
        {**completed_diagnostic, "diagnosed_page_count": 1},
        "comptage",
    )

    for invalid_conversion in (
        {
            "document_id": document_id,
            "conversion_status": "QA_REJECTED",
            "qa_rejection_error_code": None,
            "canonical_version_id": None,
        },
        {
            "document_id": document_id,
            "conversion_status": "CANONICAL_ACCEPTED",
            "qa_rejection_error_code": None,
            "canonical_version_id": None,
        },
    ):
        conversion_client = UiDocumentApiClient(
            transport=QueueTransport([_response(invalid_conversion)])
        )
        try:
            conversion_client.read_conversion(document_id)
        except ValueError:
            pass
        else:
            raise AssertionError("Nullabilité conversion incohérente acceptée")

    repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    configuration = load_application_configuration(
        repository_root / "config" / "application.example.yaml",
        {},
    )
    assert (
        build_ui_orchestrator_origin(configuration, execution_context="host")
        == "http://127.0.0.1:8080"
    )
    assert (
        build_ui_orchestrator_origin(configuration, execution_context="compose")
        == "http://orchestrator-api:8080"
    )
    try:
        build_ui_orchestrator_origin(configuration, execution_context="invented")
    except ValueError as exc:
        assert "contexte" in str(exc)
    else:
        raise AssertionError("Contexte d'exécution UI inconnu accepté")

    error_inspection = render_document_inspection(
        title="Diagnostic",
        response=UiDocumentJsonResponse(
            status_code=503,
            payload={"error_code": "ORCHESTRATOR_API_UNAVAILABLE"},
        ),
        action_progress=None,
    )
    assert 'role="alert"' in error_inspection
    assert "disponibilit" in error_inspection
    missing_conversion = render_document_inspection(
        title="Conversion",
        response=UiDocumentJsonResponse(
            status_code=409,
            payload={"error_code": "CONVERSION_NOT_REQUESTED"},
        ),
        action_progress=None,
    )
    assert "fonctionnalit" in missing_conversion and "non livr" in missing_conversion
    assert "essayer" not in missing_conversion
