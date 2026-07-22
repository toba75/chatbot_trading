"""Preuve réelle, persistante et non destructive de l'environnement production."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Final
from uuid import uuid4

import httpx

from app.platform.configuration import (
    ApplicationConfiguration,
    load_application_configuration,
)
from app.platform.development_e2e import (
    DevelopmentE2EError,
    _EXPECTED_QUALIFICATION_ROUTES,
    _ProofContext,
    _exercise_product,
    _git_revision,
    _prepare_reemitted_real_pdf,
    _probe_foreign_environment,
    _public_client,
    _read_secret,
    _require_real_versioned_pdf,
    _sha256_file,
    verify_worker_documents_runtime_limits,
    _verify_persistence_after_restart,
    _verify_public_readiness,
    _verify_public_ui,
    _write_secret_free_payload,
)
from app.platform.environment_compose import (
    _run_compose,
    _technical_environment_from_repository,
    environment_stack_definition,
    export_environment_caddy_ca,
    render_environment_compose,
    start_environment_compose_stack,
)
from app.platform.configured_datastore_identity import preflight_all_mutable_roots


_ENVIRONMENT: Final = "production"
_DEPLOYMENT_ID: Final = "ostrading-production-primary"
_EDGE_BASE_URL: Final = "https://localhost:20443"
_PRODUCTION_PROOF_CONTEXT: Final = _ProofContext(
    environment=_ENVIRONMENT,
    deployment_id=_DEPLOYMENT_ID,
    edge_base_url=_EDGE_BASE_URL,
)
_EXPECTED_PRODUCTION_VOLUMES: Final = frozenset(
    {
        "ostrading-production-application-data",
        "ostrading-production-caddy-config",
        "ostrading-production-caddy-data",
        "ostrading-production-model-cache",
        "ostrading-production-ocr-runtime-data",
        "ostrading-production-postgres-data",
        "ostrading-production-qdrant-data",
    }
)


class ProductionE2EError(RuntimeError):
    """Échec terminal stable de la preuve production réelle."""


@dataclass(frozen=True, slots=True)
class ProductionE2EReport:
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
    qualification_routes: tuple[str, str, str, str, str]
    progress_phases: tuple[str, str, str]
    worker_identity_count: int
    container_count: int
    environment_job_count: int
    https_ca_verified: bool
    caddy_ca_sha256: str
    restart_persistence_verified: bool
    foreign_environment_probes: tuple[str, str]
    production_resources_preserved: bool
    non_production_credentials_inaccessible: bool
    automatic_cleanup_performed: bool
    completed_at: str
    report_path: Path

    def __post_init__(self) -> None:
        if self.environment != _ENVIRONMENT or self.deployment_id != _DEPLOYMENT_ID:
            raise ValueError("PRODUCTION_E2E_IDENTITY_INVALID")
        for value, code in (
            (self.configuration_hash, "PRODUCTION_E2E_CONFIGURATION_HASH_INVALID"),
            (self.source_pdf_sha256, "PRODUCTION_E2E_SOURCE_HASH_INVALID"),
            (self.pdf_sha256, "PRODUCTION_E2E_PDF_HASH_INVALID"),
        ):
            if re.fullmatch(r"[0-9a-f]{64}", value) is None:
                raise ValueError(code)
        if re.fullmatch(r"[0-9a-f]{40}", self.image_revision) is None:
            raise ValueError("PRODUCTION_E2E_IMAGE_REVISION_INVALID")
        if self.source_pdf_sha256 == self.pdf_sha256:
            raise ValueError("PRODUCTION_E2E_REEMITTED_PDF_REQUIRED")
        for prefix, value in (
            ("DOC", self.document_id),
            ("CVER", self.canonical_version_id),
            ("PROJ", self.projection_id),
            ("ANS", self.answer_id),
        ):
            if re.fullmatch(rf"{prefix}-[A-Z0-9][A-Z0-9-]*", value) is None:
                raise ValueError("PRODUCTION_E2E_PRODUCT_IDENTIFIER_INVALID")
        if not self.citation_url.startswith(
            f"{_EDGE_BASE_URL}/api/v1/documents/{self.document_id}/original#page="
        ):
            raise ValueError("PRODUCTION_E2E_CITATION_URL_INVALID")
        if not isinstance(self.spark_raw_response_id, str) or self.spark_raw_response_id == "":
            raise ValueError("PRODUCTION_E2E_SPARK_RESPONSE_ID_INVALID")
        if self.support_status not in {"SUPPORTED", "PARTIALLY_SUPPORTED"}:
            raise ValueError("PRODUCTION_E2E_SUPPORT_STATUS_INVALID")
        if self.qualification_routes != _EXPECTED_QUALIFICATION_ROUTES:
            raise ValueError("PRODUCTION_E2E_QUALIFICATION_ROUTES_INVALID")
        if self.progress_phases != ("SUCCEEDED", "SUCCEEDED", "SUCCEEDED"):
            raise ValueError("PRODUCTION_E2E_PROGRESS_INVALID")
        if (
            self.worker_identity_count != 4
            or self.container_count != 14
            or self.environment_job_count < 3
        ):
            raise ValueError("PRODUCTION_E2E_ENVIRONMENT_IDENTITY_INCOMPLETE")
        if self.https_ca_verified is not True:
            raise ValueError("PRODUCTION_E2E_HTTPS_CA_NOT_VERIFIED")
        if re.fullmatch(r"[0-9a-f]{64}", self.caddy_ca_sha256) is None:
            raise ValueError("PRODUCTION_E2E_CADDY_CA_HASH_INVALID")
        if self.restart_persistence_verified is not True:
            raise ValueError("PRODUCTION_E2E_RESTART_NOT_PROVEN")
        if any(
            observed not in {f"{environment}:ABSENT", f"{environment}:ISOLATED"}
            for environment, observed in zip(
                ("development", "test"),
                self.foreign_environment_probes,
                strict=True,
            )
        ):
            raise ValueError("PRODUCTION_E2E_FOREIGN_PROBES_INVALID")
        if self.production_resources_preserved is not True:
            raise ValueError("PRODUCTION_E2E_RESOURCES_NOT_PRESERVED")
        if self.non_production_credentials_inaccessible is not True:
            raise ValueError("PRODUCTION_E2E_NON_PRODUCTION_CREDENTIALS_ACCESSIBLE")
        if self.automatic_cleanup_performed is not False:
            raise ValueError("PRODUCTION_E2E_AUTOMATIC_CLEANUP_FORBIDDEN")
        _require_utc(self.completed_at)
        if not isinstance(self.report_path, Path):
            raise ValueError("PRODUCTION_E2E_REPORT_PATH_INVALID")

    def to_mapping(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["report_path"] = str(self.report_path)
        return payload


@dataclass(frozen=True, slots=True)
class _ProductionLaunchConfiguration:
    environment: str
    service_id: str
    port: int
    config_path: str


def run_production_environment_e2e(
    *,
    repository_root: Path,
    pdf_path: Path,
) -> ProductionE2EReport:
    """Traverse production, redémarre et conserve toutes les preuves."""

    root = _require_repository_root(repository_root)
    qualified_revision = _git_revision(root)
    source_pdf = _require_real_versioned_pdf(root, pdf_path)
    configuration = load_application_configuration(
        config_path=root / "config" / "environments" / "production.yaml",
        environment_snapshot=dict(os.environ),
    )
    _require_production_configuration(configuration)
    preflight_all_mutable_roots(configuration, initialize_if_empty=True)
    report_root = (root / configuration.paths.reports_root).resolve()
    _require_production_path(report_root)
    report_root.mkdir(parents=True, exist_ok=True)
    initial_sentinels = _production_volume_sentinels(repository_root=root)
    rendered = render_environment_compose(
        environment_stack_definition(_ENVIRONMENT, repository_root=root),
        technical_environment=_technical_environment_from_repository(root),
    )
    _verify_production_compose_document(rendered)

    proof_id = uuid4().hex.upper()
    selected_pdf = _prepare_production_reemitted_pdf(
        source_pdf=source_pdf,
        report_root=report_root,
        proof_id=proof_id,
    )
    pdf_sha256 = _sha256_file(selected_pdf)
    token = _read_secret(root / configuration.security.secrets.local_api_token_path)
    checkpoint_path = report_root / f"production-e2e-checkpoint-{proof_id}.json"
    product_holder: list[Any] = []

    def run_stack(*, phase: str) -> str:
        ca_bundle_path = report_root / "certificates" / f"production-{phase}-caddy-root.crt"
        ca_bundle_path.parent.mkdir(parents=True, exist_ok=True)
        launch_configuration = _ProductionLaunchConfiguration(
            environment=_ENVIRONMENT,
            service_id="ui",
            port=8081,
            config_path=str(
                (root / "config" / "environments" / "production.yaml").resolve()
            ),
        )
        with start_environment_compose_stack(
            launch_configuration
        ), _production_red_report_guard(
            proof_id=proof_id,
            phase=phase,
            checkpoint_path=checkpoint_path,
            configuration=configuration,
            repository_root=root,
        ):
            export_environment_caddy_ca(
                environment=_ENVIRONMENT,
                repository_root=root,
                destination_path=ca_bundle_path,
                technical_environment=_technical_environment_from_repository(root),
            )
            _verify_runtime_excludes_non_production_credentials(repository_root=root)
            with _public_client(
                token=token,
                timeout_seconds=900,
                base_url=_PRODUCTION_PROOF_CONTEXT.api_base_url,
                ca_bundle_path=ca_bundle_path,
            ) as client:
                _verify_public_readiness(
                    client,
                    expected_environment=configuration.application.environment,
                    expected_deployment_id=configuration.application.deployment_id,
                    expected_configuration_hash=configuration.configuration_hash,
                )
                _verify_public_ui(client, proof_context=_PRODUCTION_PROOF_CONTEXT)
                if phase == "product":
                    try:
                        product = _exercise_product(
                            client=client,
                            configuration=configuration,
                            pdf_path=selected_pdf,
                            pdf_sha256=pdf_sha256,
                            proof_id=proof_id,
                            repository_root=root,
                            existing_document_id=None,
                            proof_context=_PRODUCTION_PROOF_CONTEXT,
                        )
                    except (DevelopmentE2EError, ValueError, httpx.TransportError) as exc:
                        raise ProductionE2EError(
                            f"PRODUCTION_E2E_PRODUCT_FAILED: {_error_code(exc)}"
                        ) from exc
                    product_holder.append(product)
                    _write_secret_free_payload(
                        payload={
                            "event_type": "production_e2e_product_checkpoint",
                            "environment": _ENVIRONMENT,
                            "deployment_id": _DEPLOYMENT_ID,
                            "proof_id": proof_id,
                            "pdf_sha256": pdf_sha256,
                            "created_at": _utc_now(),
                            **asdict(product),
                        },
                        output_path=checkpoint_path,
                        configuration=configuration,
                        repository_root=root,
                    )
                elif phase == "restart-read":
                    if len(product_holder) != 1:
                        raise ProductionE2EError("PRODUCTION_E2E_PRODUCT_PROOF_MISSING")
                    try:
                        _verify_persistence_after_restart(
                            client=client,
                            product=product_holder[0],
                            pdf_sha256=pdf_sha256,
                            proof_id=proof_id,
                            proof_context=_PRODUCTION_PROOF_CONTEXT,
                        )
                    except (DevelopmentE2EError, ValueError, httpx.TransportError) as exc:
                        raise ProductionE2EError(
                            f"PRODUCTION_E2E_RESTART_READ_FAILED: {_error_code(exc)}"
                        ) from exc
                else:
                    raise ValueError("PRODUCTION_E2E_PHASE_INVALID")
        return phase

    _run_production_stack_twice(stack_runner=run_stack)
    if len(product_holder) != 1:
        raise ProductionE2EError("PRODUCTION_E2E_PRODUCT_PROOF_MISSING")
    product = product_holder[0]

    development_probe = _probe_development_absence(
        repository_root=root,
        forbidden_document_id=product.document_id,
    )
    test_probe = _probe_test_storage_absence(
        repository_root=root,
        forbidden_document_id=product.document_id,
    )
    final_sentinels = _production_volume_sentinels(repository_root=root)
    _verify_production_sentinels_preserved(
        initial=initial_sentinels,
        final=final_sentinels,
    )
    _verify_production_containers_stopped(repository_root=root)

    completed_at = _utc_now()
    report_path = report_root / (
        f"production-e2e-{completed_at.replace(':', '').replace('-', '')}-{proof_id}.json"
    )
    report = ProductionE2EReport(
        environment=_ENVIRONMENT,
        deployment_id=_DEPLOYMENT_ID,
        configuration_hash=configuration.configuration_hash,
        image_revision=qualified_revision,
        source_pdf_path=source_pdf.relative_to(root).as_posix(),
        source_pdf_sha256=_sha256_file(source_pdf),
        pdf_path=selected_pdf.relative_to(root).as_posix(),
        pdf_sha256=pdf_sha256,
        document_id=product.document_id,
        canonical_version_id=product.canonical_version_id,
        projection_id=product.projection_id,
        answer_id=product.answer_id,
        citation_url=product.citation_url,
        spark_raw_response_id=product.spark_raw_response_id,
        support_status=product.support_status,
        qualification_routes=product.qualification_routes,
        progress_phases=product.progress_phases,
        worker_identity_count=product.worker_identity_count,
        container_count=product.container_count,
        environment_job_count=product.environment_job_count,
        https_ca_verified=True,
        caddy_ca_sha256=_sha256_file(
            report_root / "certificates" / "production-restart-read-caddy-root.crt"
        ),
        restart_persistence_verified=True,
        foreign_environment_probes=(development_probe, test_probe),
        production_resources_preserved=True,
        non_production_credentials_inaccessible=True,
        automatic_cleanup_performed=False,
        completed_at=completed_at,
        report_path=report_path,
    )
    _write_secret_free_payload(
        payload=report.to_mapping(),
        output_path=report_path,
        configuration=configuration,
        repository_root=root,
    )
    return report


@contextmanager
def _production_red_report_guard(
    *,
    proof_id: str,
    phase: str,
    checkpoint_path: Path,
    configuration: ApplicationConfiguration,
    repository_root: Path,
):
    try:
        yield
    except (
        ProductionE2EError,
        DevelopmentE2EError,
        ValueError,
        httpx.TransportError,
    ) as exc:
        if isinstance(exc, httpx.TransportError):
            error_code = "PRODUCTION_E2E_NETWORK_FAILED"
        elif isinstance(exc, DevelopmentE2EError):
            error_code = "PRODUCTION_E2E_SHARED_FAILURE"
        else:
            error_code = _error_code(exc)
        _write_secret_free_payload(
            payload={
                "event_type": "production_e2e_checkpoint",
                "status": "RED",
                "environment": _ENVIRONMENT,
                "deployment_id": _DEPLOYMENT_ID,
                "proof_id": proof_id,
                "phase": phase,
                "error_code": error_code,
                "completed_at": _utc_now(),
            },
            output_path=checkpoint_path,
            configuration=configuration,
            repository_root=repository_root,
        )
        if isinstance(exc, ProductionE2EError):
            raise
        raise ProductionE2EError(error_code) from exc


def _run_production_stack_twice(
    *,
    stack_runner: Callable[..., Any],
) -> tuple[Any, Any]:
    if not callable(stack_runner):
        raise ValueError("PRODUCTION_E2E_STACK_RUNNER_INVALID")
    first = stack_runner(phase="product")
    second = stack_runner(phase="restart-read")
    return first, second


def _verify_production_compose_document(
    document: Mapping[str, Any],
) -> Mapping[str, Any]:
    if not isinstance(document, Mapping):
        raise ValueError("PRODUCTION_E2E_COMPOSE_DOCUMENT_INVALID")
    if document.get("name") != "ostrading-production":
        raise ProductionE2EError("PRODUCTION_E2E_COMPOSE_IDENTITY_INVALID")
    serialized = json.dumps(document, sort_keys=True).replace("\\\\", "/").replace("\\", "/").lower()
    forbidden = (
        "config/secrets/development",
        "config/secrets/test",
        "config/environments/development.yaml",
        "config/environments/test.yaml",
        "data/environments/development",
        "data/environments/test",
    )
    collision = next((path for path in forbidden if path in serialized), None)
    if collision is not None:
        raise ProductionE2EError(
            f"PRODUCTION_E2E_NON_PRODUCTION_RESOURCE_VISIBLE: {collision}"
        )
    services = document.get("services")
    if not isinstance(services, Mapping):
        raise ProductionE2EError("PRODUCTION_E2E_COMPOSE_SERVICES_INVALID")
    worker = services.get("worker-documents")
    if not isinstance(worker, Mapping):
        raise ProductionE2EError("PRODUCTION_E2E_WORKER_DOCUMENTS_MISSING")
    deploy = worker.get("deploy")
    resources = deploy.get("resources") if isinstance(deploy, Mapping) else None
    limits = resources.get("limits") if isinstance(resources, Mapping) else None
    if not isinstance(limits, Mapping):
        raise ProductionE2EError("PRODUCTION_E2E_WORKER_DOCUMENTS_RESOURCES_INVALID")
    if limits.get("memory") != str(8 * 1024**3) or limits.get("cpus") != 4:
        raise ProductionE2EError("PRODUCTION_E2E_WORKER_DOCUMENTS_RESOURCES_INVALID")
    healthcheck = worker.get("healthcheck")
    if not isinstance(healthcheck, Mapping) or healthcheck.get("timeout") != "30s":
        raise ProductionE2EError("PRODUCTION_E2E_WORKER_DOCUMENTS_HEALTHCHECK_INVALID")
    for resource_kind in ("volumes", "networks"):
        resources_by_name = document.get(resource_kind)
        if not isinstance(resources_by_name, Mapping):
            raise ProductionE2EError("PRODUCTION_E2E_COMPOSE_RESOURCES_INVALID")
        for resource in resources_by_name.values():
            if not isinstance(resource, Mapping):
                raise ProductionE2EError("PRODUCTION_E2E_COMPOSE_RESOURCE_INVALID")
            name = resource.get("name")
            if not isinstance(name, str) or not name.startswith("ostrading-production-"):
                raise ProductionE2EError("PRODUCTION_E2E_COMPOSE_RESOURCE_IDENTITY_INVALID")
    return document


def _verify_runtime_excludes_non_production_credentials(
    *,
    repository_root: Path,
) -> None:
    definition = environment_stack_definition(
        _ENVIRONMENT,
        repository_root=repository_root,
    )
    technical_environment = _technical_environment_from_repository(repository_root)
    result = _run_compose(
        definition,
        ("ps", "--all", "--format", "json"),
        technical_environment=technical_environment,
        capture_output=True,
    )
    container_names: list[str] = []
    for line in result.stdout.splitlines():
        if line.strip() == "":
            continue
        payload = json.loads(line)
        if not isinstance(payload, Mapping):
            raise ProductionE2EError("PRODUCTION_E2E_COMPOSE_PS_INVALID")
        name = payload.get("Name")
        if not isinstance(name, str) or not name.startswith("ostrading-production-"):
            raise ProductionE2EError("PRODUCTION_E2E_CONTAINER_IDENTITY_INVALID")
        container_names.append(name)
    if len(container_names) != 14:
        raise ProductionE2EError("PRODUCTION_E2E_CONTAINER_COUNT_INVALID")
    inspected = subprocess.run(
        (_docker_executable(), "inspect", *container_names),
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if inspected.returncode != 0:
        raise ProductionE2EError("PRODUCTION_E2E_CONTAINER_INSPECTION_FAILED")
    verify_worker_documents_runtime_limits(inspected.stdout, environment="production")
    normalized = inspected.stdout.replace("\\\\", "/").replace("\\", "/").lower()
    for forbidden in (
        "config/secrets/development",
        "config/secrets/test",
        "config/environments/development.yaml",
        "config/environments/test.yaml",
        "data/environments/development",
        "data/environments/test",
    ):
        if forbidden in normalized:
            raise ProductionE2EError(
                f"PRODUCTION_E2E_NON_PRODUCTION_RESOURCE_VISIBLE: {forbidden}"
            )


def _prepare_production_reemitted_pdf(
    *,
    source_pdf: Path,
    report_root: Path,
    proof_id: str,
) -> Path:
    development_named_path = _prepare_reemitted_real_pdf(
        source_pdf=source_pdf,
        temporary_report_root=report_root / "temp",
        proof_id=proof_id,
    )
    production_named_path = report_root / "temp" / f"production-e2e-{proof_id}.pdf"
    development_named_path.rename(production_named_path)
    return production_named_path


def _probe_development_absence(
    *,
    repository_root: Path,
    forbidden_document_id: str,
) -> str:
    try:
        return _probe_foreign_environment(
            repository_root=repository_root,
            source_environment=_ENVIRONMENT,
            environment="development",
            forbidden_document_id=forbidden_document_id,
        )
    except DevelopmentE2EError as exc:
        raise ProductionE2EError(
            f"PRODUCTION_E2E_DEVELOPMENT_PROBE_FAILED: {_error_code(exc)}"
        ) from exc


def _probe_test_storage_absence(
    *,
    repository_root: Path,
    forbidden_document_id: str,
) -> str:
    try:
        return _probe_foreign_environment(
            repository_root=repository_root,
            source_environment=_ENVIRONMENT,
            environment="test",
            forbidden_document_id=forbidden_document_id,
        )
    except DevelopmentE2EError as exc:
        raise ProductionE2EError(
            f"PRODUCTION_E2E_TEST_PROBE_FAILED: {_error_code(exc)}"
        ) from exc


def _production_volume_sentinels(*, repository_root: Path) -> tuple[str, ...]:
    listed = subprocess.run(
        (_docker_executable(), "volume", "ls", "--format", "{{.Name}}"),
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if listed.returncode != 0:
        raise ProductionE2EError("PRODUCTION_E2E_VOLUME_LIST_FAILED")
    names = tuple(
        sorted(
            name
            for line in listed.stdout.splitlines()
            if (name := line.strip()).startswith("ostrading-production-")
        )
    )
    if not names:
        return ()
    inspected = subprocess.run(
        (
            _docker_executable(),
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
        raise ProductionE2EError("PRODUCTION_E2E_VOLUME_INSPECTION_FAILED")
    return tuple(
        sorted(line.strip() for line in inspected.stdout.splitlines() if line.strip())
    )


def _verify_production_sentinels_preserved(
    *,
    initial: tuple[str, ...],
    final: tuple[str, ...],
) -> None:
    missing_or_recreated = tuple(sorted(set(initial) - set(final)))
    if missing_or_recreated:
        raise ProductionE2EError(
            "PRODUCTION_E2E_VOLUME_SENTINELS_CHANGED: "
            + ",".join(missing_or_recreated)
        )
    final_names = frozenset(item.split("|", 1)[0] for item in final)
    missing_expected = tuple(sorted(_EXPECTED_PRODUCTION_VOLUMES - final_names))
    if missing_expected:
        raise ProductionE2EError(
            "PRODUCTION_E2E_EXPECTED_VOLUME_MISSING: " + ",".join(missing_expected)
        )


def _verify_production_containers_stopped(*, repository_root: Path) -> None:
    listed = subprocess.run(
        (_docker_executable(), "ps", "--all", "--format", "{{.Names}}"),
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if listed.returncode != 0:
        raise ProductionE2EError("PRODUCTION_E2E_CONTAINER_LIST_FAILED")
    remaining = tuple(
        name
        for line in listed.stdout.splitlines()
        if (name := line.strip()).startswith("ostrading-production-")
    )
    if remaining:
        raise ProductionE2EError(
            "PRODUCTION_E2E_CONTAINERS_NOT_STOPPED: " + ",".join(sorted(remaining))
        )


def _require_production_configuration(
    configuration: ApplicationConfiguration,
) -> None:
    if not isinstance(configuration, ApplicationConfiguration):
        raise ValueError("PRODUCTION_E2E_CONFIGURATION_INVALID")
    if (
        configuration.application.environment != _ENVIRONMENT
        or configuration.application.deployment_id != _DEPLOYMENT_ID
    ):
        raise ValueError("CONFIG_ENVIRONMENT_MISMATCH: preuve production")
    if configuration.services.llm_gateway.spark_endpoint_url != "http://192.168.1.120:8000/v1":
        raise ValueError("PRODUCTION_E2E_SPARK_ENDPOINT_INVALID")
    if configuration.quality_gates.llm.real_path_required is not True:
        raise ValueError("PRODUCTION_E2E_REAL_PATH_REQUIRED")
    if configuration.quality_gates.llm.fallback_model_allowed is not False:
        raise ValueError("PRODUCTION_E2E_LLM_FALLBACK_FORBIDDEN")


def _require_repository_root(value: Path) -> Path:
    if not isinstance(value, Path):
        raise ValueError("PRODUCTION_E2E_REPOSITORY_ROOT_INVALID")
    root = value.resolve()
    if not (root / "pyproject.toml").is_file():
        raise ValueError("PRODUCTION_E2E_REPOSITORY_ROOT_INVALID")
    return root


def _require_production_path(path: Path) -> None:
    if "production" not in path.parts:
        raise ValueError("PRODUCTION_E2E_PROFILE_PATH_INVALID")


def _docker_executable() -> str:
    executable = shutil.which("docker")
    if executable is None:
        raise ProductionE2EError("PRODUCTION_E2E_DOCKER_UNAVAILABLE")
    return executable


def _error_code(error: Exception) -> str:
    code = str(error).split(":", 1)[0].strip()
    if code == "":
        raise ValueError("PRODUCTION_E2E_ERROR_CODE_INVALID")
    return code


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _require_utc(value: str) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("PRODUCTION_E2E_UTC_INVALID")
    datetime.fromisoformat(value.removesuffix("Z") + "+00:00")


__all__ = [
    "ProductionE2EError",
    "ProductionE2EReport",
    "run_production_environment_e2e",
]
