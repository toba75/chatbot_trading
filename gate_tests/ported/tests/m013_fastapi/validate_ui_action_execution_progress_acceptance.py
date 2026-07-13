from __future__ import annotations

import asyncio
import json
from pathlib import Path


def test_validate_ui_action_execution_progress_acceptance() -> None:
    repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    import sys

    sys.path.insert(0, str(repository_root))

    from app.contracts.document_public_statuses import PublicActionPhase
    from app.platform.configuration import load_application_configuration
    from app.platform.orchestrator_asgi import create_orchestrator_app
    from app.platform.orchestrator_composition import DependencyReadiness, OrchestratorCompositionRoot
    from app.source_processing.adapters.query_http import build_document_query_router
    from app.source_processing.application.document_queries import DocumentActionProgressView

    class Queries:
        def list_documents(self, *, limit: int, cursor: str | None):
            raise AssertionError("La liste ne doit pas être appelée")

        def read_diagnostic(self, document_id: str):
            raise AssertionError("Le diagnostic ne doit pas être appelé")

        def read_conversion(self, document_id: str):
            raise AssertionError("La conversion ne doit pas être appelée")

        def read_document_action_progress(self, document_id: str):
            assert document_id == "DOC-M013-UI-PROGRESS"
            return DocumentActionProgressView(
                action_name="DIAGNOSE",
                phase=PublicActionPhase.RUNNING,
                completed_units=0,
                total_units=38,
                failure_error_code=None,
            )

    class ReadyDependency:
        async def open(self):
            return None

        async def close(self):
            return None

        def readiness(self):
            return DependencyReadiness(name="action-progress", status="ready")

    async def get(application):
        sent: list[dict[str, object]] = []
        delivered = False

        async def receive():
            nonlocal delivered
            if delivered:
                return {"type": "http.disconnect"}
            delivered = True
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            sent.append(message)

        await application(
            {
                "type": "http",
                "asgi": {"version": "3.0", "spec_version": "2.3"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": "/v1/documents/DOC-M013-UI-PROGRESS/diagnostic/progress",
                "raw_path": b"/v1/documents/DOC-M013-UI-PROGRESS/diagnostic/progress",
                "query_string": b"",
                "root_path": "",
                "headers": [],
                "client": ("acceptance", 50000),
                "server": ("orchestrator-api", 8080),
                "state": {},
            },
            receive,
            send,
        )
        status = next(message["status"] for message in sent if message["type"] == "http.response.start")
        body = b"".join(
            message.get("body", b"")
            for message in sent
            if message["type"] == "http.response.body"
        )
        return status, json.loads(body.decode("utf-8"))

    configuration = load_application_configuration(
        repository_root / "config" / "application.example.yaml", {}
    )
    application = create_orchestrator_app(
        configuration=configuration,
        composition_root_factory=lambda validated: OrchestratorCompositionRoot(
            configuration=validated,
            dependencies=(ReadyDependency(),),
            document_command_router=build_document_query_router(document_queries=Queries()),
        ),
    )

    # Given une action dont le worker a persisté la progression publique.
    # When l'UI lit cette progression via l'API orchestratrice.
    # Then le contrat public expose seulement la phase et les unités persistées.
    async def scenario() -> None:
        async with application.router.lifespan_context(application):
            status, payload = await get(application)
        assert status == 200
        assert payload == {
            "action_name": "DIAGNOSE",
            "phase": "RUNNING",
            "completed_units": 0,
            "total_units": 38,
            "failure_error_code": None,
        }

    asyncio.run(scenario())
