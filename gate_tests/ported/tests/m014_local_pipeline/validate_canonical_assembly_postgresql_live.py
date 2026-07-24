"""Preuve PostgreSQL réelle T-007 de l'assemblage canonique atomique."""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from app.contracts.technical_jobs import (
    JobEnvironmentIdentity,
    JobIdempotenceKey,
    JobPriority,
    JobRequest,
)
from app.platform.job_runtime import JobCatalog
from app.platform.job_runtime.postgres import PostgresJobQueue
from app.platform.job_runtime.relay import JobOutboxRelay
from app.platform.postgres import PostgresConnectionFactory
from app.platform.ui_local_stack import LOCAL_POSTGRES_IMAGE
from app.source_processing.adapters.docling_native_conversion import (
    CanonicalArtifactFileStore,
)
from app.source_processing.adapters.local_page_artifacts import LocalPageArtifactStore
from app.source_processing.adapters.postgres_canonical_assembly import (
    PostgresCanonicalAssemblyRepository,
)
from app.source_processing.adapters.postgres_page_completion import (
    PostgresPageResultRepository,
)
from app.source_processing.application.assemble_canonical_document import (
    AssembleCanonicalDocumentHandler,
)
from app.source_processing.application.fan_out_document_pages import (
    DISTRIBUTED_PAGE_FAN_OUT_VERSION,
    FanOutDocumentPagesHandler,
)
from app.source_processing.domain.distribution_contracts import (
    ASSEMBLE_CANONICAL_DOCUMENT_JOB_NAME,
    PAGE_RESULT_CONTRACT_VERSION,
    DistributionContractError,
    LocalArtifactDescriptor,
    LocalArtifactIdentity,
    LockedAssetVersion,
    PageExecutionIdentity,
    PageResultContract,
    PageResultStatus,
    PageTechnicalMetrics,
)
from app.source_processing.domain.document_processing_run import (
    DiagnosticVersion,
    DocumentProcessingRun,
    DocumentProcessingRunStatus,
    PageDecision,
    PageDecisionState,
    PageDiagnosticSignals,
    PageManifest,
    PageManifestEntry,
    PageManifestEntryState,
    PageNumber,
    PagePreprocessingAction,
    PageRoute,
    PageRouteName,
    ProcessingRunId,
    RouteDecisionMode,
    RoutePlan,
    RoutingPolicyVersion,
)
from app.source_processing.domain.page_conversion import (
    ConversionToolName,
    PageConversionArtifact,
    PageConversionItem,
    PageConversionItemLabel,
    PageItemGeometry,
)
from app.source_processing.domain.source_document import (
    BibliographicMetadata,
    DocumentId,
    OriginalStorageRef,
    SourceDocument,
    SourceFingerprint,
)


POLICY = "routing-m014-assembly-live-v1"


def _docker(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("docker", *arguments),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=False,
    )


def _published_port(container: str) -> int:
    published = _docker("port", container, "5432/tcp")
    assert published.returncode == 0, published.stderr
    return int(published.stdout.strip().splitlines()[0].rsplit(":", 1)[1])


def _wait_postgres(
    *, container: str, connection_factory: PostgresConnectionFactory
) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        state = _docker("inspect", "--format", "{{.State.Running}}", container)
        assert state.returncode == 0 and state.stdout.strip() == "true"
        try:
            with connection_factory.connect() as connection, connection.cursor() as cursor:
                cursor.execute("SELECT 1", ())
                assert cursor.fetchone() == (1,)
        except psycopg.OperationalError as error:
            if error.sqlstate is not None:
                raise
            time.sleep(0.5)
        else:
            return
    raise AssertionError("PostgreSQL T-007 non prêt")


def _source() -> SourceDocument:
    content = b"%PDF-1.7\nM014 canonical assembly live\n%%EOF\n"
    fingerprint = SourceFingerprint.from_content(content)
    document_id = DocumentId.from_fingerprint(fingerprint)
    return SourceDocument.register_original(
        document_id=document_id,
        fingerprint=fingerprint,
        original_storage_ref=OriginalStorageRef.from_value(
            "artifact:source_processing.original_sources/"
            f"{document_id.value}/{fingerprint.value}.pdf"
        ),
        metadata=BibliographicMetadata.from_payload(
            {
                "title": "Assemblage canonique M14",
                "authors": ["Équipe OSTrading"],
                "publication_year": 2026,
                "edition": "1re édition",
            }
        ),
    )


def _signals(*, empty: bool) -> PageDiagnosticSignals:
    return PageDiagnosticSignals(
        native_text_state="ABSENT" if empty else "RELIABLE",
        image_state="NONE",
        existing_ocr_state="NONE",
        layout_complexity="SIMPLE",
        corruption_state="NONE",
        mixed_content_detected=False,
        has_table=False,
        has_formula=False,
    )


def _run(source: SourceDocument) -> DocumentProcessingRun:
    manifest = PageManifest.from_entries(
        source_page_count=3,
        entries=(
            PageManifestEntry(PageNumber.from_value(1), PageManifestEntryState.PRESENT),
            PageManifestEntry(PageNumber.from_value(2), PageManifestEntryState.EMPTY),
            PageManifestEntry(PageNumber.from_value(3), PageManifestEntryState.PRESENT),
        ),
    )
    started = DocumentProcessingRun.start(
        processing_run_id=ProcessingRunId.from_value("RUN-M014-ASSEMBLY-LIVE"),
        source_document=source,
        page_manifest=manifest,
    )
    decisions = tuple(
        PageDecision(
            page_number=PageNumber.from_value(page),
            page_state=PageDecisionState.EMPTY if page == 2 else PageDecisionState.NATIVE_OK,
            signals=_signals(empty=page == 2),
            diagnostic_version=DiagnosticVersion.from_value("diag-m014-assembly-live-v1"),
            justification=f"Diagnostic persistant page {page}.",
        )
        for page in range(1, 4)
    )
    diagnosed = started.record_page_diagnostics(decisions)
    routes = tuple(
        PageRoute(
            page_number=PageNumber.from_value(page),
            route_name=(PageRouteName.SKIP_EMPTY if page == 2 else PageRouteName.NATIVE_STANDARD),
            decision_mode=RouteDecisionMode.AUTO,
            confidence_score=1.0,
            preprocessing_action=PagePreprocessingAction.NONE,
            routing_policy_version=RoutingPolicyVersion.from_value(POLICY),
            justification=f"Route persistante page {page}.",
        )
        for page in range(1, 4)
    )
    plan = RoutePlan(
        routing_policy_version=RoutingPolicyVersion.from_value(POLICY),
        page_routes=routes,
        dominant_route_name=PageRouteName.NATIVE_STANDARD,
        page_exceptions=(routes[1],),
        confidence_score=1.0,
    )
    return DocumentProcessingRun(
        processing_run_id=diagnosed.processing_run_id,
        document_id=diagnosed.document_id,
        page_manifest=diagnosed.page_manifest,
        page_decisions=diagnosed.page_decisions,
        route_plan=plan,
        manual_review_reason=None,
        blocking_policy_version=None,
        status=DocumentProcessingRunStatus.ROUTE_PLANNED,
        aggregate_version=diagnosed.aggregate_version + 1,
        events=diagnosed.events,
    )


def _identity() -> JobEnvironmentIdentity:
    return JobEnvironmentIdentity(
        environment="test",
        deployment_id="ostrading-test-local",
        configuration_hash="c" * 64,
    )


def _parent(source: SourceDocument, run: DocumentProcessingRun) -> JobRequest:
    return JobRequest(
        environment="test",
        deployment_id="ostrading-test-local",
        job_name="CONVERT_DOCUMENT",
        priority=JobPriority.P1,
        idempotence_key=JobIdempotenceKey(
            job_name="CONVERT_DOCUMENT",
            input_hash=source.fingerprint.value,
            configuration_hash="c" * 64,
            code_version="m014-assembly-live-v1",
            model_version="m014-page-assets-live-v1",
        ),
        execution_requirements=None,
        payload={
            "document_id": source.document_id.value,
            "processing_run_id": run.processing_run_id.value,
            "source_sha256": source.fingerprint.value,
            "routing_policy_version": POLICY,
            "route_count": 3,
            "orchestration_version": DISTRIBUTED_PAGE_FAN_OUT_VERSION,
        },
    )


def _source_artifact(source: SourceDocument) -> LocalArtifactDescriptor:
    path = f"documents/{source.document_id.value}/original.pdf"
    return LocalArtifactDescriptor(
        identity=LocalArtifactIdentity(
            environment="test",
            artifact_ref=f"artifact:source_processing.local/test/{path}",
            relative_path=path,
        ),
        sha256=source.fingerprint.value,
        size_bytes=48,
    )


def _page_bytes(page: int) -> bytes:
    text = f"Texte canonique persistant de la page {page}."
    artifact = PageConversionArtifact(
        page_number=PageNumber.from_value(page),
        route_name=PageRouteName.NATIVE_STANDARD,
        tool_name=ConversionToolName.DOCLING_STANDARD,
        tool_version="docling-m014-assembly-live-v1",
        artifact_hash=f"{page:064x}",
        audit_artifact_ref=(
            "artifact:source_processing.page_conversion/"
            f"RUN-M014-ASSEMBLY-LIVE/page-{page:03d}.json"
        ),
        items=(
            PageConversionItem(
                label=PageConversionItemLabel.TEXT,
                text=text,
                geometry=PageItemGeometry(10, 10, 90, 30, 100, 100),
                content_hash=sha256(text.encode()).hexdigest(),
            ),
        ),
    )
    return json.dumps(
        asdict(artifact),
        default=lambda value: value.value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _page_result(request: JobRequest, store: LocalPageArtifactStore) -> PageResultContract:
    payload = request.payload
    content = _page_bytes(payload["page_number"])
    expected = LocalArtifactIdentity.from_mapping(payload["expected_result_artifact"])
    descriptor = store.write_immutable(
        identity=expected,
        content=content,
        authorize_publication=lambda: None,
    )
    page = payload["page_number"]
    return PageResultContract(
        contract_version=PAGE_RESULT_CONTRACT_VERSION,
        environment_identity=_identity(),
        document_id=payload["document_id"],
        processing_run_id=payload["processing_run_id"],
        page_number=page,
        route_name=payload["route_name"],
        routing_policy_version=payload["routing_policy_version"],
        request_idempotence_key=payload["idempotence_key"],
        execution=PageExecutionIdentity(
            job_id=f"JOB-M002-{page:06d}",
            claim_generation=1,
            claim_token=f"00000000-0000-4000-8000-{page:012d}",
            worker_instance_id="worker-documents-a",
        ),
        granite_slot_execution=None,
        status=PageResultStatus.SUCCEEDED,
        result_artifact=descriptor,
        tool_name="DOCLING_STANDARD",
        tool_version="docling-m014-assembly-live-v1",
        error_code=None,
        technical_metrics=PageTechnicalMetrics(
            duration_seconds=0.1,
            peak_ram_bytes=1024,
            gpu=None,
        ),
    )


class _CrashAfterArtifact:
    def __init__(self, repository: PostgresCanonicalAssemblyRepository) -> None:
        self._repository = repository
        self.crashed = False

    def load_snapshot(self, contract):
        return self._repository.load_snapshot(contract)

    def publish_atomic(self, publication):
        self.crashed = True
        raise RuntimeError("M014_TEST_CRASH_BEFORE_SP_COMMIT")

    def mark_failed(self, contract, *, error_code: str):
        return self._repository.mark_failed(contract, error_code=error_code)


@pytest.mark.timeout(240)
def test_assemblage_postgresql_complet_concurrent_crash_et_rejeu() -> None:
    from app.platform.datastore_identity import DatastoreIdentity, PostgresIdentityPreflight
    from app.platform.postgres import PsycopgConnectionFactory
    from app.platform.postgres_migrations import PostgresMigrationRunner
    from app.source_processing.adapters.postgres_document_persistence import (
        PostgresDocumentConversionRepository,
        PostgresDocumentPersistence,
        PostgresProcessingRunRepository,
    )
    from app.source_processing.adapters.postgres_job_outbox import PostgresJobOutbox

    root = Path(__file__).resolve().parents[4]
    container = f"ostrading-m014-assembly-{uuid4().hex[:12]}"
    password = "m014-assembly-postgres-password"
    started = _docker(
        "run", "--detach", "--rm", "--name", container,
        "--publish", "127.0.0.1::5432", "--env", f"POSTGRES_PASSWORD={password}",
        LOCAL_POSTGRES_IMAGE,
    )
    assert started.returncode == 0, started.stderr
    try:
        with tempfile.TemporaryDirectory(prefix="ostrading-m014-assembly-") as temporary:
            temporary_path = Path(temporary)
            password_path = temporary_path / "postgres-password"
            password_path.write_text(password, encoding="utf-8")
            factory = PsycopgConnectionFactory(
                connection_url=(
                    f"postgresql://postgres@127.0.0.1:{_published_port(container)}/postgres"
                ),
                password_path=password_path,
                connect_timeout_seconds=10,
            )
            _wait_postgres(container=container, connection_factory=factory)
            PostgresMigrationRunner(
                connection_factory=factory,
                migrations_path=root / "deploy/postgres/migrations",
                operation_timeout_seconds=30,
                identity_preflight=PostgresIdentityPreflight(
                    expected_identity=DatastoreIdentity(
                        environment="test", deployment_id="ostrading-test-local"
                    )
                ),
                initialize_identity_if_empty=True,
                adopt_legacy_if_unidentified=False,
            ).run()

            source = _source()
            run = _run(source)
            persistence = PostgresDocumentPersistence(connection_factory=factory)
            persistence.save_if_absent(source)
            persistence.save(run)
            with factory.connect() as connection, connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO source_processing.document_conversion_requests (
                        document_id, conversion_status, canonical_version_id,
                        rejection_error_code, submission_id, job_id,
                        execution_phase, completed_units, total_units,
                        failure_error_code, orchestration_version,
                        producer_environment, producer_deployment_id,
                        producer_configuration_hash
                    )
                    VALUES (%s, 'CONVERSION_REQUESTED', NULL, NULL, %s, NULL,
                            'QUEUED', 0, 3, NULL, 'm014-page-fanout-v1',
                            'test', 'ostrading-test-local', %s)
                    """,
                    (
                        source.document_id.value,
                        "OUTBOX-SP-M014-ASSEMBLY-PARENT",
                        "c" * 64,
                    ),
                )
            fanout = FanOutDocumentPagesHandler(
                processing_run_repository=PostgresProcessingRunRepository(persistence),
                page_fan_out_repository=PostgresDocumentConversionRepository(persistence),
                locked_assets=(
                    LockedAssetVersion(
                        name="document-assets", version="m014-live-v1", sha256="a" * 64
                    ),
                ),
            )
            planned = fanout.handle(
                parent_job=_parent(source, run),
                source_artifact=_source_artifact(source),
                trace_id="TRACE-M014-ASSEMBLY-LIVE",
            )
            assert (planned.completed_units, planned.page_job_count) == (1, 2)

            page_store = LocalPageArtifactStore(
                profile_root=(temporary_path / "page-artifacts").resolve()
            )
            page_repository = PostgresPageResultRepository(connection_factory=factory)
            with factory.connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT environment, deployment_id, priority, input_hash,
                           configuration_hash, code_version, model_version, payload
                      FROM source_processing.job_outbox
                     WHERE job_name = 'CONVERT_PAGE'
                     ORDER BY (payload ->> 'page_number')::integer
                    """,
                    (),
                )
                requests = tuple(
                    JobRequest(
                        environment=row[0],
                        deployment_id=row[1],
                        job_name="CONVERT_PAGE",
                        priority=JobPriority(row[2]),
                        idempotence_key=JobIdempotenceKey(
                            job_name="CONVERT_PAGE",
                            input_hash=row[3],
                            configuration_hash=row[4],
                            code_version=row[5],
                            model_version=row[6],
                        ),
                        execution_requirements=None,
                        payload=row[7],
                    )
                    for row in cursor.fetchall()
                )
            assert tuple(request.payload["page_number"] for request in requests) == (1, 3)
            first_result, last_result = tuple(
                _page_result(request, page_store) for request in requests
            )
            first_fingerprint = sha256(first_result.to_json().encode()).hexdigest()
            assert page_repository.persist_page_result(
                completion_id="PAGE-M014-ASSEMBLY-LIVE-001",
                payload_fingerprint=first_fingerprint,
                result=first_result,
            )
            assert not page_repository.persist_page_result(
                completion_id="PAGE-M014-ASSEMBLY-LIVE-001",
                payload_fingerprint=first_fingerprint,
                result=first_result,
            )
            with pytest.raises(
                DistributionContractError,
                match="PAGE_RESULT_REPLAY_DIVERGENCE",
            ):
                page_repository.persist_page_result(
                    completion_id="PAGE-M014-ASSEMBLY-LIVE-DIVERGENT",
                    payload_fingerprint=first_fingerprint,
                    result=first_result,
                )
            with factory.connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT count(*) FROM source_processing.job_outbox
                     WHERE job_name = 'ASSEMBLE_CANONICAL_DOCUMENT'
                    """,
                    (),
                )
                assert cursor.fetchone() == (0,)

            last_fingerprint = sha256(last_result.to_json().encode()).hexdigest()
            assert page_repository.persist_page_result(
                completion_id="PAGE-M014-ASSEMBLY-LIVE-003",
                payload_fingerprint=last_fingerprint,
                result=last_result,
            )
            with factory.connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT count(*), min(status)
                      FROM source_processing.job_outbox
                     WHERE job_name = 'ASSEMBLE_CANONICAL_DOCUMENT'
                    """,
                    (),
                )
                assert cursor.fetchone() == (1, "pending")

            catalog = JobCatalog.from_job_names(
                ("CONVERT_PAGE", ASSEMBLE_CANONICAL_DOCUMENT_JOB_NAME)
            )
            source_outbox = PostgresJobOutbox(
                connection_factory=factory,
                environment_identity=_identity(),
            )
            queue = PostgresJobQueue(
                connection_factory=factory,
                catalog=catalog,
                environment_identity=_identity(),
            )
            assert JobOutboxRelay(outbox=source_outbox, consumer=queue).relay_pending(
                limit=10,
                owner_id="relay-canonical-assembly",
                lease_seconds=30,
            ) == 3

            def claim(owner: str):
                return queue.claim_next(
                    owner_id=owner,
                    lease_seconds=30,
                    job_names=(ASSEMBLE_CANONICAL_DOCUMENT_JOB_NAME,),
                )

            with ThreadPoolExecutor(max_workers=2) as executor:
                claims = tuple(
                    future.result()
                    for future in (
                        executor.submit(claim, "worker-documents-a"),
                        executor.submit(claim, "worker-documents-b"),
                    )
                )
            claimed = next(value for value in claims if value is not None)
            assert sum(value is not None for value in claims) == 1

            canonical_repository = PostgresCanonicalAssemblyRepository(
                connection_factory=factory
            )
            canonical_store = CanonicalArtifactFileStore(
                root=(temporary_path / "canonical-sources").resolve()
            )
            crash_repository = _CrashAfterArtifact(canonical_repository)
            crashing_handler = AssembleCanonicalDocumentHandler(
                repository=crash_repository,
                page_artifact_reader=page_store,
                canonical_artifact_store=canonical_store,
            )
            with pytest.raises(RuntimeError, match="M014_TEST_CRASH_BEFORE_SP_COMMIT"):
                crashing_handler.handle(
                    request=claimed.job.request,
                    trace_id=claimed.trace_id,
                )
            assert crash_repository.crashed
            assert tuple((temporary_path / "canonical-sources").rglob("docling.json"))
            with factory.connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM source_processing.canonical_source_versions",
                    (),
                )
                assert cursor.fetchone() == (0,)
                cursor.execute(
                    "SELECT count(*) FROM source_processing.canonical_publication_outbox",
                    (),
                )
                assert cursor.fetchone() == (0,)

            handler = AssembleCanonicalDocumentHandler(
                repository=canonical_repository,
                page_artifact_reader=page_store,
                canonical_artifact_store=canonical_store,
            )
            with factory.connect() as connection, connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE FUNCTION source_processing.fail_canonical_publication_once()
                    RETURNS trigger LANGUAGE plpgsql AS $$
                    BEGIN
                        RAISE EXCEPTION 'M014_INJECTED_CANONICAL_TRANSACTION_FAILURE';
                    END;
                    $$
                    """,
                    (),
                )
                cursor.execute(
                    """
                    CREATE TRIGGER fail_canonical_publication_once
                    BEFORE INSERT ON source_processing.canonical_publication_outbox
                    FOR EACH ROW EXECUTE FUNCTION
                        source_processing.fail_canonical_publication_once()
                    """,
                    (),
                )
            with pytest.raises(psycopg.errors.RaiseException):
                handler.handle(
                    request=claimed.job.request,
                    trace_id=claimed.trace_id,
                )
            with factory.connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM source_processing.canonical_source_versions",
                    (),
                )
                assert cursor.fetchone() == (0,)
                cursor.execute(
                    "SELECT count(*) FROM source_processing.canonical_publication_outbox",
                    (),
                )
                assert cursor.fetchone() == (0,)
                cursor.execute(
                    """
                    SELECT conversion_status, execution_phase, canonical_version_id
                      FROM source_processing.document_conversion_requests
                     WHERE document_id = %s
                    """,
                    (source.document_id.value,),
                )
                assert cursor.fetchone() == (
                    "CONVERSION_REQUESTED",
                    "RUNNING",
                    None,
                )
            with factory.connect() as connection, connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    "DROP TRIGGER fail_canonical_publication_once ON source_processing.canonical_publication_outbox",
                    (),
                )
                cursor.execute(
                    "DROP FUNCTION source_processing.fail_canonical_publication_once()",
                    (),
                )
            published = handler.handle(
                request=claimed.job.request,
                trace_id=claimed.trace_id,
            )
            replay = handler.handle(
                request=claimed.job.request,
                trace_id=claimed.trace_id,
            )
            assert published.created is True
            assert replay.created is False
            assert replay.canonical_ref == published.canonical_ref
            canonical_artifacts = tuple(
                (temporary_path / "canonical-sources").rglob("docling.json")
            )
            assert len(canonical_artifacts) == 1
            canonical_payload = json.loads(
                canonical_artifacts[0].read_text(encoding="utf-8")
            )
            assert canonical_payload["document_id"] == source.document_id.value
            assert (
                canonical_payload["canonical_version_id"]
                == published.canonical_ref.canonical_version_id
            )
            assert tuple(page["page_pdf"] for page in canonical_payload["pages"]) == (
                1,
                2,
                3,
            )
            assert canonical_payload["pages"][1]["items"] == []
            actual_items = tuple(
                item
                for page in canonical_payload["pages"]
                for item in page["items"]
            )
            assert tuple(item["text"] for item in actual_items) == (
                "Texte canonique persistant de la page 1.",
                "Texte canonique persistant de la page 3.",
            )
            assert all(
                item["content_hash"]
                == sha256(item["text"].encode("utf-8")).hexdigest()
                for item in actual_items
            )
            assert tuple(
                item["provenance"]["page_pdf"] for item in actual_items
            ) == (1, 3)
            with factory.connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT conversion_status, execution_phase,
                           completed_units, total_units, canonical_version_id
                      FROM source_processing.document_conversion_requests
                     WHERE document_id = %s
                    """,
                    (source.document_id.value,),
                )
                state = cursor.fetchone()
                assert state[:4] == ("CANONICAL_ACCEPTED", "SUCCEEDED", 3, 3)
                assert state[4] == published.canonical_ref.canonical_version_id
                cursor.execute(
                    """
                    SELECT count(*), min(event_id), min(status)
                      FROM source_processing.canonical_publication_outbox
                    """,
                    (),
                )
                event_count, event_id, status = cursor.fetchone()
                assert event_count == 1
                assert event_id == published.event.event_id
                assert status == "pending"
                cursor.execute(
                    "SELECT count(*) FROM source_processing.canonical_source_versions",
                    (),
                )
                assert cursor.fetchone() == (1,)
    finally:
        removed = _docker("rm", "--force", container)
        assert removed.returncode == 0, removed.stderr
