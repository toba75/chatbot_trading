"""Acceptation de la frontière UI vers l'API orchestratrice."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

from app.platform.configuration import load_application_configuration
from app.platform.local_runtime import _build_ui_corpus_state
from app.platform.ui_corpus import ui_get_response
from app.platform.ui_document_api import (
    UiDocumentApiClient,
    UiDocumentApiResponse,
)


class RecordingTransport:
    def __init__(self) -> None:
        self.paths: list[str] = []
        payload = {
            "documents": [
                {
                    "document_id": "DOC-M013-UI-API01",
                    "title": "Depuis API",
                    "authors": ["Auteur API"],
                    "publication_year": 2026,
                    "edition": None,
                    "metadata_status": "LEGACY_DECLARED",
                    "document_status": "REGISTERED",
                    "diagnostic_status": "DIAGNOSTIC_NOT_REQUESTED",
                    "conversion_status": "CONVERSION_NOT_REQUESTED",
                    "canonical_version_id": None,
                    "projection_status": "PROJECTION_NOT_REQUESTED",
                    "manual_review_reason": None,
                    "failure_error_code": None,
                    "conversion_action_available": False,
                    "projection_action_available": False,
                }
            ],
            "next_cursor": None,
        }
        self.responses = [
            UiDocumentApiResponse(
                200,
                "application/json",
                json.dumps(payload).encode("utf-8"),
            )
        ]

    def request(self, *, method, path, body, content_type):
        del method, body, content_type
        self.paths.append(path)
        return self.responses.pop(0)


def test_validate_ui_corpus_backend_connection_acceptance() -> None:
    repository_root = next(
        parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file()
    )
    with tempfile.TemporaryDirectory() as temporary_root:
        corpus_root = Path(temporary_root) / "corpus"
        corpus_root.mkdir()
        (corpus_root / "Ne doit pas être lu.pdf").write_bytes(
            b"%PDF-1.7\ninterdit\n%%EOF\n"
        )
        config_text = (
            repository_root / "config/application.example.yaml"
        ).read_text(encoding="utf-8").replace(
            "  corpus_root: data/corpus",
            f'  corpus_root: "{corpus_root.as_posix()}"',
        )
        config_path = Path(temporary_root) / "application.yaml"
        config_path.write_text(config_text, encoding="utf-8")
        configuration = load_application_configuration(
            config_path=config_path,
            environment_snapshot={},
        )
        transport = RecordingTransport()
        state = _build_ui_corpus_state(
            application_configuration=configuration,
            api_client=UiDocumentApiClient(transport=transport),
        )

        assert state.read_model_status == "READ_MODEL_READY"
        assert state.documents[0].title == "Depuis API"
        assert state.documents[0].metadata_status == "LEGACY_DECLARED"
        assert transport.paths == ["/v1/documents?limit=100"]
        status, content_type, body = ui_get_response(
            path="/ui/corpus-pdf",
            state=state,
        )
        assert status == 200
        assert content_type == "text/html; charset=utf-8"
        assert "Depuis API" in body
        assert ">Diagnostiquer</button>" in body
        assert "Ne doit pas être lu" not in body

    runtime_source = (repository_root / "app/platform/local_runtime.py").read_text(
        encoding="utf-8"
    )
    ui_source = (repository_root / "app/platform/ui_corpus.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "build_unconnected_corpus_pdf_state",
        "ORCHESTRATOR_API_CONTRACT_NOT_WIRED",
        "UI_FUNCTION_NOT_OPERATIONAL",
        "_UI_DIAGNOSTIC_REQUESTED_DOCUMENT_IDS",
    ):
        assert forbidden not in runtime_source + ui_source
    for forbidden in (".iterdir()", ".read_bytes()", "hashlib.sha256"):
        assert forbidden not in ui_source
