"""Preuve rejouable du parcours produit réel dans l'environnement development."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
from types import MappingProxyType
from typing import Any, Final
from urllib.parse import quote
from uuid import uuid4

import httpx
from pypdf import PdfReader, PdfWriter

from app.platform.configuration import (
    ApplicationConfiguration,
    load_application_configuration,
)
from app.platform.environment_compose import (
    _run_compose,
    _technical_environment_from_repository,
    environment_stack_definition,
    inspect_environment_readiness,
)


_ENVIRONMENT: Final = "development"
_DEPLOYMENT_ID: Final = "ostrading-development-local"
_EDGE_BASE_URL: Final = "https://localhost:18443"
_API_BASE_URL: Final = f"{_EDGE_BASE_URL}/api"
_WORKER_IDS: Final = frozenset(
    {"worker-documents", "worker-projection", "worker-research", "worker-backtest"}
)
_PROJECTION_PROFILE: Final = MappingProxyType(
    {
        "projection_profile_id": "local-hash-projection-v1",
        "chunking_profile": "hierarchical-pagewise-v1",
        "embedding_model": "hashing-dense-256-v1",
        "sparse_profile": "lexical-tf-v1",
        "index_schema": "qdrant-hybrid-v1",
    }
)


class DevelopmentE2EError(RuntimeError):
    """Échec terminal stable de la preuve development."""


@dataclass(frozen=True, slots=True)
class DevelopmentE2EReport:
    environment: str
    deployment_id: str
    configuration_hash: str
    image_revision: str
    source_pdf_path: str
    source_pdf_sha256: str
    pdf_path: str
    pdf_sha256: str
    document_id: str
    canonical_version_id: str
    projection_id: str
    answer_id: str
    citation_url: str
    spark_raw_response_id: str
    support_status: str
    progress_phases: tuple[str, str, str]
    worker_identity_count: int
    environment_job_count: int
    restart_persistence_verified: bool
    foreign_environment_probes: tuple[str, str]
    volume_sentinels_preserved: bool
    completed_at: str
    report_path: Path

    def __post_init__(self) -> None:
        if self.environment != _ENVIRONMENT or self.deployment_id != _DEPLOYMENT_ID:
            raise ValueError("DEVELOPMENT_E2E_IDENTITY_INVALID")
        _require_sha256(self.configuration_hash, "configuration_hash")
        _require_git_revision(self.image_revision)
        _require_sha256(self.source_pdf_sha256, "source_pdf_sha256")
        _require_sha256(self.pdf_sha256, "pdf_sha256")
        if self.source_pdf_sha256 == self.pdf_sha256:
            raise ValueError("DEVELOPMENT_E2E_REEMITTED_PDF_REQUIRED")
        _require_identifier(self.document_id, "DOC", "document_id")
        _require_identifier(self.canonical_version_id, "CVER", "canonical_version_id")
        _require_identifier(self.projection_id, "PROJ", "projection_id")
        _require_identifier(self.answer_id, "ANS", "answer_id")
        if not self.citation_url.startswith(f"{_EDGE_BASE_URL}/api/v1/documents/"):
            raise ValueError("DEVELOPMENT_E2E_CITATION_URL_INVALID")
        _require_text(self.spark_raw_response_id, "spark_raw_response_id")
        if self.support_status not in {"SUPPORTED", "PARTIALLY_SUPPORTED"}:
            raise ValueError("DEVELOPMENT_E2E_SUPPORT_STATUS_INVALID")
        if self.progress_phases != ("SUCCEEDED", "SUCCEEDED", "SUCCEEDED"):
            raise ValueError("DEVELOPMENT_E2E_PROGRESS_INVALID")
        if self.worker_identity_count < 6:
            raise ValueError("DEVELOPMENT_E2E_WORKER_IDENTITY_INCOMPLETE")
        if self.environment_job_count < 3:
            raise ValueError("DEVELOPMENT_E2E_JOB_IDENTITY_INCOMPLETE")
        if self.restart_persistence_verified is not True:
            raise ValueError("DEVELOPMENT_E2E_RESTART_NOT_PROVEN")
        if self.foreign_environment_probes != ("test:ABSENT", "production:ABSENT"):
            raise ValueError("DEVELOPMENT_E2E_FOREIGN_PROBES_INVALID")
        if self.volume_sentinels_preserved is not True:
            raise ValueError("DEVELOPMENT_E2E_VOLUME_SENTINELS_NOT_PRESERVED")
        _require_utc(self.completed_at, "completed_at")
        if not isinstance(self.report_path, Path):
            raise ValueError("DEVELOPMENT_E2E_REPORT_PATH_INVALID")


@dataclass(frozen=True, slots=True)
class _ProductProof:
    document_id: str
    canonical_version_id: str
    projection_id: str
    answer_id: str
    citation_url: str
    support_status: str
    spark_raw_response_id: str
    progress_phases: tuple[str, str, str]
    worker_identity_count: int
    environment_job_count: int


def run_development_environment_e2e(
    *,
    repository_root: Path,
    pdf_path: Path,
) -> DevelopmentE2EReport:
    """Traverse la chaîne development réelle puis en publie un rapport sans secret."""

    root = _require_repository_root(repository_root)
    initial_volume_sentinels = _environment_volume_sentinels(repository_root=root)
    source_pdf = _require_real_versioned_pdf(root, pdf_path)
    configuration_path = root / "config" / "environments" / "development.yaml"
    configuration = load_application_configuration(
        config_path=configuration_path,
        environment_snapshot={},
    )
    _require_development_configuration(configuration)
    token_path = root / configuration.security.secrets.local_api_token_path
    token = _read_secret(token_path)
    proof_id = uuid4().hex.upper()
    report_root = (root / configuration.paths.reports_root).resolve()
    log_root = (root / configuration.paths.logs_root).resolve()
    _require_profile_path(report_root)
    _require_profile_path(log_root)
    report_root.mkdir(parents=True, exist_ok=True)
    log_root.mkdir(parents=True, exist_ok=True)
    selected_pdf = _prepare_reemitted_real_pdf(
        source_pdf=source_pdf,
        temporary_report_root=report_root / "temp",
        proof_id=proof_id,
    )
    source_pdf_sha256 = _sha256_file(source_pdf)
    pdf_sha256 = _sha256_file(selected_pdf)
    log_path = log_root / f"development-e2e-{proof_id}.log"

    with _running_development_command(
        repository_root=root,
        token=token,
        log_path=log_path,
    ):
        with _public_client(token=token, timeout_seconds=900) as client:
            _verify_public_ui(client)
            product = _exercise_product(
                client=client,
                configuration=configuration,
                pdf_path=selected_pdf,
                pdf_sha256=pdf_sha256,
                proof_id=proof_id,
                repository_root=root,
            )

    with _running_development_command(
        repository_root=root,
        token=token,
        log_path=log_path,
    ):
        with _public_client(token=token, timeout_seconds=900) as client:
            _verify_public_ui(client)
            _verify_persistence_after_restart(
                client=client,
                product=product,
                pdf_sha256=pdf_sha256,
                proof_id=proof_id,
            )

    foreign_probes = tuple(
        _probe_foreign_environment(
            repository_root=root,
            environment=environment,
            forbidden_document_id=product.document_id,
        )
        for environment in ("test", "production")
    )
    final_volume_sentinels = _environment_volume_sentinels(repository_root=root)
    _verify_volume_sentinels_preserved(
        initial=initial_volume_sentinels,
        final=final_volume_sentinels,
    )
    completed_at = _utc_now()
    revision = _git_revision(root)
    report_path = report_root / f"development-e2e-{completed_at.replace(':', '').replace('-', '')}-{proof_id}.json"
    report = DevelopmentE2EReport(
        environment=_ENVIRONMENT,
        deployment_id=_DEPLOYMENT_ID,
        configuration_hash=configuration.configuration_hash,
        image_revision=revision,
        source_pdf_path=source_pdf.relative_to(root).as_posix(),
        source_pdf_sha256=source_pdf_sha256,
        pdf_path=selected_pdf.relative_to(root).as_posix(),
        pdf_sha256=pdf_sha256,
        document_id=product.document_id,
        canonical_version_id=product.canonical_version_id,
        projection_id=product.projection_id,
        answer_id=product.answer_id,
        citation_url=product.citation_url,
        spark_raw_response_id=product.spark_raw_response_id,
        support_status=product.support_status,
        progress_phases=product.progress_phases,
        worker_identity_count=product.worker_identity_count,
        environment_job_count=product.environment_job_count,
        restart_persistence_verified=True,
        foreign_environment_probes=(foreign_probes[0], foreign_probes[1]),
        volume_sentinels_preserved=True,
        completed_at=completed_at,
        report_path=report_path,
    )
    _write_secret_free_report(report, configuration=configuration, repository_root=root)
    return report


@contextmanager
def _running_development_command(
    *,
    repository_root: Path,
    token: str,
    log_path: Path,
) -> Iterator[None]:
    uv_executable = shutil.which("uv")
    if uv_executable is None:
        raise DevelopmentE2EError("DEVELOPMENT_E2E_UV_UNAVAILABLE")
    with log_path.open("ab") as log_stream:
        current_run_offset = log_stream.tell()
        process = subprocess.Popen(
            (uv_executable, "run", "development"),
            cwd=repository_root,
            stdout=log_stream,
            stderr=subprocess.STDOUT,
        )
        try:
            _wait_public_readiness(
                process=process,
                token=token,
                log_path=log_path,
                start_offset=current_run_offset,
            )
            yield
        finally:
            _stop_development_command(repository_root=repository_root, process=process)


def _environment_lifecycle_state_since(*, log_path: Path, start_offset: int) -> str | None:
    if not isinstance(log_path, Path):
        raise DevelopmentE2EError("DEVELOPMENT_E2E_LOG_PATH_INVALID")
    if not isinstance(start_offset, int) or isinstance(start_offset, bool) or start_offset < 0:
        raise DevelopmentE2EError("DEVELOPMENT_E2E_LOG_OFFSET_INVALID")
    with log_path.open("rb") as stream:
        stream.seek(start_offset)
        current_run_log = stream.read().decode("utf-8")
    lifecycle_state: str | None = None
    for line in current_run_log.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, Mapping):
            continue
        if event.get("event_type") != "environment_lifecycle":
            continue
        if event.get("environment") != _ENVIRONMENT:
            continue
        state = event.get("state")
        if state not in {"starting", "ready", "failed", "stopped"}:
            raise DevelopmentE2EError("DEVELOPMENT_E2E_LIFECYCLE_STATE_INVALID")
        lifecycle_state = state
    return lifecycle_state


def _wait_public_readiness(
    *,
    process: subprocess.Popen[bytes],
    token: str,
    log_path: Path,
    start_offset: int,
) -> None:
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise DevelopmentE2EError(
                f"DEVELOPMENT_E2E_COMMAND_EXITED_BEFORE_READY: code={process.returncode}"
            )
        lifecycle_state = _environment_lifecycle_state_since(
            log_path=log_path,
            start_offset=start_offset,
        )
        if lifecycle_state == "ready":
            break
        if lifecycle_state in {"failed", "stopped"}:
            raise DevelopmentE2EError(
                f"DEVELOPMENT_E2E_LIFECYCLE_TERMINAL_BEFORE_READY: {lifecycle_state}"
            )
        time.sleep(1)
    else:
        raise DevelopmentE2EError("DEVELOPMENT_E2E_LIFECYCLE_READY_TIMEOUT")

    with _public_client(token=token, timeout_seconds=8) as client:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise DevelopmentE2EError(
                    f"DEVELOPMENT_E2E_COMMAND_EXITED_BEFORE_READY: code={process.returncode}"
                )
            try:
                response = client.get("/ready")
            except httpx.TransportError:
                time.sleep(1)
                continue
            if response.status_code == 200:
                payload = _json_mapping(response, "readiness")
                if payload.get("status") != "ready":
                    raise DevelopmentE2EError("DEVELOPMENT_E2E_READINESS_INVALID")
                return
            if response.status_code != 503:
                raise DevelopmentE2EError(
                    f"DEVELOPMENT_E2E_READINESS_HTTP_INVALID: {response.status_code}"
                )
            time.sleep(1)
    raise DevelopmentE2EError("DEVELOPMENT_E2E_READINESS_TIMEOUT")


def _stop_development_command(
    *,
    repository_root: Path,
    process: subprocess.Popen[bytes],
) -> None:
    if process.poll() is not None:
        if process.returncode != 0:
            raise DevelopmentE2EError(
                f"DEVELOPMENT_E2E_COMMAND_EXITED: code={process.returncode}"
            )
        return
    definition = environment_stack_definition(
        _ENVIRONMENT,
        repository_root=repository_root,
    )
    technical_environment = _technical_environment_from_repository(repository_root)
    _run_compose(
        definition,
        ("stop", "--timeout", "30"),
        technical_environment=technical_environment,
        capture_output=True,
    )
    try:
        return_code = process.wait(timeout=180)
    except subprocess.TimeoutExpired as exc:
        raise DevelopmentE2EError("DEVELOPMENT_E2E_COMMAND_STOP_TIMEOUT") from exc
    if return_code != 0:
        raise DevelopmentE2EError(
            f"DEVELOPMENT_E2E_COMMAND_STOP_FAILED: code={return_code}"
        )


def _exercise_product(
    *,
    client: httpx.Client,
    configuration: ApplicationConfiguration,
    pdf_path: Path,
    pdf_sha256: str,
    proof_id: str,
    repository_root: Path,
) -> _ProductProof:
    with pdf_path.open("rb") as pdf_stream:
        response = client.post(
            "/v1/documents",
            files={"original_content": (pdf_path.name, pdf_stream, "application/pdf")},
        )
    if response.status_code not in {200, 201}:
        _raise_http("DEVELOPMENT_E2E_UPLOAD_FAILED", response)
    registration = _json_mapping(response, "registration")
    document_id = _require_identifier(registration.get("document_id"), "DOC", "document_id")

    state = _find_document(client, document_id)
    if state.get("diagnostic_status") == "DIAGNOSTIC_NOT_REQUESTED":
        _request_empty_command(client, f"/v1/documents/{document_id}/diagnose", expected_status=202)
    diagnostic_progress = _wait_action_progress(
        client,
        path=f"/v1/documents/{document_id}/diagnostic/progress",
        expected_action="DIAGNOSE",
        timeout_seconds=600,
    )
    diagnostic = _get_json(client, f"/v1/documents/{document_id}/diagnostic")
    if diagnostic.get("diagnostic_status") != "ROUTE_PLANNED":
        raise DevelopmentE2EError(
            f"DEVELOPMENT_E2E_DIAGNOSTIC_NOT_ROUTED: {diagnostic.get('diagnostic_status')!r}"
        )

    state = _find_document(client, document_id)
    if state.get("conversion_status") == "CONVERSION_NOT_REQUESTED":
        _request_empty_command(client, f"/v1/documents/{document_id}/convert", expected_status=202)
    conversion_progress = _wait_action_progress(
        client,
        path=f"/v1/documents/{document_id}/conversion/progress",
        expected_action="CONVERT_DOCUMENT",
        timeout_seconds=7200,
    )
    conversion = _get_json(client, f"/v1/documents/{document_id}/conversion")
    if conversion.get("conversion_status") != "CANONICAL_ACCEPTED":
        raise DevelopmentE2EError(
            f"DEVELOPMENT_E2E_CONVERSION_NOT_ACCEPTED: {conversion!r}"
        )
    canonical_version_id = _require_identifier(
        conversion.get("canonical_version_id"),
        "CVER",
        "canonical_version_id",
    )

    state = _find_document(client, document_id)
    if state.get("projection_status") == "PROJECTION_NOT_REQUESTED":
        response = client.post(
            f"/v1/documents/{document_id}/index",
            json=dict(_PROJECTION_PROFILE),
        )
        if response.status_code != 202:
            _raise_http("DEVELOPMENT_E2E_PROJECTION_REQUEST_FAILED", response)
    projection_progress = _wait_action_progress(
        client,
        path=f"/v1/documents/{document_id}/projection/progress",
        expected_action="PROJECT_DOCUMENT",
        timeout_seconds=1800,
    )
    projection = _get_json(client, f"/v1/documents/{document_id}/projection")
    if projection.get("projection_status") != "SEARCHABLE":
        raise DevelopmentE2EError(
            f"DEVELOPMENT_E2E_PROJECTION_NOT_SEARCHABLE: {projection!r}"
        )
    projection_id = _require_identifier(projection.get("projection_id"), "PROJ", "projection_id")
    if projection.get("canonical_version_id") != canonical_version_id:
        raise DevelopmentE2EError("DEVELOPMENT_E2E_PROJECTION_CANONICAL_MISMATCH")
    if not isinstance(projection.get("chunk_count"), int) or projection["chunk_count"] < 1:
        raise DevelopmentE2EError("DEVELOPMENT_E2E_SEARCH_INDEX_EMPTY")

    answer = _ask_documentary_question(
        client=client,
        document_id=document_id,
        canonical_version_id=canonical_version_id,
        proof_id=proof_id,
    )
    citation_url = _citation_url(answer=answer, document_id=document_id)
    _verify_original_pdf(
        client=client,
        path=f"/v1/documents/{document_id}/original",
        expected_sha256=pdf_sha256,
    )
    spark_raw_response_id = _prove_real_spark(
        client=client,
        configuration=configuration,
        proof_id=proof_id,
    )
    worker_identity_count = _verify_worker_identities(
        repository_root=repository_root,
        configuration=configuration,
    )
    environment_job_count = _verify_job_identities(
        repository_root=repository_root,
        document_id=document_id,
    )
    return _ProductProof(
        document_id=document_id,
        canonical_version_id=canonical_version_id,
        projection_id=projection_id,
        answer_id=_require_identifier(answer.get("answer_id"), "ANS", "answer_id"),
        citation_url=citation_url,
        support_status=_require_text(answer.get("support_status"), "support_status"),
        spark_raw_response_id=spark_raw_response_id,
        progress_phases=(
            _require_text(diagnostic_progress.get("phase"), "diagnostic_phase"),
            _require_text(conversion_progress.get("phase"), "conversion_phase"),
            _require_text(projection_progress.get("phase"), "projection_phase"),
        ),
        worker_identity_count=worker_identity_count,
        environment_job_count=environment_job_count,
    )


def _verify_public_ui(client: httpx.Client) -> None:
    response = client.get(f"{_EDGE_BASE_URL}/")
    if response.status_code != 200:
        _raise_http("DEVELOPMENT_E2E_UI_UNAVAILABLE", response)
    if not response.headers.get("content-type", "").startswith("text/html"):
        raise DevelopmentE2EError("DEVELOPMENT_E2E_UI_CONTENT_TYPE_INVALID")
    required_fragments = (
        "<title>Corpus PDF</title>",
        'href="/ui/chat"',
        "POST /v1/documents",
    )
    if any(fragment not in response.text for fragment in required_fragments):
        raise DevelopmentE2EError("DEVELOPMENT_E2E_UI_CONTRACT_INCOMPLETE")
    chat_response = client.get(f"{_EDGE_BASE_URL}/ui/chat")
    if chat_response.status_code != 200:
        _raise_http("DEVELOPMENT_E2E_CHAT_UI_UNAVAILABLE", chat_response)
    if "<title>Nouvelle conversation documentaire</title>" not in chat_response.text:
        raise DevelopmentE2EError("DEVELOPMENT_E2E_CHAT_UI_CONTRACT_INCOMPLETE")


def _ask_documentary_question(
    *,
    client: httpx.Client,
    document_id: str,
    canonical_version_id: str,
    proof_id: str,
) -> Mapping[str, Any]:
    occurred_at = _utc_now()
    response = client.post(
        "/v1/conversations",
        json={
            "title": f"Preuve development {proof_id}",
            "default_mandate": {"objective": "Répondre uniquement depuis le PDF sélectionné."},
            "presentation_preferences": {"language": "fr"},
            "occurred_at": occurred_at,
        },
    )
    if response.status_code != 201:
        _raise_http("DEVELOPMENT_E2E_CONVERSATION_CREATE_FAILED", response)
    conversation = _json_mapping(response, "conversation")
    conversation_id = _require_identifier(
        conversation.get("conversation_id"), "CONV", "conversation_id"
    )
    response = client.post(
        f"/v1/conversations/{conversation_id}/messages",
        json={
            "message": (
                "Selon le document sélectionné, quelles règles de gestion du risque "
                "et de suivi de tendance sont décrites ?"
            ),
            "idempotency_key": f"IDEMP-DEVELOPMENT-E2E-{proof_id}",
            "occurred_at": _utc_now(),
            "requested_mode": "CHAT_DOCUMENTAIRE",
            "selected_documents": [document_id],
        },
    )
    if response.status_code != 200:
        _raise_http("DEVELOPMENT_E2E_DOCUMENTARY_ANSWER_FAILED", response)
    answer = _json_mapping(response, "documentary_answer")
    if answer.get("support_status") not in {"SUPPORTED", "PARTIALLY_SUPPORTED"}:
        raise DevelopmentE2EError("DEVELOPMENT_E2E_DOCUMENTARY_SUPPORT_INVALID")
    citations = answer.get("citations")
    if not isinstance(citations, list) or len(citations) == 0:
        raise DevelopmentE2EError("DEVELOPMENT_E2E_CITATION_MISSING")
    for citation in citations:
        parsed = _require_mapping(citation, "citation")
        locator = _require_mapping(parsed.get("source_locator"), "source_locator")
        if locator.get("document_id") != document_id:
            raise DevelopmentE2EError("DEVELOPMENT_E2E_CITATION_DOCUMENT_MISMATCH")
        if locator.get("canonical_version_id") != canonical_version_id:
            raise DevelopmentE2EError("DEVELOPMENT_E2E_CITATION_CANONICAL_MISMATCH")
        page_pdf = locator.get("page_pdf")
        if isinstance(page_pdf, bool) or not isinstance(page_pdf, int) or page_pdf < 1:
            raise DevelopmentE2EError("DEVELOPMENT_E2E_CITATION_PAGE_INVALID")
        _require_sha256(locator.get("content_hash"), "citation_content_hash")
        quoted_span = _require_text(parsed.get("quoted_span"), "quoted_span")
        if parsed.get("quoted_span_hash") != hashlib.sha256(quoted_span.encode("utf-8")).hexdigest():
            raise DevelopmentE2EError("DEVELOPMENT_E2E_CITATION_HASH_MISMATCH")
    return answer


def _prove_real_spark(
    *,
    client: httpx.Client,
    configuration: ApplicationConfiguration,
    proof_id: str,
) -> str:
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": configuration.models.llm.served_model_name,
            "conversation_id": f"CONV-DEVELOPMENT-E2E-SPARK-{proof_id}",
            "trace_id": f"TRACE-DEVELOPMENT-E2E-SPARK-{proof_id}",
            "request_id": f"REQ-DEVELOPMENT-E2E-SPARK-{proof_id}",
            "idempotency_key": f"IDEMP-DEVELOPMENT-E2E-SPARK-{proof_id}",
            "messages": [
                {
                    "role": "user",
                    "content": "Réponds en français en une phrase : chemin Spark development vérifié.",
                }
            ],
            "sampling_parameters": {"max_tokens": 96, "temperature": 0},
        },
    )
    if response.status_code != 200:
        _raise_http("DEVELOPMENT_E2E_SPARK_FAILED", response)
    payload = _json_mapping(response, "spark_response")
    product = _require_mapping(payload.get("ost_product"), "ost_product")
    if product.get("execution_mode") != "live_spark":
        raise DevelopmentE2EError("DEVELOPMENT_E2E_SPARK_MODE_INVALID")
    if tuple(product.get("path_segments", ())) != (
        "docker-local",
        "orchestrator-api",
        "llm-gateway",
        "vllm-spark",
    ):
        raise DevelopmentE2EError("DEVELOPMENT_E2E_SPARK_PATH_INVALID")
    provenance = _require_mapping(product.get("provenance"), "spark_provenance")
    if provenance.get("configuration_hash") != configuration.configuration_hash:
        raise DevelopmentE2EError("DEVELOPMENT_E2E_SPARK_CONFIGURATION_MISMATCH")
    if provenance.get("model_id") != configuration.models.llm.served_model_name:
        raise DevelopmentE2EError("DEVELOPMENT_E2E_SPARK_MODEL_MISMATCH")
    return _require_text(product.get("raw_response_id"), "spark_raw_response_id")


def _citation_url(*, answer: Mapping[str, Any], document_id: str) -> str:
    citations = answer.get("citations")
    if not isinstance(citations, list) or len(citations) == 0:
        raise DevelopmentE2EError("DEVELOPMENT_E2E_CITATION_MISSING")
    citation = _require_mapping(citations[0], "citation")
    locator = _require_mapping(citation.get("source_locator"), "source_locator")
    page_pdf = locator.get("page_pdf")
    if isinstance(page_pdf, bool) or not isinstance(page_pdf, int) or page_pdf < 1:
        raise DevelopmentE2EError("DEVELOPMENT_E2E_CITATION_PAGE_INVALID")
    return (
        f"{_EDGE_BASE_URL}/api/v1/documents/{quote(document_id)}/original"
        f"#page={page_pdf}"
    )


def _verify_persistence_after_restart(
    *,
    client: httpx.Client,
    product: _ProductProof,
    pdf_sha256: str,
    proof_id: str,
) -> None:
    document = _find_document(client, product.document_id)
    if document.get("canonical_version_id") != product.canonical_version_id:
        raise DevelopmentE2EError("DEVELOPMENT_E2E_RESTART_DOCUMENT_MISMATCH")
    conversion = _get_json(client, f"/v1/documents/{product.document_id}/conversion")
    if conversion.get("canonical_version_id") != product.canonical_version_id:
        raise DevelopmentE2EError("DEVELOPMENT_E2E_RESTART_CONVERSION_MISMATCH")
    projection = _get_json(client, f"/v1/documents/{product.document_id}/projection")
    if (
        projection.get("projection_id") != product.projection_id
        or projection.get("projection_status") != "SEARCHABLE"
    ):
        raise DevelopmentE2EError("DEVELOPMENT_E2E_RESTART_PROJECTION_MISMATCH")
    _verify_original_pdf(
        client=client,
        path=f"/v1/documents/{product.document_id}/original",
        expected_sha256=pdf_sha256,
    )
    _ask_documentary_question(
        client=client,
        document_id=product.document_id,
        canonical_version_id=product.canonical_version_id,
        proof_id=f"{proof_id}-RESTART",
    )


def _probe_foreign_environment(
    *,
    repository_root: Path,
    environment: str,
    forbidden_document_id: str,
) -> str:
    definition = environment_stack_definition(environment, repository_root=repository_root)
    technical_environment = _technical_environment_from_repository(repository_root)
    configuration = load_application_configuration(
        config_path=definition.configuration_path,
        environment_snapshot={},
    )
    token = _read_secret(
        repository_root / configuration.security.secrets.local_api_token_path
    )
    _run_compose(
        definition,
        ("up", "--detach", "--no-build", "--wait", "--wait-timeout", "600"),
        technical_environment=technical_environment,
        capture_output=True,
    )
    try:
        inspect_environment_readiness(
            definition,
            technical_environment=technical_environment,
        )
        base_url = f"https://localhost:{definition.edge_port}/api"
        with _public_client(token=token, timeout_seconds=30, base_url=base_url) as client:
            before = _all_public_document_ids(client)
            if forbidden_document_id in before:
                raise DevelopmentE2EError(
                    f"DEVELOPMENT_E2E_FOREIGN_DOCUMENT_VISIBLE: {environment}"
                )
            after = _all_public_document_ids(client)
            if after != before:
                raise DevelopmentE2EError(
                    f"DEVELOPMENT_E2E_FOREIGN_PROBE_MUTATED_DATA: {environment}"
                )
    finally:
        _run_compose(
            definition,
            ("down", "--remove-orphans"),
            technical_environment=technical_environment,
            capture_output=True,
        )
    return f"{environment}:ABSENT"


def _verify_worker_identities(
    *,
    repository_root: Path,
    configuration: ApplicationConfiguration,
) -> int:
    definition = environment_stack_definition(_ENVIRONMENT, repository_root=repository_root)
    technical_environment = _technical_environment_from_repository(repository_root)
    ps_result = _run_compose(
        definition,
        ("ps", "--all", "--format", "json"),
        technical_environment=technical_environment,
        capture_output=True,
    )
    containers = tuple(
        _require_mapping(json.loads(line), "compose_ps")
        for line in ps_result.stdout.splitlines()
        if line.strip()
    )
    worker_containers = tuple(
        row
        for row in containers
        if row.get("Service") in _WORKER_IDS
    )
    if len(worker_containers) < 6:
        raise DevelopmentE2EError("DEVELOPMENT_E2E_WORKERS_MISSING")
    docker_executable = shutil.which("docker")
    if docker_executable is None:
        raise DevelopmentE2EError("DEVELOPMENT_E2E_DOCKER_UNAVAILABLE")
    for row in worker_containers:
        worker_id = _require_text(row.get("Service"), "worker_id")
        container_name = _require_text(row.get("Name"), "worker_container")
        if worker_id == "worker-documents":
            memory_result = subprocess.run(
                (
                    docker_executable,
                    "inspect",
                    "--format",
                    "{{.HostConfig.Memory}}",
                    container_name,
                ),
                cwd=repository_root,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if (
                memory_result.returncode != 0
                or memory_result.stdout.strip() != str(8 * 1024**3)
            ):
                raise DevelopmentE2EError(
                    "DEVELOPMENT_E2E_WORKER_DOCUMENTS_MEMORY_LIMIT_INVALID"
                )
        result = subprocess.run(
            (
                docker_executable,
                "exec",
                container_name,
                "python",
                "-m",
                "app.platform.environment_compose",
                "check-worker",
                "--worker-id",
                worker_id,
                "--config",
                "/workspace/config/application.yaml",
            ),
            cwd=repository_root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise DevelopmentE2EError(
                f"DEVELOPMENT_E2E_WORKER_HEALTH_FAILED: {worker_id}: code={result.returncode}"
            )
        lines = tuple(line for line in result.stdout.splitlines() if line.strip())
        if len(lines) != 1:
            raise DevelopmentE2EError("DEVELOPMENT_E2E_WORKER_HEALTH_INVALID")
        health = _require_mapping(json.loads(lines[0]), "worker_health")
        expected = {
            "environment": _ENVIRONMENT,
            "deployment_id": _DEPLOYMENT_ID,
            "configuration_hash": configuration.configuration_hash,
            "service": worker_id,
        }
        if any(health.get(key) != value for key, value in expected.items()):
            raise DevelopmentE2EError(
                f"DEVELOPMENT_E2E_WORKER_IDENTITY_MISMATCH: {worker_id}"
            )
    return len(worker_containers)


def _verify_job_identities(*, repository_root: Path, document_id: str) -> int:
    docker_executable = shutil.which("docker")
    if docker_executable is None:
        raise DevelopmentE2EError("DEVELOPMENT_E2E_DOCKER_UNAVAILABLE")
    sql = (
        "SELECT count(*), count(*) FILTER (WHERE environment='development' "
        "AND deployment_id='ostrading-development-local') "
        "FROM platform.technical_jobs WHERE payload->>'document_id'="
        f"'{document_id}';"
    )
    result = subprocess.run(
        (
            docker_executable,
            "exec",
            "ostrading-development-postgres-1",
            "psql",
            "-U",
            "ostrading_development",
            "-d",
            "ostrading_development",
            "-Atc",
            sql,
        ),
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise DevelopmentE2EError(
            f"DEVELOPMENT_E2E_JOB_IDENTITY_QUERY_FAILED: code={result.returncode}"
        )
    match = re.fullmatch(r"(?P<total>[0-9]+)\|(?P<matching>[0-9]+)\s*", result.stdout)
    if match is None:
        raise DevelopmentE2EError("DEVELOPMENT_E2E_JOB_IDENTITY_RESULT_INVALID")
    total = int(match.group("total"))
    matching = int(match.group("matching"))
    if total < 3 or matching != total:
        raise DevelopmentE2EError(
            f"DEVELOPMENT_E2E_JOB_IDENTITY_MISMATCH: total={total}: matching={matching}"
        )
    return total


def _environment_volume_sentinels(*, repository_root: Path) -> tuple[str, ...]:
    docker_executable = shutil.which("docker")
    if docker_executable is None:
        raise DevelopmentE2EError("DEVELOPMENT_E2E_DOCKER_UNAVAILABLE")
    listed = subprocess.run(
        (docker_executable, "volume", "ls", "--format", "{{.Name}}"),
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if listed.returncode != 0:
        raise DevelopmentE2EError("DEVELOPMENT_E2E_VOLUME_LIST_FAILED")
    prefixes = tuple(f"ostrading-{environment}-" for environment in (
        "development",
        "test",
        "production",
    ))
    names = tuple(
        sorted(
            name
            for line in listed.stdout.splitlines()
            if (name := line.strip()).startswith(prefixes)
        )
    )
    for prefix in prefixes:
        if not any(name.startswith(prefix) for name in names):
            raise DevelopmentE2EError(
                f"DEVELOPMENT_E2E_VOLUME_SENTINEL_MISSING: {prefix}"
            )
    inspected = subprocess.run(
        (
            docker_executable,
            "volume",
            "inspect",
            *names,
            "--format",
            "{{.Name}}|{{.CreatedAt}}|{{.Mountpoint}}",
        ),
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if inspected.returncode != 0:
        raise DevelopmentE2EError("DEVELOPMENT_E2E_VOLUME_INSPECTION_FAILED")
    sentinels = tuple(sorted(line.strip() for line in inspected.stdout.splitlines() if line.strip()))
    if len(sentinels) != len(names):
        raise DevelopmentE2EError("DEVELOPMENT_E2E_VOLUME_INSPECTION_INCOMPLETE")
    return sentinels


def _verify_volume_sentinels_preserved(
    *,
    initial: tuple[str, ...],
    final: tuple[str, ...],
) -> None:
    missing_or_recreated = tuple(sorted(set(initial) - set(final)))
    if missing_or_recreated:
        raise DevelopmentE2EError(
            "DEVELOPMENT_E2E_VOLUME_SENTINELS_CHANGED: "
            + ",".join(missing_or_recreated)
        )


def _wait_action_progress(
    client: httpx.Client,
    *,
    path: str,
    expected_action: str,
    timeout_seconds: int,
) -> Mapping[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    previous_completed = -1
    while time.monotonic() < deadline:
        progress = _get_json(client, path)
        if progress.get("action_name") != expected_action:
            raise DevelopmentE2EError("DEVELOPMENT_E2E_PROGRESS_ACTION_MISMATCH")
        phase = _require_text(progress.get("phase"), "progress_phase")
        completed = progress.get("completed_units")
        total = progress.get("total_units")
        failure = progress.get("failure_error_code")
        if isinstance(completed, bool) or not isinstance(completed, int) or completed < 0:
            raise DevelopmentE2EError("DEVELOPMENT_E2E_PROGRESS_COMPLETED_INVALID")
        if isinstance(total, bool) or not isinstance(total, int) or total < 1:
            raise DevelopmentE2EError("DEVELOPMENT_E2E_PROGRESS_TOTAL_INVALID")
        if completed < previous_completed or completed > total:
            raise DevelopmentE2EError("DEVELOPMENT_E2E_PROGRESS_NON_MONOTONIC")
        previous_completed = completed
        if phase == "FAILED":
            raise DevelopmentE2EError(
                f"DEVELOPMENT_E2E_ACTION_FAILED: {expected_action}: {failure!r}"
            )
        if failure is not None:
            raise DevelopmentE2EError("DEVELOPMENT_E2E_PROGRESS_ERROR_IN_NON_FAILED_PHASE")
        if phase == "SUCCEEDED":
            if completed != total:
                raise DevelopmentE2EError("DEVELOPMENT_E2E_PROGRESS_SUCCESS_INCOMPLETE")
            return progress
        if phase not in {"QUEUED", "RUNNING"}:
            raise DevelopmentE2EError(
                f"DEVELOPMENT_E2E_PROGRESS_PHASE_INVALID: {phase}"
            )
        time.sleep(2)
    raise DevelopmentE2EError(f"DEVELOPMENT_E2E_PROGRESS_TIMEOUT: {expected_action}")


def _request_empty_command(client: httpx.Client, path: str, *, expected_status: int) -> None:
    response = client.post(path, content=b"")
    if response.status_code != expected_status:
        _raise_http("DEVELOPMENT_E2E_COMMAND_FAILED", response)


def _find_document(client: httpx.Client, document_id: str) -> Mapping[str, Any]:
    cursor: str | None = None
    while True:
        path = "/v1/documents?limit=100"
        if cursor is not None:
            path = f"{path}&cursor={quote(cursor)}"
        payload = _get_json(client, path)
        documents = payload.get("documents")
        if not isinstance(documents, list):
            raise DevelopmentE2EError("DEVELOPMENT_E2E_DOCUMENT_LIST_INVALID")
        for document in documents:
            parsed = _require_mapping(document, "document")
            if parsed.get("document_id") == document_id:
                return parsed
        cursor_value = payload.get("next_cursor")
        if cursor_value is None:
            raise DevelopmentE2EError(
                f"DEVELOPMENT_E2E_DOCUMENT_NOT_FOUND: {document_id}"
            )
        cursor = _require_text(cursor_value, "next_cursor")


def _all_public_document_ids(client: httpx.Client) -> tuple[str, ...]:
    cursor: str | None = None
    identifiers: list[str] = []
    while True:
        path = "/v1/documents?limit=100"
        if cursor is not None:
            path = f"{path}&cursor={quote(cursor)}"
        payload = _get_json(client, path)
        documents = payload.get("documents")
        if not isinstance(documents, list):
            raise DevelopmentE2EError("DEVELOPMENT_E2E_DOCUMENT_LIST_INVALID")
        identifiers.extend(
            _require_identifier(
                _require_mapping(document, "document").get("document_id"),
                "DOC",
                "document_id",
            )
            for document in documents
        )
        cursor_value = payload.get("next_cursor")
        if cursor_value is None:
            return tuple(identifiers)
        cursor = _require_text(cursor_value, "next_cursor")


def _verify_original_pdf(
    *,
    client: httpx.Client,
    path: str,
    expected_sha256: str,
) -> None:
    response = client.get(path)
    if response.status_code != 200:
        _raise_http("DEVELOPMENT_E2E_ORIGINAL_OPEN_FAILED", response)
    if response.headers.get("content-type") != "application/pdf":
        raise DevelopmentE2EError("DEVELOPMENT_E2E_ORIGINAL_CONTENT_TYPE_INVALID")
    if not response.content.startswith(b"%PDF-"):
        raise DevelopmentE2EError("DEVELOPMENT_E2E_ORIGINAL_NOT_PDF")
    if hashlib.sha256(response.content).hexdigest() != expected_sha256:
        raise DevelopmentE2EError("DEVELOPMENT_E2E_ORIGINAL_HASH_MISMATCH")


def _get_json(client: httpx.Client, path: str) -> Mapping[str, Any]:
    response = client.get(path)
    if response.status_code != 200:
        _raise_http("DEVELOPMENT_E2E_PUBLIC_READ_FAILED", response)
    return _json_mapping(response, path)


def _raise_http(error_code: str, response: httpx.Response) -> None:
    body = response.text[:1000]
    raise DevelopmentE2EError(
        f"{error_code}: status={response.status_code}: body={body!r}"
    )


def _json_mapping(response: httpx.Response, context: str) -> Mapping[str, Any]:
    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise DevelopmentE2EError(
            f"DEVELOPMENT_E2E_JSON_INVALID: {context}"
        ) from exc
    return _require_mapping(payload, context)


@contextmanager
def _public_client(
    *,
    token: str,
    timeout_seconds: int,
    base_url: str = _API_BASE_URL,
) -> Iterator[httpx.Client]:
    with httpx.Client(
        base_url=base_url,
        headers={"Authorization": f"Bearer {token}"},
        verify=False,
        timeout=timeout_seconds,
        trust_env=False,
    ) as client:
        yield client


def _write_secret_free_report(
    report: DevelopmentE2EReport,
    *,
    configuration: ApplicationConfiguration,
    repository_root: Path,
) -> None:
    payload = asdict(report)
    payload["report_path"] = str(report.report_path)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    secret_paths = (
        configuration.security.secrets.postgres_password_path,
        configuration.security.secrets.qdrant_api_key_path,
        configuration.security.secrets.llm_gateway_api_key_path,
        configuration.security.secrets.tls_ca_certificate_path,
        configuration.security.secrets.local_api_token_path,
    )
    for secret_path in secret_paths:
        if _read_secret(repository_root / secret_path) in serialized:
            raise DevelopmentE2EError("DEVELOPMENT_E2E_REPORT_SECRET_LEAK")
    report.report_path.write_text(serialized, encoding="utf-8", newline="\n")


def _require_real_versioned_pdf(repository_root: Path, pdf_path: Path) -> Path:
    if not isinstance(pdf_path, Path):
        raise ValueError("DEVELOPMENT_E2E_PDF_PATH_INVALID")
    path = pdf_path.resolve()
    corpus_root = (repository_root / "data" / "corpus").resolve()
    try:
        relative = path.relative_to(corpus_root)
    except ValueError as exc:
        raise ValueError("DEVELOPMENT_E2E_PDF_OUTSIDE_CORPUS") from exc
    if not path.is_file() or path.suffix.lower() != ".pdf" or path.stat().st_size < 100_000:
        raise ValueError("DEVELOPMENT_E2E_REAL_PDF_REQUIRED")
    git_executable = shutil.which("git")
    if git_executable is None:
        raise ValueError("DEVELOPMENT_E2E_GIT_UNAVAILABLE")
    result = subprocess.run(
        (git_executable, "ls-files", "--error-unmatch", f"data/corpus/{relative.as_posix()}"),
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise ValueError("DEVELOPMENT_E2E_VERSIONED_PDF_REQUIRED")
    return path


def _prepare_reemitted_real_pdf(
    *,
    source_pdf: Path,
    temporary_report_root: Path,
    proof_id: str,
) -> Path:
    if not isinstance(source_pdf, Path) or not source_pdf.is_file():
        raise ValueError("DEVELOPMENT_E2E_REAL_PDF_REQUIRED")
    if not isinstance(temporary_report_root, Path):
        raise ValueError("DEVELOPMENT_E2E_REPORT_PATH_INVALID")
    if tuple(temporary_report_root.parts[-2:]) != ("reports", "temp"):
        raise ValueError("DEVELOPMENT_E2E_TEMP_REPORT_PATH_INVALID")
    if re.fullmatch(r"[A-F0-9]{32}", proof_id) is None:
        raise ValueError("DEVELOPMENT_E2E_PROOF_ID_INVALID")

    source_reader = PdfReader(str(source_pdf), strict=True)
    if len(source_reader.pages) != 38:
        raise ValueError("DEVELOPMENT_E2E_SOURCE_PAGE_COUNT_INVALID")
    source_page_hashes = _pdf_page_content_hashes(source_reader)
    source_sha256 = _sha256_file(source_pdf)
    writer = PdfWriter()
    for page in source_reader.pages:
        writer.add_page(page)
    writer.add_metadata(
        {
            "/OSTradingProofId": proof_id,
            "/OSTradingSourceSHA256": source_sha256,
        }
    )

    temporary_report_root.mkdir(parents=True, exist_ok=True)
    derived_pdf = temporary_report_root / f"development-e2e-{proof_id}.pdf"
    try:
        with derived_pdf.open("xb") as stream:
            writer.write(stream)
    except OSError as exc:
        raise DevelopmentE2EError("DEVELOPMENT_E2E_REEMITTED_PDF_WRITE_FAILED") from exc

    derived_bytes = derived_pdf.read_bytes()
    if not derived_bytes.startswith(b"%PDF-") or not derived_bytes.rstrip().endswith(b"%%EOF"):
        raise DevelopmentE2EError("DEVELOPMENT_E2E_REEMITTED_PDF_ENVELOPE_INVALID")
    derived_reader = PdfReader(str(derived_pdf), strict=True)
    if len(derived_reader.pages) != 38:
        raise DevelopmentE2EError("DEVELOPMENT_E2E_REEMITTED_PAGE_COUNT_INVALID")
    if _pdf_page_content_hashes(derived_reader) != source_page_hashes:
        raise DevelopmentE2EError("DEVELOPMENT_E2E_REEMITTED_PAGE_CONTENT_MISMATCH")
    if derived_reader.metadata.get("/OSTradingProofId") != proof_id:
        raise DevelopmentE2EError("DEVELOPMENT_E2E_REEMITTED_METADATA_MISMATCH")
    if _sha256_file(derived_pdf) == source_sha256:
        raise DevelopmentE2EError("DEVELOPMENT_E2E_REEMITTED_PDF_NOT_UNIQUE")
    return derived_pdf


def _pdf_page_content_hashes(reader: PdfReader) -> tuple[str, ...]:
    hashes: list[str] = []
    for page in reader.pages:
        contents = page.get_contents()
        content_bytes = b"" if contents is None else contents.get_data()
        hashes.append(hashlib.sha256(content_bytes).hexdigest())
    return tuple(hashes)


def _require_development_configuration(configuration: ApplicationConfiguration) -> None:
    if not isinstance(configuration, ApplicationConfiguration):
        raise ValueError("DEVELOPMENT_E2E_CONFIGURATION_INVALID")
    if (
        configuration.application.environment != _ENVIRONMENT
        or configuration.application.deployment_id != _DEPLOYMENT_ID
    ):
        raise ValueError("CONFIG_ENVIRONMENT_MISMATCH: preuve development")
    if configuration.services.llm_gateway.spark_endpoint_url != "http://192.168.1.120:8000/v1":
        raise ValueError("DEVELOPMENT_E2E_SPARK_ENDPOINT_INVALID")
    if configuration.quality_gates.llm.real_path_required is not True:
        raise ValueError("DEVELOPMENT_E2E_REAL_PATH_REQUIRED")
    if configuration.quality_gates.llm.fallback_model_allowed is not False:
        raise ValueError("DEVELOPMENT_E2E_LLM_FALLBACK_FORBIDDEN")


def _require_repository_root(value: Path) -> Path:
    if not isinstance(value, Path):
        raise ValueError("DEVELOPMENT_E2E_REPOSITORY_ROOT_INVALID")
    root = value.resolve()
    if not (root / "pyproject.toml").is_file():
        raise ValueError("DEVELOPMENT_E2E_REPOSITORY_ROOT_INVALID")
    return root


def _require_profile_path(path: Path) -> None:
    if "development" not in path.parts:
        raise ValueError("DEVELOPMENT_E2E_PROFILE_PATH_INVALID")


def _read_secret(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"DEVELOPMENT_E2E_SECRET_UNREADABLE: {path}")
    value = path.read_text(encoding="utf-8").strip()
    if len(value.encode("utf-8")) < 32:
        raise ValueError(f"DEVELOPMENT_E2E_SECRET_INVALID: {path}")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _git_revision(repository_root: Path) -> str:
    git_executable = shutil.which("git")
    if git_executable is None:
        raise ValueError("DEVELOPMENT_E2E_GIT_UNAVAILABLE")
    result = subprocess.run(
        (git_executable, "rev-parse", "HEAD"),
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="ascii",
        errors="replace",
    )
    revision = result.stdout.strip()
    if result.returncode != 0:
        raise ValueError("DEVELOPMENT_E2E_GIT_REVISION_INVALID")
    return _require_git_revision(revision)


def _require_git_revision(value: object) -> str:
    text = _require_text(value, "image_revision")
    if re.fullmatch(r"[0-9a-f]{40}", text) is None:
        raise ValueError("DEVELOPMENT_E2E_GIT_REVISION_INVALID")
    return text


def _require_mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"DEVELOPMENT_E2E_MAPPING_REQUIRED: {field_name}")
    return value


def _require_identifier(value: object, prefix: str, field_name: str) -> str:
    text = _require_text(value, field_name)
    if re.fullmatch(rf"{re.escape(prefix)}-[A-Z0-9][A-Z0-9-]*", text) is None:
        raise ValueError(f"DEVELOPMENT_E2E_IDENTIFIER_INVALID: {field_name}")
    return text


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(f"DEVELOPMENT_E2E_TEXT_REQUIRED: {field_name}")
    return value


def _require_sha256(value: object, field_name: str) -> str:
    text = _require_text(value, field_name)
    if re.fullmatch(r"[0-9a-f]{64}", text) is None:
        raise ValueError(f"DEVELOPMENT_E2E_SHA256_INVALID: {field_name}")
    return text


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _require_utc(value: object, field_name: str) -> str:
    text = _require_text(value, field_name)
    if not text.endswith("Z"):
        raise ValueError(f"DEVELOPMENT_E2E_UTC_REQUIRED: {field_name}")
    datetime.fromisoformat(text.removesuffix("Z") + "+00:00")
    return text


__all__ = [
    "DevelopmentE2EError",
    "DevelopmentE2EReport",
    "run_development_environment_e2e",
]
