"""Revue gouvernance, OpenAPI, runtime, performance et observabilité."""

from __future__ import annotations

import inspect
from pathlib import Path
import subprocess
import sys

from fastapi import FastAPI

from app.platform.configuration import load_application_configuration
from app.platform.orchestrator_runtime import build_orchestrator_composition_root
from app.source_processing.adapters.postgres_document_persistence import (
    PostgresDocumentPersistence,
)


def test_validate_review_governance_performance_acceptance(monkeypatch) -> None:
    repository_root = next(
        parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file()
    )
    configuration = load_application_configuration(
        config_path=repository_root / "config" / "application.example.yaml",
        environment_snapshot={},
    )
    monkeypatch.setattr(
        "app.platform.orchestrator_runtime.read_required_secret",
        lambda *, path, error_code: "fixture-secret-explicite-00000001",
    )
    monkeypatch.setattr(
        "app.platform.configured_datastore_identity.read_required_secret",
        lambda *, path, error_code: "fixture-secret-explicite-00000001",
    )
    root = build_orchestrator_composition_root(configuration)
    application = FastAPI()
    application.include_router(root.document_command_router)
    schema = application.openapi()

    registration = schema["paths"]["/v1/documents"]["post"]
    multipart = registration["requestBody"]["content"]["multipart/form-data"]["schema"]
    assert set(multipart["required"]) == {"original_content"}
    assert set(multipart["properties"]) == {"original_content"}
    assert multipart["properties"]["original_content"]["format"] == "binary"
    assert set(registration["responses"]) >= {"201", "400", "409", "422", "500"}
    for status in ("201", "400", "409", "422", "500"):
        response = registration["responses"][status]
        assert "application/json" in response["content"]
        assert "$ref" in response["content"]["application/json"]["schema"]

    original = schema["paths"]["/v1/documents/{document_id}/original"]["get"]
    assert "application/pdf" in original["responses"]["200"]["content"]
    diagnose = schema["paths"]["/v1/documents/{document_id}/diagnose"]["post"]
    assert set(diagnose["responses"]) >= {"202", "400", "404", "409", "422", "500"}

    router_source = (
        repository_root / "app/platform/orchestrator_contract_routers.py"
    ).read_text(encoding="utf-8")
    assert "local_runtime._" not in router_source
    assert "build_public_contract_router" in inspect.getsource(
        build_orchestrator_composition_root
    )
    build_source = inspect.getsource(build_orchestrator_composition_root)
    assert build_source.count("PsycopgConnectionFactory(") == 1
    assert "connection_factory=connection_factory" in build_source

    persistence_source = inspect.getsource(
        PostgresDocumentPersistence.list_document_snapshots
    )
    assert "limit" in persistence_source and "after_document_id" in persistence_source
    assert "ANY(%s)" in persistence_source
    assert persistence_source.count("cursor.execute(") <= 8

    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.platform.local_runtime",
            "serve-http",
            "orchestrator-api",
            "8080",
            "--config",
            str(repository_root / "config" / "application.example.yaml"),
        ],
        cwd=repository_root,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert process.returncode != 0
    assert "ORCHESTRATOR_LEGACY_RUNTIME_FORBIDDEN" in process.stderr

    worker_source = (
        repository_root / "app/source_processing/adapters/worker_runtime.py"
    ).read_text(encoding="utf-8")
    for marker in (
        "bind_trace_id(claimed.trace_id)",
        '"success_count"',
        '"error_count"',
        '"duration_ms"',
        '"processed_volume"',
        '"tracing_enabled"',
    ):
        assert marker in worker_source

    migration = (
        repository_root
        / "deploy/postgres/migrations/005_source_processing_read_performance.sql"
    ).read_text(encoding="utf-8")
    assert "source_documents_editorial_duplicate_idx" in migration
    assert "work_title, work_authors" in migration

    persistence_all = (
        repository_root / "app/source_processing/adapters/postgres_document_persistence.py"
    ).read_text(encoding="utf-8")
    for marker in (
        "jsonb_to_recordset",
        "page_manifest_entries",
        "page_decisions",
        "page_routes",
    ):
        assert marker in persistence_all
