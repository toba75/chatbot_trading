"""Qualification réelle, reproductible et jetable de l'environnement test."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Literal
from uuid import UUID, uuid4

from app.platform.configuration import (
    ApplicationConfiguration,
    load_application_configuration,
)
from app.platform.development_e2e import (
    DevelopmentE2EError,
    _ProofContext,
    _all_public_document_ids,
    _exercise_product,
    _git_revision,
    _prepare_reemitted_real_pdf,
    _public_client,
    _read_secret,
    _require_real_versioned_pdf,
    _sha256_file,
    _verify_public_ui,
    _write_secret_free_payload,
)
from app.platform.environment_compose import (
    _run_compose,
    _technical_environment_from_repository,
    environment_stack_definition,
    render_environment_compose,
    start_environment_compose_stack,
)


_ENVIRONMENT = "test"
_DEPLOYMENT_ID = "ostrading-test-ci"
_EDGE_BASE_URL = "https://localhost:19443"
_TEST_PROOF_CONTEXT = _ProofContext(
    environment=_ENVIRONMENT,
    deployment_id=_DEPLOYMENT_ID,
    edge_base_url=_EDGE_BASE_URL,
)


class TestE2EError(RuntimeError):
    """Échec terminal stable de la qualification test réelle."""


@dataclass(frozen=True, slots=True)
class TestEnvironmentCycle:
    """Identité du cycle autorisé à créer puis détruire la pile test."""

    environment: Literal["test", "production"]
    deployment_id: str
    lifecycle_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.environment, str):
            raise ValueError("TEST_E2E_ENVIRONMENT_INVALID")
        if not isinstance(self.deployment_id, str) or self.deployment_id.strip() == "":
            raise ValueError("TEST_E2E_DEPLOYMENT_ID_INVALID")
        try:
            parsed_lifecycle_id = UUID(self.lifecycle_id)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("TEST_E2E_LIFECYCLE_ID_INVALID") from exc
        if parsed_lifecycle_id.version != 4:
            raise ValueError("TEST_E2E_LIFECYCLE_ID_INVALID")


@dataclass(frozen=True, slots=True)
class TestE2ERunReport:
    run_number: int
    proof_id: str
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
    non_test_credentials_inaccessible: bool
    completed_at: str
    pre_teardown_report_path: Path

    def __post_init__(self) -> None:
        if self.run_number not in {1, 2}:
            raise ValueError("TEST_E2E_RUN_NUMBER_INVALID")
        if re.fullmatch(r"[A-F0-9]{32}", self.proof_id) is None:
            raise ValueError("TEST_E2E_PROOF_ID_INVALID")
        if re.fullmatch(r"[0-9a-f]{64}", self.pdf_sha256) is None:
            raise ValueError("TEST_E2E_PDF_HASH_INVALID")
        for prefix, value in (
            ("DOC", self.document_id),
            ("CVER", self.canonical_version_id),
            ("PROJ", self.projection_id),
            ("ANS", self.answer_id),
        ):
            if re.fullmatch(rf"{prefix}-[A-Z0-9][A-Z0-9-]*", value) is None:
                raise ValueError("TEST_E2E_PRODUCT_IDENTIFIER_INVALID")
        if not self.citation_url.startswith(
            f"{_EDGE_BASE_URL}/api/v1/documents/{self.document_id}/original#page="
        ):
            raise ValueError("TEST_E2E_CITATION_URL_INVALID")
        if not isinstance(self.spark_raw_response_id, str) or self.spark_raw_response_id == "":
            raise ValueError("TEST_E2E_SPARK_RESPONSE_ID_INVALID")
        if self.support_status not in {"SUPPORTED", "PARTIALLY_SUPPORTED"}:
            raise ValueError("TEST_E2E_SUPPORT_STATUS_INVALID")
        if self.progress_phases != ("SUCCEEDED", "SUCCEEDED", "SUCCEEDED"):
            raise ValueError("TEST_E2E_PROGRESS_INVALID")
        if self.worker_identity_count < 6 or self.environment_job_count < 3:
            raise ValueError("TEST_E2E_ENVIRONMENT_IDENTITY_INCOMPLETE")
        if self.non_test_credentials_inaccessible is not True:
            raise ValueError("TEST_E2E_NON_TEST_CREDENTIALS_ACCESSIBLE")
        _require_utc(self.completed_at)
        if not isinstance(self.pre_teardown_report_path, Path):
            raise ValueError("TEST_E2E_REPORT_PATH_INVALID")

    def to_mapping(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["pre_teardown_report_path"] = str(self.pre_teardown_report_path)
        return payload


@dataclass(frozen=True, slots=True)
class TestE2EReport:
    environment: str
    deployment_id: str
    configuration_hash: str
    image_revision: str
    source_pdf_path: str
    source_pdf_sha256: str
    runs: tuple[TestE2ERunReport, TestE2ERunReport]
    non_test_credentials_inaccessible: bool
    foreign_volume_sentinels_preserved: bool
    test_resources_removed: bool
    completed_at: str
    report_path: Path

    def __post_init__(self) -> None:
        if self.environment != _ENVIRONMENT or self.deployment_id != _DEPLOYMENT_ID:
            raise ValueError("TEST_E2E_IDENTITY_INVALID")
        if re.fullmatch(r"[0-9a-f]{64}", self.configuration_hash) is None:
            raise ValueError("TEST_E2E_CONFIGURATION_HASH_INVALID")
        if re.fullmatch(r"[0-9a-f]{40}", self.image_revision) is None:
            raise ValueError("TEST_E2E_IMAGE_REVISION_INVALID")
        if re.fullmatch(r"[0-9a-f]{64}", self.source_pdf_sha256) is None:
            raise ValueError("TEST_E2E_SOURCE_HASH_INVALID")
        if tuple(run.run_number for run in self.runs) != (1, 2):
            raise ValueError("TEST_E2E_TWO_RUNS_REQUIRED")
        if self.runs[0].document_id == self.runs[1].document_id:
            raise ValueError("TEST_E2E_DISTINCT_DOCUMENTS_REQUIRED")
        if self.non_test_credentials_inaccessible is not True:
            raise ValueError("TEST_E2E_NON_TEST_CREDENTIALS_ACCESSIBLE")
        if self.foreign_volume_sentinels_preserved is not True:
            raise ValueError("TEST_E2E_FOREIGN_SENTINELS_CHANGED")
        if self.test_resources_removed is not True:
            raise ValueError("TEST_E2E_RESOURCES_NOT_REMOVED")
        _require_utc(self.completed_at)
        if not isinstance(self.report_path, Path):
            raise ValueError("TEST_E2E_REPORT_PATH_INVALID")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "environment": self.environment,
            "deployment_id": self.deployment_id,
            "configuration_hash": self.configuration_hash,
            "image_revision": self.image_revision,
            "source_pdf_path": self.source_pdf_path,
            "source_pdf_sha256": self.source_pdf_sha256,
            "runs": [run.to_mapping() for run in self.runs],
            "non_test_credentials_inaccessible": self.non_test_credentials_inaccessible,
            "foreign_volume_sentinels_preserved": self.foreign_volume_sentinels_preserved,
            "test_resources_removed": self.test_resources_removed,
            "completed_at": self.completed_at,
            "report_path": str(self.report_path),
        }


@dataclass(frozen=True, slots=True)
class _TestLaunchConfiguration:
    environment: str
    service_id: str
    port: int
    config_path: str


def run_test_environment_e2e(
    *,
    repository_root: Path,
    pdf_path: Path,
) -> TestE2EReport:
    """Exécute deux installations test réelles puis supprime leurs ressources."""

    root = _require_repository_root(repository_root)
    source_pdf = _require_real_versioned_pdf(root, pdf_path)
    configuration = load_application_configuration(
        config_path=root / "config" / "environments" / "test.yaml",
        environment_snapshot={},
    )
    _require_test_configuration(configuration)
    report_root = (root / configuration.paths.reports_root).resolve()
    report_root.mkdir(parents=True, exist_ok=True)
    foreign_sentinels = _foreign_volume_sentinels(repository_root=root)
    _verify_test_compose_excludes_non_test_credentials(
        repository_root=root,
    )

    _reset_preexisting_test_installation(
        repository_root=root,
        configuration=configuration,
    )
    _verify_test_resources_removed(repository_root=root)

    runs = _run_two_test_cycles(
        repository_root=root,
        pdf_path=source_pdf,
        cycle_runner=lambda **arguments: _run_single_test_cycle(
            configuration=configuration,
            report_root=report_root,
            **arguments,
        ),
    )
    if not isinstance(runs[0], TestE2ERunReport) or not isinstance(
        runs[1], TestE2ERunReport
    ):
        raise TestE2EError("TEST_E2E_RUN_REPORT_INVALID")
    if runs[0].document_id == runs[1].document_id:
        raise TestE2EError("TEST_E2E_DISTINCT_DOCUMENTS_REQUIRED")
    _verify_test_resources_removed(repository_root=root)
    final_foreign_sentinels = _foreign_volume_sentinels(repository_root=root)
    if final_foreign_sentinels != foreign_sentinels:
        raise TestE2EError("TEST_E2E_FOREIGN_VOLUME_SENTINELS_CHANGED")

    completed_at = _utc_now()
    report_path = report_root / (
        f"test-e2e-{completed_at.replace(':', '').replace('-', '')}.json"
    )
    report = TestE2EReport(
        environment=_ENVIRONMENT,
        deployment_id=_DEPLOYMENT_ID,
        configuration_hash=configuration.configuration_hash,
        image_revision=_git_revision(root),
        source_pdf_path=source_pdf.relative_to(root).as_posix(),
        source_pdf_sha256=_sha256_file(source_pdf),
        runs=(runs[0], runs[1]),
        non_test_credentials_inaccessible=True,
        foreign_volume_sentinels_preserved=True,
        test_resources_removed=True,
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


def _verify_test_cleanup_target(cycle: TestEnvironmentCycle) -> TestEnvironmentCycle:
    if not isinstance(cycle, TestEnvironmentCycle):
        raise ValueError("TEST_E2E_CYCLE_INVALID")
    if cycle.environment != "test" or cycle.deployment_id != "ostrading-test-ci":
        raise ValueError("ADMINISTRATIVE_OPERATION_FORBIDDEN")
    return cycle


def _run_two_test_cycles(
    *,
    repository_root: Path,
    pdf_path: Path,
    cycle_runner: Callable[..., Any],
) -> tuple[Any, Any]:
    if not isinstance(repository_root, Path):
        raise ValueError("TEST_E2E_REPOSITORY_ROOT_INVALID")
    if not isinstance(pdf_path, Path):
        raise ValueError("TEST_E2E_PDF_PATH_INVALID")
    if not callable(cycle_runner):
        raise ValueError("TEST_E2E_CYCLE_RUNNER_INVALID")
    first = cycle_runner(
        run_number=1,
        repository_root=repository_root,
        pdf_path=pdf_path,
    )
    second = cycle_runner(
        run_number=2,
        repository_root=repository_root,
        pdf_path=pdf_path,
    )
    return first, second


def _run_single_test_cycle(
    *,
    run_number: int,
    repository_root: Path,
    pdf_path: Path,
    configuration: ApplicationConfiguration,
    report_root: Path,
) -> TestE2ERunReport:
    proof_id = uuid4().hex.upper()
    selected_pdf = _prepare_test_reemitted_pdf(
        source_pdf=pdf_path,
        report_root=report_root,
        proof_id=proof_id,
    )
    pdf_sha256 = _sha256_file(selected_pdf)
    token = _read_secret(
        repository_root / configuration.security.secrets.local_api_token_path
    )
    pre_teardown_report_path = report_root / (
        f"test-e2e-run-{run_number}-{proof_id}-pre-teardown.json"
    )
    launch_configuration = _TestLaunchConfiguration(
        environment=_ENVIRONMENT,
        service_id="ui",
        port=8081,
        config_path=str(
            (repository_root / "config" / "environments" / "test.yaml").resolve()
        ),
    )

    with start_environment_compose_stack(launch_configuration):
        try:
            _verify_runtime_excludes_non_test_credentials(
                repository_root=repository_root,
            )
            with _public_client(
                token=token,
                timeout_seconds=900,
                base_url=_TEST_PROOF_CONTEXT.api_base_url,
            ) as client:
                _verify_public_ui(client, proof_context=_TEST_PROOF_CONTEXT)
                initial_document_ids = _all_public_document_ids(client)
                if initial_document_ids != ():
                    raise TestE2EError(
                        "TEST_E2E_INITIAL_DATA_NOT_EMPTY: "
                        + ",".join(initial_document_ids)
                    )
                product = _exercise_product(
                    client=client,
                    configuration=configuration,
                    pdf_path=selected_pdf,
                    pdf_sha256=pdf_sha256,
                    proof_id=proof_id,
                    repository_root=repository_root,
                    existing_document_id=None,
                    proof_context=_TEST_PROOF_CONTEXT,
                )
        except (DevelopmentE2EError, TestE2EError, ValueError) as exc:
            _write_secret_free_payload(
                payload={
                    "event_type": "test_e2e_pre_teardown",
                    "status": "RED",
                    "environment": _ENVIRONMENT,
                    "deployment_id": _DEPLOYMENT_ID,
                    "run_number": run_number,
                    "proof_id": proof_id,
                    "pdf_sha256": pdf_sha256,
                    "error_code": _error_code(exc),
                    "completed_at": _utc_now(),
                },
                output_path=pre_teardown_report_path,
                configuration=configuration,
                repository_root=repository_root,
            )
            raise TestE2EError(
                f"TEST_E2E_PRODUCT_FAILED: {_error_code(exc)}"
            ) from exc

        completed_at = _utc_now()
        run_report = TestE2ERunReport(
            run_number=run_number,
            proof_id=proof_id,
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
            non_test_credentials_inaccessible=True,
            completed_at=completed_at,
            pre_teardown_report_path=pre_teardown_report_path,
        )
        _write_secret_free_payload(
            payload={
                "event_type": "test_e2e_pre_teardown",
                "status": "GREEN",
                "environment": _ENVIRONMENT,
                "deployment_id": _DEPLOYMENT_ID,
                **run_report.to_mapping(),
            },
            output_path=pre_teardown_report_path,
            configuration=configuration,
            repository_root=repository_root,
        )

    _verify_test_resources_removed(repository_root=repository_root)
    return run_report


def _reset_preexisting_test_installation(
    *,
    repository_root: Path,
    configuration: ApplicationConfiguration,
) -> None:
    _require_test_configuration(configuration)
    launch_configuration = _TestLaunchConfiguration(
        environment=_ENVIRONMENT,
        service_id="ui",
        port=8081,
        config_path=str(
            (repository_root / "config" / "environments" / "test.yaml").resolve()
        ),
    )
    with start_environment_compose_stack(launch_configuration):
        _verify_runtime_excludes_non_test_credentials(
            repository_root=repository_root,
        )


def _prepare_test_reemitted_pdf(
    *,
    source_pdf: Path,
    report_root: Path,
    proof_id: str,
) -> Path:
    temporary_root = report_root / "temp"
    development_named_path = _prepare_reemitted_real_pdf(
        source_pdf=source_pdf,
        temporary_report_root=temporary_root,
        proof_id=proof_id,
    )
    test_named_path = temporary_root / f"test-e2e-{proof_id}.pdf"
    development_named_path.rename(test_named_path)
    return test_named_path


def _verify_test_compose_excludes_non_test_credentials(
    *,
    repository_root: Path,
) -> None:
    definition = environment_stack_definition(
        _ENVIRONMENT,
        repository_root=repository_root,
    )
    technical_environment = _technical_environment_from_repository(repository_root)
    rendered = render_environment_compose(
        definition,
        technical_environment=technical_environment,
    )
    serialized = json.dumps(rendered, sort_keys=True)
    _reject_non_test_paths(serialized)
    services = rendered.get("services")
    if not isinstance(services, Mapping):
        raise TestE2EError("TEST_E2E_COMPOSE_SERVICES_INVALID")
    worker = services.get("worker-documents")
    if not isinstance(worker, Mapping):
        raise TestE2EError("TEST_E2E_WORKER_DOCUMENTS_MISSING")
    deploy = worker.get("deploy")
    if not isinstance(deploy, Mapping):
        raise TestE2EError("TEST_E2E_WORKER_DOCUMENTS_DEPLOY_INVALID")
    resources = deploy.get("resources")
    if not isinstance(resources, Mapping):
        raise TestE2EError("TEST_E2E_WORKER_DOCUMENTS_RESOURCES_INVALID")
    limits = resources.get("limits")
    if not isinstance(limits, Mapping):
        raise TestE2EError("TEST_E2E_WORKER_DOCUMENTS_RESOURCES_INVALID")
    if limits.get("memory") != str(8 * 1024**3) or limits.get("cpus") != 4:
        raise TestE2EError("TEST_E2E_WORKER_DOCUMENTS_RESOURCES_INVALID")
    healthcheck = worker.get("healthcheck")
    if not isinstance(healthcheck, Mapping) or healthcheck.get("timeout") != "30s":
        raise TestE2EError("TEST_E2E_WORKER_DOCUMENTS_HEALTHCHECK_INVALID")


def _verify_runtime_excludes_non_test_credentials(
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
            raise TestE2EError("TEST_E2E_COMPOSE_PS_INVALID")
        name = payload.get("Name")
        if not isinstance(name, str) or name == "":
            raise TestE2EError("TEST_E2E_CONTAINER_NAME_INVALID")
        container_names.append(name)
    if len(container_names) != 17:
        raise TestE2EError("TEST_E2E_CONTAINER_COUNT_INVALID")
    docker_executable = _docker_executable()
    inspected = subprocess.run(
        (docker_executable, "inspect", *container_names),
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if inspected.returncode != 0:
        raise TestE2EError("TEST_E2E_CONTAINER_INSPECTION_FAILED")
    _reject_non_test_paths(inspected.stdout)


def _reject_non_test_paths(serialized: str) -> None:
    if not isinstance(serialized, str):
        raise ValueError("TEST_E2E_SERIALIZED_RUNTIME_INVALID")
    normalized = serialized.replace("\\\\", "/").replace("\\", "/").lower()
    forbidden = (
        "config/secrets/development",
        "config/secrets/production",
        "config/environments/development.yaml",
        "config/environments/production.yaml",
        "data/environments/development",
        "data/environments/production",
    )
    collision = next((path for path in forbidden if path in normalized), None)
    if collision is not None:
        raise TestE2EError(f"TEST_E2E_NON_TEST_RESOURCE_VISIBLE: {collision}")


def _foreign_volume_sentinels(*, repository_root: Path) -> tuple[str, ...]:
    docker_executable = _docker_executable()
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
        raise TestE2EError("TEST_E2E_VOLUME_LIST_FAILED")
    prefixes = ("ostrading-development-", "ostrading-production-")
    names = tuple(
        sorted(
            name
            for line in listed.stdout.splitlines()
            if (name := line.strip()).startswith(prefixes)
        )
    )
    for prefix in prefixes:
        if not any(name.startswith(prefix) for name in names):
            raise TestE2EError(f"TEST_E2E_FOREIGN_SENTINEL_MISSING: {prefix}")
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
        raise TestE2EError("TEST_E2E_FOREIGN_SENTINEL_INSPECTION_FAILED")
    sentinels = tuple(
        sorted(line.strip() for line in inspected.stdout.splitlines() if line.strip())
    )
    if len(sentinels) != len(names):
        raise TestE2EError("TEST_E2E_FOREIGN_SENTINEL_INSPECTION_INCOMPLETE")
    return sentinels


def _verify_test_resources_removed(*, repository_root: Path) -> None:
    docker_executable = _docker_executable()
    commands = (
        ("ps", "--all", "--format", "{{.Names}}"),
        ("volume", "ls", "--format", "{{.Name}}"),
        ("network", "ls", "--format", "{{.Name}}"),
    )
    remaining: list[str] = []
    for arguments in commands:
        result = subprocess.run(
            (docker_executable, *arguments),
            cwd=repository_root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise TestE2EError("TEST_E2E_RESOURCE_LIST_FAILED")
        remaining.extend(
            name
            for line in result.stdout.splitlines()
            if (name := line.strip()).startswith("ostrading-test-")
        )
    if remaining:
        raise TestE2EError(
            "TEST_E2E_RESOURCES_NOT_REMOVED: " + ",".join(sorted(remaining))
        )


def _require_test_configuration(configuration: ApplicationConfiguration) -> None:
    if not isinstance(configuration, ApplicationConfiguration):
        raise ValueError("TEST_E2E_CONFIGURATION_INVALID")
    if (
        configuration.application.environment != _ENVIRONMENT
        or configuration.application.deployment_id != _DEPLOYMENT_ID
    ):
        raise ValueError("CONFIG_ENVIRONMENT_MISMATCH: preuve test")
    if configuration.services.llm_gateway.spark_endpoint_url != "http://192.168.1.120:8000/v1":
        raise ValueError("TEST_E2E_SPARK_ENDPOINT_INVALID")
    if configuration.quality_gates.llm.real_path_required is not True:
        raise ValueError("TEST_E2E_REAL_PATH_REQUIRED")
    if configuration.quality_gates.llm.fallback_model_allowed is not False:
        raise ValueError("TEST_E2E_LLM_FALLBACK_FORBIDDEN")


def _require_repository_root(value: Path) -> Path:
    if not isinstance(value, Path):
        raise ValueError("TEST_E2E_REPOSITORY_ROOT_INVALID")
    root = value.resolve()
    if not (root / "pyproject.toml").is_file():
        raise ValueError("TEST_E2E_REPOSITORY_ROOT_INVALID")
    return root


def _docker_executable() -> str:
    executable = shutil.which("docker")
    if executable is None:
        raise TestE2EError("TEST_E2E_DOCKER_UNAVAILABLE")
    return executable


def _error_code(error: Exception) -> str:
    code = str(error).split(":", 1)[0].strip()
    if code == "":
        raise ValueError("TEST_E2E_ERROR_CODE_INVALID")
    return code


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _require_utc(value: str) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("TEST_E2E_UTC_INVALID")
    datetime.fromisoformat(value.removesuffix("Z") + "+00:00")


__all__ = [
    "TestE2EError",
    "TestE2EReport",
    "TestE2ERunReport",
    "TestEnvironmentCycle",
    "run_test_environment_e2e",
]
