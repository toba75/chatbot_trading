"""Gate fail-closed des preuves et de l'étanchéité M13-environments."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Final

from app.platform.configuration import load_application_configuration
from app.platform.environment_resources import validate_environment_resource_matrix
from ost_gate.manifest import load_manifest


ENVIRONMENTS: Final = ("development", "test", "production")
LIVE_QUALIFICATION_ENVIRONMENTS: Final = ("test",)
CLOSURE_STATUS: Final = "SUBMILESTONE_GREEN_M013_OPEN"
EXPECTED_LIVE_WORKER_IDENTITY_COUNT: Final = 4
EXPECTED_LIVE_CONTAINER_COUNT: Final = 14
EXPECTED_QUALIFICATION_ROUTES: Final = (
    "NATIVE_STANDARD",
    "MIXED_PAGEWISE",
    "PREPROCESS_GRANITE",
    "TARGETED_ENRICHMENT",
    "SKIP_EMPTY",
)

_DEPLOYMENTS: Final = {
    "development": "ostrading-development-local",
    "test": "ostrading-test-ci",
    "production": "ostrading-production-primary",
}
_EXPECTED_PROBES: Final = {
    "development": ("test:ABSENT", "production:ABSENT"),
    "production": ("development:ABSENT", "test:ABSENT"),
}
_EXPECTED_PORTS: Final = {
    "development": "18443",
    "test": "19443",
    "production": "20443",
}
_EXPECTED_TRACEABILITY_IDS: Final = tuple(
    f"REQ-M013-ENV-{number:03d}" for number in range(1, 13)
)
_ADR_046: Final = "docs/adr/ADR-046-profils-locaux-etanches-sur-autorite-docker-explicite.md"
_ADR_047: Final = "docs/adr/ADR-047-archive-chiffree-verifiee-avant-preuve-restauration.md"
_ADR_048: Final = "docs/adr/ADR-048-progression-et-parallelisme-dans-profils-explicites.md"
_ADR_050: Final = "docs/adr/ADR-050-separer-qualification-fonctionnelle-et-isolation.md"
_EXPECTED_TRACEABILITY_ADRS: Final = {
    "REQ-M013-ENV-001": (_ADR_046,),
    "REQ-M013-ENV-002": (_ADR_046,),
    "REQ-M013-ENV-003": (_ADR_046, _ADR_050),
    "REQ-M013-ENV-004": (_ADR_046,),
    "REQ-M013-ENV-005": (_ADR_046,),
    "REQ-M013-ENV-006": (_ADR_046,),
    "REQ-M013-ENV-007": (_ADR_046, _ADR_048),
    "REQ-M013-ENV-008": (_ADR_046, _ADR_047),
    "REQ-M013-ENV-009": (_ADR_046, _ADR_050),
    "REQ-M013-ENV-010": (_ADR_046, _ADR_048, _ADR_050),
    "REQ-M013-ENV-011": (_ADR_046, _ADR_050),
    "REQ-M013-ENV-012": (_ADR_046, _ADR_047, _ADR_048, _ADR_050),
}
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_REVISION: Final = re.compile(r"^[0-9a-f]{7,64}$")
_SENSITIVE_KEYS: Final = frozenset(
    {
        "api_key",
        "api_token",
        "authorization",
        "bearer_token",
        "password",
        "private_key",
        "secret",
    }
)
_SENSITIVE_TEXT_MARKERS: Final = (
    "authorization: bearer ",
    "-----begin private key-----",
    "-----begin rsa private key-----",
)
_WORKER_PREFIX: Final = "worker-"


class EnvironmentGovernanceError(ValueError):
    """Erreur stable qui interdit la clôture du sous-milestone."""


@dataclass(frozen=True, slots=True)
class EnvironmentExecutionEvidence:
    environments: tuple[str, ...]
    execution_count: int
    worker_identity_count: int


@dataclass(frozen=True, slots=True)
class RepositoryEnvironmentEvidence:
    environments: tuple[str, ...]
    worker_names: tuple[str, ...]
    worker_replica_count: int
    matrix_cell_count: int
    mutable_resource_count: int
    execution_count: int
    closure_status: str
    source: str


@dataclass(frozen=True, slots=True)
class _ComposeInventory:
    project: str
    networks: tuple[str, ...]
    volumes: tuple[str, ...]
    secrets: tuple[str, ...]


def build_isolation_access_matrix(
    environments: Sequence[str],
) -> dict[str, dict[str, str]]:
    """Construit les neuf décisions d'accès, sans profil implicite."""

    if isinstance(environments, (str, bytes)) or tuple(environments) != ENVIRONMENTS:
        raise EnvironmentGovernanceError("ISOLATION_MATRIX_ENVIRONMENTS_INVALID")
    return {
        source: {
            target: "OWNED" if source == target else "FORBIDDEN"
            for target in ENVIRONMENTS
        }
        for source in ENVIRONMENTS
    }


def validate_closure_status(status: object) -> str:
    """Refuse qu'un sous-milestone déclare M-013 globalement clos."""

    if status != CLOSURE_STATUS:
        raise EnvironmentGovernanceError("M013_GLOBAL_CLOSURE_FORBIDDEN")
    return CLOSURE_STATUS


def assert_no_sensitive_data(value: object) -> None:
    """Refuse les clés et marqueurs qui matérialiseraient un secret."""

    def visit(current: object) -> None:
        if isinstance(current, Mapping):
            for key, nested in current.items():
                if not isinstance(key, str):
                    raise EnvironmentGovernanceError("SENSITIVE_EVIDENCE_REJECTED")
                normalized = key.casefold()
                if normalized in _SENSITIVE_KEYS or any(
                    normalized.endswith(f"_{suffix}") for suffix in _SENSITIVE_KEYS
                ):
                    raise EnvironmentGovernanceError("SENSITIVE_EVIDENCE_REJECTED")
                visit(nested)
            return
        if isinstance(current, list):
            for nested in current:
                visit(nested)
            return
        if isinstance(current, str):
            folded = current.casefold()
            if any(marker in folded for marker in _SENSITIVE_TEXT_MARKERS):
                raise EnvironmentGovernanceError("SENSITIVE_EVIDENCE_REJECTED")

    visit(value)


def validate_execution_evidence(
    reports: Mapping[str, object],
) -> EnvironmentExecutionEvidence:
    """Valide la preuve d'isolation à deux cycles du seul profil test."""

    if not isinstance(reports, Mapping):
        raise EnvironmentGovernanceError("LIVE_EVIDENCE_DOCUMENT_INVALID")
    missing = [
        environment
        for environment in LIVE_QUALIFICATION_ENVIRONMENTS
        if environment not in reports
    ]
    if missing:
        raise EnvironmentGovernanceError(f"LIVE_EVIDENCE_MISSING:{missing[0]}")
    if frozenset(reports) != frozenset(LIVE_QUALIFICATION_ENVIRONMENTS):
        raise EnvironmentGovernanceError("LIVE_EVIDENCE_ENVIRONMENTS_INVALID")
    assert_no_sensitive_data(reports)

    environment = "test"
    report = _require_mapping(reports[environment], "LIVE_EVIDENCE_REPORT_INVALID")
    _validate_report_header(report, environment=environment)
    if report.get("qualification_mode") != "ISOLATION":
        raise EnvironmentGovernanceError("LIVE_EVIDENCE_QUALIFICATION_MODE_INVALID")
    _required_hash(report, "configuration_hash", "LIVE_EVIDENCE_HASH_INVALID")
    _required_hash(report, "source_pdf_sha256", "LIVE_EVIDENCE_HASH_INVALID")
    _require_true(report, "foreign_volume_sentinels_preserved")
    _require_true(report, "non_test_credentials_inaccessible")
    _require_true(report, "test_resources_removed")
    runs = report.get("runs")
    if not isinstance(runs, list) or len(runs) != 2:
        raise EnvironmentGovernanceError("LIVE_EVIDENCE_TEST_RUNS_INVALID")
    if tuple(run.get("run_number") for run in runs if isinstance(run, Mapping)) != (1, 2):
        raise EnvironmentGovernanceError("LIVE_EVIDENCE_TEST_RUNS_INVALID")
    flattened = [
        (environment, _require_mapping(run, "LIVE_EVIDENCE_RUN_INVALID"))
        for run in runs
    ]

    identifier_fields = (
        "document_id",
        "canonical_version_id",
        "projection_id",
        "answer_id",
        "spark_raw_response_id",
        "pdf_sha256",
    )
    identifiers: dict[str, str] = {}
    worker_identity_count = 0
    for environment, execution in flattened:
        if execution.get("progress_phases") != ["SUCCEEDED", "SUCCEEDED", "SUCCEEDED"]:
            raise EnvironmentGovernanceError("LIVE_EVIDENCE_PROGRESS_INVALID")
        if tuple(execution.get("qualification_routes", ())) != EXPECTED_QUALIFICATION_ROUTES:
            raise EnvironmentGovernanceError("LIVE_EVIDENCE_QUALIFICATION_ROUTES_INVALID")
        if execution.get("worker_identity_count") != EXPECTED_LIVE_WORKER_IDENTITY_COUNT:
            raise EnvironmentGovernanceError("LIVE_EVIDENCE_WORKERS_INCOMPLETE")
        if execution.get("container_count") != EXPECTED_LIVE_CONTAINER_COUNT:
            raise EnvironmentGovernanceError("LIVE_EVIDENCE_CONTAINERS_INCOMPLETE")
        _require_true(execution, "https_ca_verified")
        _required_hash(execution, "caddy_ca_sha256", "LIVE_EVIDENCE_CADDY_CA_INVALID")
        if execution.get("environment_job_count") != 3:
            raise EnvironmentGovernanceError("LIVE_EVIDENCE_JOBS_INCOMPLETE")
        worker_identity_count += EXPECTED_LIVE_WORKER_IDENTITY_COUNT
        citation = _required_text(execution, "citation_url", "LIVE_EVIDENCE_CITATION_INVALID")
        if not citation.startswith(f"https://localhost:{_EXPECTED_PORTS[environment]}/"):
            raise EnvironmentGovernanceError("LIVE_EVIDENCE_CITATION_INVALID")
        for field in identifier_fields:
            value = (
                _required_hash(execution, field, "LIVE_EVIDENCE_HASH_INVALID")
                if field == "pdf_sha256"
                else _required_text(execution, field, "LIVE_EVIDENCE_IDENTIFIER_INVALID")
            )
            previous = identifiers.get(value)
            if previous is not None:
                raise EnvironmentGovernanceError(
                    f"EVIDENCE_ID_COLLISION:{previous}:{environment}:{field}"
                )
            identifiers[value] = environment

    return EnvironmentExecutionEvidence(
        environments=LIVE_QUALIFICATION_ENVIRONMENTS,
        execution_count=len(flattened),
        worker_identity_count=worker_identity_count,
    )


def validate_repository_environment_governance(
    *,
    repository_root: Path,
    require_live_sources: bool,
) -> RepositoryEnvironmentEvidence:
    """Relie configurations, preuves, matrice, runbook et traçabilité."""

    if not isinstance(repository_root, Path) or not repository_root.is_dir():
        raise EnvironmentGovernanceError("REPOSITORY_ROOT_INVALID")
    if not isinstance(require_live_sources, bool):
        raise EnvironmentGovernanceError("LIVE_SOURCE_POLICY_INVALID")
    root = repository_root.resolve()

    evidence_document = _load_json(
        root / "docs" / "governance" / "m013_environments_execution_evidence.json"
    )
    _require_exact_keys(
        evidence_document,
        {
            "schema_version",
            "evidence_kind",
            "evidence_status",
            "closure_status",
            "current_runtime",
            "normalizations",
            "source_reports",
            "historical_reports",
        },
        "VERSIONED_EVIDENCE_SCHEMA_INVALID",
    )
    if evidence_document["schema_version"] != 2:
        raise EnvironmentGovernanceError("VERSIONED_EVIDENCE_SCHEMA_INVALID")
    if evidence_document["evidence_kind"] != "HISTORICAL_STACK_EXECUTION":
        raise EnvironmentGovernanceError("VERSIONED_EVIDENCE_KIND_INVALID")
    if evidence_document["evidence_status"] != "STALE":
        raise EnvironmentGovernanceError("VERSIONED_EVIDENCE_STATUS_INVALID")
    if evidence_document["current_runtime"] != {
        "worker_identity_count": EXPECTED_LIVE_WORKER_IDENTITY_COUNT,
        "container_count": EXPECTED_LIVE_CONTAINER_COUNT,
    }:
        raise EnvironmentGovernanceError("VERSIONED_EVIDENCE_RUNTIME_INVALID")
    if evidence_document["normalizations"] != [
        "report_path:repository-relative",
        "runs.pre_teardown_report_path:repository-relative",
    ]:
        raise EnvironmentGovernanceError("VERSIONED_EVIDENCE_NORMALIZATION_INVALID")
    closure_status = validate_closure_status(evidence_document["closure_status"])
    _validate_source_report_references(root, evidence_document["source_reports"])

    historical_reports = _require_mapping(
        evidence_document["historical_reports"],
        "VERSIONED_EVIDENCE_REPORTS_INVALID",
    )
    if frozenset(historical_reports) != frozenset(ENVIRONMENTS):
        raise EnvironmentGovernanceError("VERSIONED_EVIDENCE_REPORTS_INVALID")
    assert_no_sensitive_data(historical_reports)

    if require_live_sources:
        reports = _load_latest_live_reports(root)
        source = "latest-live-reports"
        execution_evidence = validate_execution_evidence(reports)
        validate_evidence_revisions(
            repository_root=root,
            reports=reports,
            require_common_revision=True,
        )
    else:
        execution_evidence = EnvironmentExecutionEvidence(
            environments=ENVIRONMENTS,
            execution_count=0,
            worker_identity_count=0,
        )
        source = "offline-awaiting-live-evidence"

    configurations = {
        environment: load_application_configuration(
            config_path=root / "config" / "environments" / f"{environment}.yaml",
            environment_snapshot={},
        )
        for environment in ENVIRONMENTS
    }
    resource_matrix = validate_environment_resource_matrix(
        configurations,
        repository_root=root,
    )
    base_workers = _parse_worker_inventory(root / "deploy" / "environments" / "compose.base.yaml")
    compose_inventories = {
        environment: _parse_compose_inventory(
            root / "deploy" / "environments" / f"{environment}.compose.yaml",
            environment=environment,
        )
        for environment in ENVIRONMENTS
    }
    matrix_document = _load_json(
        root / "docs" / "governance" / "m013_environments_isolation_matrix.json"
    )
    mutable_resource_count = _validate_isolation_document(
        matrix_document=matrix_document,
        resource_matrix=resource_matrix.coordinates,
        compose_inventories=compose_inventories,
        workers=base_workers,
    )
    _validate_traceability_document(root)
    _validate_documentation(root)
    _validate_gate_enrollment(root)
    _validate_tracked_secrets(root)

    return RepositoryEnvironmentEvidence(
        environments=ENVIRONMENTS,
        worker_names=tuple(sorted(base_workers)),
        worker_replica_count=sum(base_workers.values()),
        matrix_cell_count=9,
        mutable_resource_count=mutable_resource_count,
        execution_count=execution_evidence.execution_count,
        closure_status=closure_status,
        source=source,
    )


def assert_no_active_environment_entrypoint_contradictions(
    documents: Mapping[str, str],
) -> None:
    """Refuse les anciens points d'entrée dans les prescriptions encore actives."""

    if not isinstance(documents, Mapping) or not documents:
        raise EnvironmentGovernanceError("ACTIVE_ENVIRONMENT_DOCUMENTS_INVALID")
    forbidden_runbook_markers = (
        "uv run ui",
        "config/application.yaml",
        "config/secrets/local",
        "deploy/local-compose",
    )
    for name, content in documents.items():
        if (
            not isinstance(name, str)
            or name.strip() == ""
            or not isinstance(content, str)
            or content.strip() == ""
        ):
            raise EnvironmentGovernanceError("ACTIVE_ENVIRONMENT_DOCUMENTS_INVALID")
        normalized_name = name.replace("\\", "/")
        if "/runbooks/" in f"/{normalized_name}":
            if any(marker in content for marker in forbidden_runbook_markers):
                raise EnvironmentGovernanceError(
                    f"ACTIVE_ENVIRONMENT_ENTRYPOINT_CONTRADICTION:{normalized_name}"
                )
            continue
        if "/adr/ADR-" not in f"/{normalized_name}":
            continue
        status_match = re.search(r"(?m)^\*\*Statut :\*\* ([^\r\n]+)$", content)
        if status_match is None or status_match.group(1) != "Acceptée":
            continue
        replacement_match = re.search(
            r"(?m)^\*\*Remplacée par :\*\* ([^\r\n]+)$",
            content,
        )
        has_partial_replacement = (
            replacement_match is not None
            and replacement_match.group(1) != "Aucune"
        )
        normative_old_entrypoint = re.search(
            r"(?i)`uv run ui`[^\r\n]{0,80}\*\*DOIT\*\*",
            content,
        )
        if normative_old_entrypoint is not None and not has_partial_replacement:
            raise EnvironmentGovernanceError(
                f"ACTIVE_ENVIRONMENT_ENTRYPOINT_CONTRADICTION:{normalized_name}"
            )


def validate_evidence_revisions(
    *,
    repository_root: Path,
    reports: Mapping[str, object],
    require_common_revision: bool,
) -> None:
    """Lie chaque preuve à un commit qualifiable et à son runner versionné."""

    if not isinstance(require_common_revision, bool):
        raise EnvironmentGovernanceError("LIVE_EVIDENCE_REVISION_POLICY_INVALID")
    root = repository_root.resolve()
    current_revision = _git_output(root, ("rev-parse", "HEAD"), "LIVE_EVIDENCE_REVISION_INVALID")
    revisions: list[str] = []
    for environment in LIVE_QUALIFICATION_ENVIRONMENTS:
        report = _require_mapping(
            reports.get(environment),
            f"LIVE_EVIDENCE_MISSING:{environment}",
        )
        revision = _required_text(
            report,
            "image_revision",
            "LIVE_EVIDENCE_REVISION_INVALID",
        )
        _git_success(
            root,
            ("cat-file", "-e", f"{revision}^{{commit}}"),
            "LIVE_EVIDENCE_REVISION_UNKNOWN",
        )
        _git_success(
            root,
            ("merge-base", "--is-ancestor", revision, current_revision),
            "LIVE_EVIDENCE_REVISION_INCOMPATIBLE",
        )
        runner = (
            "gate_tests/ported/tests/m013_environments/"
            f"validate_{environment}_real_e2e_acceptance.py"
        )
        _git_success(
            root,
            ("cat-file", "-e", f"{revision}:{runner}"),
            "LIVE_EVIDENCE_RUNNER_MISSING",
        )
        revisions.append(revision)
    for left, right in zip(revisions, revisions[1:]):
        left_precedes = _git_completed(
            root,
            ("merge-base", "--is-ancestor", left, right),
        ).returncode == 0
        right_precedes = _git_completed(
            root,
            ("merge-base", "--is-ancestor", right, left),
        ).returncode == 0
        if not left_precedes and not right_precedes:
            raise EnvironmentGovernanceError("LIVE_EVIDENCE_REVISIONS_DIVERGED")
    if require_common_revision:
        if len(set(revisions)) != 1 or revisions[0] != current_revision:
            raise EnvironmentGovernanceError("LIVE_EVIDENCE_COMMON_REVISION_REQUIRED")
        for runner in ("app/platform/test_e2e.py",):
            _git_success(
                root,
                ("cat-file", "-e", f"{current_revision}:{runner}"),
                "LIVE_EVIDENCE_RUNNER_MISSING",
            )


def _git_completed(root: Path, arguments: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("git", *arguments),
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=False,
    )


def _git_success(root: Path, arguments: tuple[str, ...], code: str) -> None:
    if _git_completed(root, arguments).returncode != 0:
        raise EnvironmentGovernanceError(code)


def _git_output(root: Path, arguments: tuple[str, ...], code: str) -> str:
    completed = _git_completed(root, arguments)
    output = completed.stdout.strip()
    if completed.returncode != 0 or output == "":
        raise EnvironmentGovernanceError(code)
    return output


def _validate_report_header(report: Mapping[str, object], *, environment: str) -> None:
    if report.get("environment") != environment:
        raise EnvironmentGovernanceError("LIVE_EVIDENCE_ENVIRONMENT_MISMATCH")
    if report.get("deployment_id") != _DEPLOYMENTS[environment]:
        raise EnvironmentGovernanceError("LIVE_EVIDENCE_DEPLOYMENT_MISMATCH")
    _required_text(report, "completed_at", "LIVE_EVIDENCE_COMPLETION_INVALID")
    revision = _required_text(report, "image_revision", "LIVE_EVIDENCE_REVISION_INVALID")
    if _REVISION.fullmatch(revision) is None:
        raise EnvironmentGovernanceError("LIVE_EVIDENCE_REVISION_INVALID")
    if report.get("source_pdf_path") != (
        "data/corpus/ostrading-environment-qualification-5-pages.pdf"
    ):
        raise EnvironmentGovernanceError("LIVE_EVIDENCE_SOURCE_PDF_INVALID")


def _validate_source_report_references(root: Path, value: object) -> None:
    references = _require_mapping(value, "SOURCE_REPORT_REFERENCES_INVALID")
    if frozenset(references) != frozenset(ENVIRONMENTS):
        raise EnvironmentGovernanceError("SOURCE_REPORT_REFERENCES_INVALID")
    for environment in ENVIRONMENTS:
        reference = _require_mapping(
            references[environment], "SOURCE_REPORT_REFERENCE_INVALID"
        )
        _require_exact_keys(
            reference,
            {"path", "sha256"},
            "SOURCE_REPORT_REFERENCE_INVALID",
        )
        relative_path = Path(
            _required_text(reference, "path", "SOURCE_REPORT_REFERENCE_INVALID")
        )
        expected_parent = Path("data") / "environments" / environment / "reports"
        if relative_path.is_absolute() or relative_path.parent != expected_parent:
            raise EnvironmentGovernanceError("SOURCE_REPORT_REFERENCE_INVALID")
        expected_sha256 = _required_hash(
            reference, "sha256", "SOURCE_REPORT_REFERENCE_INVALID"
        )
        source_path = root / relative_path
        if source_path.is_file() and _sha256(source_path) != expected_sha256:
            raise EnvironmentGovernanceError("SOURCE_REPORT_HASH_MISMATCH")


def _load_latest_live_reports(root: Path) -> dict[str, object]:
    patterns = {"test": "test-isolation-e2e-20*.json"}
    reports: dict[str, object] = {}
    for environment in LIVE_QUALIFICATION_ENVIRONMENTS:
        report_root = root / "data" / "environments" / environment / "reports"
        candidates = tuple(sorted(report_root.glob(patterns[environment])))
        if not candidates:
            raise EnvironmentGovernanceError(f"LIVE_EVIDENCE_MISSING:{environment}")
        reports[environment] = _load_json(candidates[-1])
    return reports


def _parse_worker_inventory(path: Path) -> dict[str, int]:
    document = _read_text(path, "COMPOSE_BASE_REQUIRED")
    matches = list(re.finditer(r"(?m)^  (worker-[a-z0-9-]+):\s*$", document))
    if not matches:
        raise EnvironmentGovernanceError("WORKER_INVENTORY_MISSING")
    workers: dict[str, int] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(document)
        block = document[match.end() : end]
        replica_match = re.search(r"(?m)^      replicas: ([1-9][0-9]*)\s*$", block)
        if replica_match is None:
            raise EnvironmentGovernanceError("WORKER_REPLICA_COUNT_MISSING")
        workers[match.group(1)] = int(replica_match.group(1))
    if len(workers) != len(matches):
        raise EnvironmentGovernanceError("WORKER_INVENTORY_DUPLICATE")
    return workers


def _parse_compose_inventory(path: Path, *, environment: str) -> _ComposeInventory:
    document = _read_text(path, "COMPOSE_PROFILE_REQUIRED")
    project_match = re.search(r"(?m)^name: ([a-z0-9-]+)\s*$", document)
    if project_match is None:
        raise EnvironmentGovernanceError("COMPOSE_PROJECT_IDENTITY_MISSING")
    project = project_match.group(1)
    networks = _named_compose_resources(document, section="networks")
    volumes = _named_compose_resources(document, section="volumes")
    secrets = tuple(
        match.group(1)
        for match in re.finditer(
            rf"(?m)^    file: (\.\./\.\./config/secrets/{environment}/[^\s]+)\s*$",
            _root_section(document, "secrets"),
        )
    )
    if environment not in project or not networks or not volumes or len(secrets) != 3:
        raise EnvironmentGovernanceError("COMPOSE_PROFILE_INVENTORY_INVALID")
    for coordinate in (project, *networks, *volumes, *secrets):
        if environment not in coordinate:
            raise EnvironmentGovernanceError("COMPOSE_PROFILE_IDENTITY_MISMATCH")
    return _ComposeInventory(
        project=project,
        networks=tuple(sorted(networks)),
        volumes=tuple(sorted(volumes)),
        secrets=tuple(sorted(secrets)),
    )


def _named_compose_resources(document: str, *, section: str) -> tuple[str, ...]:
    section_document = _root_section(document, section)
    names = tuple(
        match.group(1)
        for match in re.finditer(r"(?m)^    name: ([a-z0-9-]+)\s*$", section_document)
    )
    if len(names) != len(set(names)):
        raise EnvironmentGovernanceError("COMPOSE_RESOURCE_COLLISION")
    return names


def _root_section(document: str, section: str) -> str:
    match = re.search(rf"(?m)^{re.escape(section)}:\s*$", document)
    if match is None:
        raise EnvironmentGovernanceError(f"COMPOSE_SECTION_MISSING:{section}")
    following = document[match.end() :]
    next_root = re.search(r"(?m)^[a-z][a-z0-9_-]*:\s*$", following)
    return following[: next_root.start()] if next_root else following


def _validate_isolation_document(
    *,
    matrix_document: Mapping[str, object],
    resource_matrix: Mapping[str, Mapping[str, str]],
    compose_inventories: Mapping[str, _ComposeInventory],
    workers: Mapping[str, int],
) -> int:
    _require_exact_keys(
        matrix_document,
        {
            "schema_version",
            "environments",
            "access_matrix",
            "mutable_resources",
            "workers",
        },
        "ISOLATION_DOCUMENT_SCHEMA_INVALID",
    )
    if matrix_document["schema_version"] != 1:
        raise EnvironmentGovernanceError("ISOLATION_DOCUMENT_SCHEMA_INVALID")
    if matrix_document["environments"] != list(ENVIRONMENTS):
        raise EnvironmentGovernanceError("ISOLATION_DOCUMENT_ENVIRONMENTS_INVALID")
    if matrix_document["access_matrix"] != build_isolation_access_matrix(ENVIRONMENTS):
        raise EnvironmentGovernanceError("ISOLATION_DOCUMENT_ACCESS_INVALID")
    if matrix_document["workers"] != workers:
        raise EnvironmentGovernanceError("ISOLATION_DOCUMENT_WORKERS_INCOMPLETE")

    mutable = _require_mapping(
        matrix_document["mutable_resources"], "ISOLATION_DOCUMENT_RESOURCES_INVALID"
    )
    _require_exact_keys(
        mutable,
        {"configuration_coordinates", "compose_projects", "compose_networks", "compose_volumes", "compose_secrets"},
        "ISOLATION_DOCUMENT_RESOURCES_INVALID",
    )
    coordinate_names = sorted(next(iter(resource_matrix.values())))
    if mutable["configuration_coordinates"] != coordinate_names:
        raise EnvironmentGovernanceError("ISOLATION_DOCUMENT_COORDINATES_INCOMPLETE")
    expected_projects = {
        environment: compose_inventories[environment].project for environment in ENVIRONMENTS
    }
    expected_networks = {
        environment: list(compose_inventories[environment].networks)
        for environment in ENVIRONMENTS
    }
    expected_volumes = {
        environment: list(compose_inventories[environment].volumes)
        for environment in ENVIRONMENTS
    }
    expected_secrets = {
        environment: list(compose_inventories[environment].secrets)
        for environment in ENVIRONMENTS
    }
    if mutable["compose_projects"] != expected_projects:
        raise EnvironmentGovernanceError("ISOLATION_DOCUMENT_PROJECTS_INVALID")
    if mutable["compose_networks"] != expected_networks:
        raise EnvironmentGovernanceError("ISOLATION_DOCUMENT_NETWORKS_INVALID")
    if mutable["compose_volumes"] != expected_volumes:
        raise EnvironmentGovernanceError("ISOLATION_DOCUMENT_VOLUMES_INVALID")
    if mutable["compose_secrets"] != expected_secrets:
        raise EnvironmentGovernanceError("ISOLATION_DOCUMENT_SECRETS_INVALID")

    for category in (expected_projects, expected_networks, expected_volumes, expected_secrets):
        values: list[str] = []
        for environment in ENVIRONMENTS:
            current = category[environment]
            values.extend(current if isinstance(current, list) else [current])
        if len(values) != len(set(values)):
            raise EnvironmentGovernanceError("ISOLATION_DOCUMENT_COLLISION")
    return (
        len(coordinate_names)
        + 1
        + len(compose_inventories["development"].networks)
        + len(compose_inventories["development"].volumes)
        + len(compose_inventories["development"].secrets)
    )


def _validate_traceability_document(root: Path) -> None:
    document = _load_json(
        root / "docs" / "governance" / "m013_environments_traceability.json"
    )
    _require_exact_keys(
        document,
        {"schema_version", "submilestone_status", "m013_global_status", "records"},
        "TRACEABILITY_SCHEMA_INVALID",
    )
    if document["schema_version"] != 2:
        raise EnvironmentGovernanceError("TRACEABILITY_SCHEMA_INVALID")
    if document["submilestone_status"] != "AWAITING_LIVE_EVIDENCE":
        raise EnvironmentGovernanceError("TRACEABILITY_SUBMILESTONE_RED")
    if document["m013_global_status"] != "OPEN":
        raise EnvironmentGovernanceError("M013_GLOBAL_CLOSURE_FORBIDDEN")
    records = document["records"]
    if not isinstance(records, list) or tuple(
        record.get("requirement_id") for record in records if isinstance(record, Mapping)
    ) != _EXPECTED_TRACEABILITY_IDS:
        raise EnvironmentGovernanceError("TRACEABILITY_REQUIREMENTS_INCOMPLETE")
    for record in records:
        current = _require_mapping(record, "TRACEABILITY_RECORD_INVALID")
        _require_exact_keys(
            current,
            {
                "requirement_id",
                "status",
                "source_task",
                "specification",
                "adrs",
                "code",
                "tests",
                "reports",
                "runbooks",
            },
            "TRACEABILITY_RECORD_INVALID",
        )
        requirement_id = current["requirement_id"]
        expected_status = (
            "AWAITING_LIVE_EVIDENCE"
            if requirement_id in {"REQ-M013-ENV-010", "REQ-M013-ENV-012"}
            else "COVERED_OFFLINE"
        )
        if current["status"] != expected_status:
            raise EnvironmentGovernanceError("TRACEABILITY_REQUIREMENT_RED")
        adrs = current["adrs"]
        if not isinstance(adrs, list) or tuple(adrs) != _EXPECTED_TRACEABILITY_ADRS[requirement_id]:
            raise EnvironmentGovernanceError("TRACEABILITY_ADR_MISMATCH")
        for key in ("source_task", "specification"):
            _require_repository_file(root, current[key])
        for adr in adrs:
            _require_repository_file(root, adr)
        for key in ("code", "tests", "reports", "runbooks"):
            paths = current[key]
            if not isinstance(paths, list) or not paths:
                raise EnvironmentGovernanceError("TRACEABILITY_PATHS_REQUIRED")
            for path in paths:
                _require_repository_file(root, path)


def _validate_documentation(root: Path) -> None:
    runbook = _read_text(
        root / "docs" / "runbooks" / "environnements_explicites.md",
        "ENVIRONMENT_RUNBOOK_REQUIRED",
    )
    specification = _read_text(
        root / "docs" / "specs" / "m013_environments_environnements_explicites.md",
        "ENVIRONMENT_SPECIFICATION_REQUIRED",
    )
    closure = _read_text(
        root / "docs" / "governance" / "m013_environments_closure.md",
        "ENVIRONMENT_CLOSURE_REPORT_REQUIRED",
    )
    isolation = _read_text(
        root / "docs" / "governance" / "m013_environments_isolation_matrix.md",
        "ENVIRONMENT_ISOLATION_MATRIX_REQUIRED",
    )
    traceability = _read_text(
        root / "docs" / "traceability" / "matrix.md",
        "TRACEABILITY_MATRIX_REQUIRED",
    )
    legacy_compose = _read_text(
        root / "deploy/local-compose/README.md",
        "LEGACY_COMPOSE_DOCUMENTATION_REQUIRED",
    )
    required_runbook_tokens = (
        "uv run development",
        "uv run test",
        "uv run production",
        "backup-v1",
        "restore-v1",
        "--config config/environments/<profil>.yaml",
        "uv run --locked gate --scope m013_environments",
        "uv run --locked gate --scope m013_environments --live",
        "down --volumes",
        "DATASTORE_ENVIRONMENT_MISMATCH",
        "export-ca --environment $profile --output $caPath",
        "curl.exe --fail --cacert",
        "n'installe jamais cette CA",
    )
    if any(token not in runbook for token in required_runbook_tokens):
        raise EnvironmentGovernanceError("ENVIRONMENT_RUNBOOK_INCOMPLETE")
    if any(
        token not in legacy_compose
        for token in (
            "DÉPRÉCIÉ",
            "uv run development",
            "uv run test",
            "uv run production",
            "docs/runbooks/environnements_explicites.md",
        )
    ):
        raise EnvironmentGovernanceError("LEGACY_COMPOSE_DOCUMENTATION_INVALID")
    for document in (specification, closure, isolation):
        if "ADR-046" not in document or CLOSURE_STATUS not in document:
            raise EnvironmentGovernanceError("ENVIRONMENT_DOCUMENTATION_INCOMPLETE")
    if (
        "`STALE`" not in closure
        or "4 workers, 14 conteneurs" not in closure
        or "https_ca_verified=true" not in closure
    ):
        raise EnvironmentGovernanceError("ENVIRONMENT_CLOSURE_EVIDENCE_INVALID")
    active_documents = {
        path.relative_to(root).as_posix(): _read_text(
            path,
            "ACTIVE_ENVIRONMENT_DOCUMENT_REQUIRED",
        )
        for path in (
            root / "docs" / "runbooks" / "configuration_applicative.md",
            root / "docs" / "runbooks" / "api_orchestratrice.md",
            root / "docs" / "runbooks" / "environnements_explicites.md",
            root / "docs" / "governance" / "m013_documentation_index.md",
            root / "docs" / "adr" / "ADR-031-actions-ui-execution-et-progression-publique.md",
            root / "docs" / "adr" / "ADR-037-parallelisme-documentaire-projection.md",
            root / "docs" / "adr" / "ADR-048-progression-et-parallelisme-dans-profils-explicites.md",
            root / "docs" / "adr" / "index.md",
        )
    }
    assert_no_active_environment_entrypoint_contradictions(active_documents)
    if any(requirement_id not in traceability for requirement_id in _EXPECTED_TRACEABILITY_IDS):
        raise EnvironmentGovernanceError("TRACEABILITY_MATRIX_INCOMPLETE")


def _validate_gate_enrollment(root: Path) -> None:
    manifest = load_manifest(root / "gate.toml")
    expected = {
        "gate_tests/ported/tests/m013_environments/validate_development_real_e2e_acceptance.py": (False, "tests"),
        "gate_tests/ported/tests/m013_environments/validate_test_real_e2e_acceptance.py": (True, "live"),
        "gate_tests/ported/tests/m013_environments/validate_production_real_e2e_acceptance.py": (False, "tests"),
        "gate_tests/ported/tests/m013_environments/validate_environment_governance_acceptance.py": (False, "tests"),
        "gate_tests/ported/tests/m013_environments/validate_environment_governance_unit.py": (False, "tests"),
        "gate_tests/ported/tests/m013_environments/validate_environment_governance_live.py": (True, "live"),
    }
    enrolled: dict[str, object] = {}
    for node in manifest.nodes:
        relative_path = node.path.relative_to(root).as_posix()
        if relative_path in expected:
            if relative_path in enrolled:
                raise EnvironmentGovernanceError("GATE_ENROLLMENT_DUPLICATE")
            enrolled[relative_path] = node
    if frozenset(enrolled) != frozenset(expected):
        raise EnvironmentGovernanceError("GATE_ENROLLMENT_MISSING")
    for path, (expected_live, expected_phase) in expected.items():
        node = enrolled[path]
        if (
            node.scope != "m013_environments"
            or node.live is not expected_live
            or node.phase != expected_phase
        ):
            raise EnvironmentGovernanceError("GATE_ENROLLMENT_CLASSIFICATION_INVALID")
    live_node = enrolled[
        "gate_tests/ported/tests/m013_environments/validate_environment_governance_live.py"
    ]
    if frozenset(live_node.depends_on) != frozenset(
        {"test.m013-environments.validate-test-real-e2e-acceptance"}
    ):
        raise EnvironmentGovernanceError("GATE_LIVE_DEPENDENCIES_INVALID")


def _validate_tracked_secrets(root: Path) -> None:
    completed = subprocess.run(
        ("git", "ls-files", "config/secrets"),
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=False,
    )
    if completed.returncode != 0:
        raise EnvironmentGovernanceError("TRACKED_SECRET_SCAN_FAILED")
    tracked = tuple(line for line in completed.stdout.splitlines() if line)
    expected = (
        "config/secrets/development/.gitignore",
        "config/secrets/local/.gitignore",
        "config/secrets/production/.gitignore",
        "config/secrets/test/.gitignore",
    )
    if tracked != expected:
        raise EnvironmentGovernanceError("TRACKED_SECRET_REJECTED")


def _require_repository_file(root: Path, value: object) -> None:
    if not isinstance(value, str) or value.strip() != value or value == "":
        raise EnvironmentGovernanceError("TRACEABILITY_PATH_INVALID")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not (root / path).is_file():
        raise EnvironmentGovernanceError(f"TRACEABILITY_PATH_MISSING:{value}")


def _load_json(path: Path) -> Mapping[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EnvironmentGovernanceError(f"GOVERNANCE_JSON_INVALID:{path}") from exc
    return _require_mapping(value, "GOVERNANCE_JSON_INVALID")


def _read_text(path: Path, code: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EnvironmentGovernanceError(code) from exc


def _required_text(document: Mapping[str, object], key: str, code: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or value.strip() != value or value == "":
        raise EnvironmentGovernanceError(code)
    return value


def _required_hash(document: Mapping[str, object], key: str, code: str) -> str:
    value = _required_text(document, key, code)
    if _SHA256.fullmatch(value) is None:
        raise EnvironmentGovernanceError(code)
    return value


def _require_true(document: Mapping[str, object], key: str) -> None:
    if document.get(key) is not True:
        raise EnvironmentGovernanceError(f"LIVE_EVIDENCE_GUARD_INVALID:{key}")


def _require_mapping(value: object, code: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise EnvironmentGovernanceError(code)
    return value


def _require_exact_keys(
    document: Mapping[str, object], expected: set[str], code: str
) -> None:
    if frozenset(document) != frozenset(expected):
        raise EnvironmentGovernanceError(code)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "CLOSURE_STATUS",
    "ENVIRONMENTS",
    "EnvironmentExecutionEvidence",
    "EnvironmentGovernanceError",
    "RepositoryEnvironmentEvidence",
    "assert_no_sensitive_data",
    "build_isolation_access_matrix",
    "validate_closure_status",
    "validate_execution_evidence",
    "validate_evidence_revisions",
    "validate_repository_environment_governance",
]
