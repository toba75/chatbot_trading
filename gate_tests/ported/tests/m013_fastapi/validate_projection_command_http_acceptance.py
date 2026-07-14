from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory


def test_validate_projection_command_http_acceptance() -> None:
    repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    import sys

    sys.path.insert(0, str(repository_root))

    from app.contracts.source_references import CanonicalSourceRef
    from app.knowledge_access.adapters.projection_http import KnowledgeProjectionHttpAdapter
    from app.knowledge_access.application.request_projection import (
        CanonicalSourceForProjection,
        RequestKnowledgeProjectionHandler,
    )
    from app.knowledge_access.adapters.in_memory_projection_repository import (
        InMemoryKnowledgeProjectionRepository,
    )
    from app.knowledge_access.domain.knowledge_projection import ProjectionProfile
    from app.platform.configuration import load_application_configuration
    from app.platform.event_bus.outbox import InMemoryTransactionalOutbox
    from app.platform.orchestrator_asgi import create_orchestrator_app
    from app.platform.orchestrator_composition import DependencyReadiness, OrchestratorCompositionRoot
    from app.knowledge_access.adapters.http import build_projection_command_router

    document_id = "DOC-M013-PROJECTION-COMMAND"
    profile_payload = {
        "projection_profile_id": "local-hybrid-hashing-v1",
        "chunking_profile": "hierarchical-local-v1",
        "embedding_model": "hashing-vector-v1",
        "sparse_profile": "lexical-frequency-v1",
        "index_schema": "qdrant-local-hybrid-v1",
    }

    canonical_ref = CanonicalSourceRef.from_payload(
        {
            "schema_version": "1.0",
            "canonical_source_id": "CSRC-M013-PROJECTION-COMMAND",
            "document_id": document_id,
            "canonical_version_id": "CVER-M013-PROJECTION-COMMAND-0001",
            "source_sha256": "a" * 64,
            "canonical_artifact_sha256": "b" * 64,
            "page_count": 2,
            "accepted_at": "2026-07-14T12:00:00Z",
            "quality_policy_version": "canonical-quality-m004-v1",
        }
    )

    class CanonicalSources:
        def find_projection_source_by_document_id(self, requested_document_id: str):
            if requested_document_id != document_id:
                return None
            return CanonicalSourceForProjection(
                document_id=document_id,
                canonical_ref=canonical_ref,
                canonical_status="ACCEPTED",
                quarantine_reason=None,
            )

    class ReadyDependency:
        async def open(self) -> None:
            return None

        async def close(self) -> None:
            return None

        def readiness(self) -> DependencyReadiness:
            return DependencyReadiness(name="projection-command", status="ready")

    handler = RequestKnowledgeProjectionHandler(
        canonical_source_reader=CanonicalSources(),
        projection_repository=InMemoryKnowledgeProjectionRepository.empty(),
        outbox=InMemoryTransactionalOutbox.empty(),
    )
    adapter = KnowledgeProjectionHttpAdapter(projection_commands=handler)

    async def post(application, *, token: str | None) -> tuple[int, dict[str, object]]:
        sent: list[dict[str, object]] = []
        delivered = False
        body = json.dumps(profile_payload).encode("utf-8")

        async def receive() -> dict[str, object]:
            nonlocal delivered
            if delivered:
                return {"type": "http.disconnect"}
            delivered = True
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message: dict[str, object]) -> None:
            sent.append(message)

        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
        ]
        if token is not None:
            headers.append((b"authorization", f"Bearer {token}".encode("ascii")))
        path = f"/v1/documents/{document_id}/index"
        await application(
            {
                "type": "http",
                "asgi": {"version": "3.0", "spec_version": "2.3"},
                "http_version": "1.1",
                "method": "POST",
                "scheme": "http",
                "path": path,
                "raw_path": path.encode("ascii"),
                "query_string": b"",
                "root_path": "",
                "headers": headers,
                "client": ("acceptance", 50000),
                "server": ("orchestrator-api", 8080),
                "state": {},
            },
            receive,
            send,
        )
        status = next(message["status"] for message in sent if message["type"] == "http.response.start")
        raw = b"".join(
            message.get("body", b"")
            for message in sent
            if message["type"] == "http.response.body"
        )
        return int(status), json.loads(raw.decode("utf-8"))

    configuration = load_application_configuration(
        repository_root / "config" / "application.example.yaml", {}
    )
    with TemporaryDirectory(prefix="ost-projection-command-") as temporary_directory:
        token = "m013-projection-command-token-00000001"
        token_path = Path(temporary_directory) / "local_api_token"
        token_path.write_text(token, encoding="ascii")
        configuration = replace(
            configuration,
            security=replace(
                configuration.security,
                secrets=replace(
                    configuration.security.secrets,
                    local_api_token_path=str(token_path),
                ),
            ),
        )
        application = create_orchestrator_app(
            configuration=configuration,
            composition_root_factory=lambda validated: OrchestratorCompositionRoot(
                configuration=validated,
                dependencies=(ReadyDependency(),),
                document_command_router=build_projection_command_router(
                    projection_command_adapter=adapter,
                ),
            ),
        )

        # Given une version canonique acceptée et un profil de projection explicite.
        # When l'UI demande POST /v1/documents/{document_id}/index.
        # Then l'API authentifiée accepte la commande KA réelle et publie son état REQUESTED.
        async def scenario() -> None:
            async with application.router.lifespan_context(application):
                assert await post(application, token=None) == (
                    401,
                    {"error_code": "LOCAL_API_TOKEN_REQUIRED"},
                )
                status, payload = await post(application, token=token)
            assert status == 202
            assert payload["document_id"] == document_id
            assert payload["projection_status"] == "REQUESTED"
            assert payload["canonical_version_id"] == canonical_ref.canonical_version_id
            assert isinstance(payload["projection_id"], str)

        asyncio.run(scenario())
