"""Acceptation de la lecture publique de progression de conversion (ADR-031)."""

from __future__ import annotations

import asyncio
import json

from app.contracts.document_public_statuses import PublicActionPhase
from app.contracts.technical_jobs import JobEnvironmentIdentity
from app.platform.orchestrator_asgi import create_orchestrator_app
from app.platform.orchestrator_composition import (
    DependencyReadiness,
    OrchestratorCompositionRoot,
)
from app.platform.configuration import load_application_configuration
from app.source_processing.adapters.query_http import build_document_query_router
from app.source_processing.application.document_queries import DocumentActionProgressView


_ENVIRONMENT_IDENTITY = JobEnvironmentIdentity(
    environment="development",
    deployment_id="ostrading-development-local",
    configuration_hash="a" * 64,
)


def _verifier_echec_gemma_relisible_publiquement() -> None:
    # Given Gemma a été l'unique récupération explicitement autorisée après Granite.
    # When Gemma échoue, puis que l'API relit l'état de conversion persistant.
    # Then l'échec terminal Gemma reste un état public 200, jamais une erreur interne 500.
    from app.source_processing.application.document_commands import (
        DocumentConversionExecutionPhase,
        DocumentConversionState,
        DocumentConversionStatus,
    )
    from app.source_processing.domain.source_document import DocumentId

    conversion = DocumentConversionState(
        document_id=DocumentId.from_value("DOC-4444444444444444"),
        producer_environment_identity=_ENVIRONMENT_IDENTITY,
        conversion_status=DocumentConversionStatus.QA_REJECTED,
        canonical_version_id=None,
        rejection_error_code="GEMMA_VISION_UNAVAILABLE",
        execution_phase=DocumentConversionExecutionPhase.FAILED,
        completed_units=4,
        total_units=289,
        failure_error_code="GEMMA_VISION_UNAVAILABLE",
    )
    progress = DocumentActionProgressView.from_conversion(
        conversion,
        environment_identity=JobEnvironmentIdentity(
            environment="test",
            deployment_id="ostrading-test-current",
            configuration_hash="b" * 64,
        ),
    )

    assert progress.phase is PublicActionPhase.FAILED
    assert progress.completed_units == 4
    assert progress.total_units == 289
    assert progress.failure_error_code == "GEMMA_VISION_UNAVAILABLE"
    assert progress.environment == _ENVIRONMENT_IDENTITY.environment
    assert progress.deployment_id == _ENVIRONMENT_IDENTITY.deployment_id
    assert progress.configuration_hash == _ENVIRONMENT_IDENTITY.configuration_hash


class _Queries:
    def list_documents(self, *, limit: int, cursor: str | None):
        raise AssertionError("La liste n'appartient pas à ce scénario.")

    def read_diagnostic(self, document_id: str):
        raise AssertionError("Le diagnostic n'appartient pas à ce scénario.")

    def read_conversion(self, document_id: str):
        raise AssertionError("La conversion finale n'appartient pas à ce scénario.")

    def read_document_action_progress(
        self,
        document_id: str,
        action_name: str,
    ) -> DocumentActionProgressView:
        assert document_id == "DOC-4444444444444444"
        assert action_name == "CONVERT_DOCUMENT"
        return DocumentActionProgressView(
            action_name="CONVERT_DOCUMENT",
            phase=PublicActionPhase.RUNNING,
            completed_units=0,
            total_units=2,
            failure_error_code=None,
            **_ENVIRONMENT_IDENTITY.to_mapping(),
        )


class _ReadyDependency:
    async def open(self) -> None:
        return None

    async def close(self) -> None:
        return None

    def readiness(self) -> DependencyReadiness:
        return DependencyReadiness(name="conversion-progress", status="ready")


async def _get(application, path: str) -> tuple[int, dict[str, object]]:
    sent: list[dict[str, object]] = []
    delivered = False

    async def receive() -> dict[str, object]:
        nonlocal delivered
        if delivered:
            return {"type": "http.disconnect"}
        delivered = True
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    await application(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
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
    status = next(
        message["status"]
        for message in sent
        if message["type"] == "http.response.start"
    )
    raw_body = b"".join(
        message.get("body", b"")
        for message in sent
        if message["type"] == "http.response.body"
    )
    return int(status), json.loads(raw_body.decode("utf-8"))


def test_la_progression_de_conversion_traverse_la_lecture_publique() -> None:
    # Given une commande CONVERT_DOCUMENT passée par l'outbox et prise par le worker,
    # dont l'état RUNNING est déjà persisté.
    # When l'UI demande GET /v1/documents/{id}/conversion/progress.
    # Then l'API restitue exclusivement phase et unités publiques persistées.
    from pathlib import Path

    repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    configuration = load_application_configuration(
        repository_root / "config" / "application.example.yaml", {}
    )
    application = create_orchestrator_app(
        configuration=configuration,
        composition_root_factory=lambda validated: OrchestratorCompositionRoot(
            configuration=validated,
            dependencies=(_ReadyDependency(),),
            document_command_router=build_document_query_router(document_queries=_Queries()),
        ),
    )

    async def scenario() -> None:
        async with application.router.lifespan_context(application):
            status, payload = await _get(
                application,
                "/v1/documents/DOC-4444444444444444/conversion/progress",
            )
        assert status == 200
        assert payload == {
            "action_name": "CONVERT_DOCUMENT",
            "phase": "RUNNING",
            "completed_units": 0,
            "total_units": 2,
            "failure_error_code": None,
            **_ENVIRONMENT_IDENTITY.to_mapping(),
        }

    _verifier_echec_gemma_relisible_publiquement()
    asyncio.run(scenario())
