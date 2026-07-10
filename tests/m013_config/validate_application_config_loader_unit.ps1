$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
from __future__ import annotations

import copy
import inspect
from pathlib import Path
import sys
import tempfile

import yaml

sys.path.insert(0, sys.argv[1])

import app.platform.configuration as configuration_module
from app.platform.configuration import (
    ApplicationConfigurationError,
    load_application_configuration,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Obtenu: {actual!r}. Attendu: {expected!r}.")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_raises_code(expected_code, action):
    try:
        action()
    except ApplicationConfigurationError as exc:
        if exc.code != expected_code:
            raise AssertionError(
                f"Code d'erreur inattendu: {exc.code}. Attendu: {expected_code}. Message: {exc}"
            )
        if expected_code not in str(exc):
            raise AssertionError(f"Le message d'erreur doit contenir {expected_code}: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_code}")


def write_yaml(path, payload, *, sort_keys=False):
    path.write_text(
        yaml.safe_dump(payload, sort_keys=sort_keys, allow_unicode=True),
        encoding="utf-8",
    )
    return path


repo_root = Path(sys.argv[1])
example_path = repo_root / "config" / "application.example.yaml"
example_payload = yaml.safe_load(example_path.read_text(encoding="utf-8-sig"))

signature = inspect.signature(load_application_configuration)
for parameter_name in ("config_path", "environment_snapshot"):
    parameter = signature.parameters[parameter_name]
    if parameter.default is not inspect.Parameter.empty:
        raise AssertionError(f"Valeur par défaut interdite pour {parameter_name}.")

source = inspect.getsource(configuration_module)
if "os.environ" in source or "getenv(" in source:
    raise AssertionError("Le chargeur ne doit pas lire directement l'environnement système.")

validated_configuration = load_application_configuration(
    config_path=example_path,
    environment_snapshot={},
)

# Parse YAML: les value objects exposent les valeurs de configuration typées.
assert_equal(validated_configuration.deployment.topology, "two_host_local", "Topologie non chargée.")
assert_equal(validated_configuration.services.api.port, 8080, "Port API non chargé comme entier.")
assert_equal(validated_configuration.services.workers.concurrency, 2, "Concurrence workers non chargée.")
assert_equal(
    validated_configuration.security.secrets.postgres_password_path,
    "config/secrets/local/postgres_password",
    "Chemin de secret PostgreSQL non chargé.",
)
assert_equal(validated_configuration.runtime.resource_limits.cpu_count, 8, "Limite CPU non chargée.")

with tempfile.TemporaryDirectory(prefix="ost_m013_config_loader_unit_") as temporary_directory_name:
    temporary_directory = Path(temporary_directory_name)

    sorted_yaml_path = write_yaml(
        temporary_directory / "application_sorted.yaml",
        copy.deepcopy(example_payload),
        sort_keys=True,
    )
    unsorted_yaml_path = write_yaml(
        temporary_directory / "application_unsorted.yaml",
        copy.deepcopy(example_payload),
        sort_keys=False,
    )
    assert_equal(
        load_application_configuration(config_path=sorted_yaml_path, environment_snapshot={}).configuration_hash,
        load_application_configuration(config_path=unsorted_yaml_path, environment_snapshot={}).configuration_hash,
        "Le hash doit dépendre du contenu validé et non de l'ordre YAML.",
    )

    invalid_yaml_path = temporary_directory / "yaml_invalide.yaml"
    invalid_yaml_path.write_text("services: [", encoding="utf-8")
    assert_raises_code(
        "CONFIG_SCHEMA_INVALID",
        lambda: load_application_configuration(config_path=invalid_yaml_path, environment_snapshot={}),
    )

    for mutation_name, mutate_payload in (
        ("port_chaine", lambda payload: payload["services"]["api"].__setitem__("port", "8080")),
        ("concurrence_zero", lambda payload: payload["services"]["workers"].__setitem__("concurrency", 0)),
        ("exposition_booleen_chaine", lambda payload: payload["security"].__setitem__("allow_public_bind", "false")),
    ):
        invalid_type_payload = copy.deepcopy(example_payload)
        mutate_payload(invalid_type_payload)
        invalid_type_path = write_yaml(temporary_directory / f"{mutation_name}.yaml", invalid_type_payload)
        assert_raises_code(
            "CONFIG_SCHEMA_INVALID",
            lambda path=invalid_type_path: load_application_configuration(
                config_path=path,
                environment_snapshot={},
            ),
        )

    unknown_root_payload = copy.deepcopy(example_payload)
    unknown_root_payload["environment"] = {"DATABASE_URL": "postgresql://interdit"}
    unknown_root_path = write_yaml(temporary_directory / "section_inconnue.yaml", unknown_root_payload)
    assert_raises_code(
        "CONFIG_SCHEMA_INVALID",
        lambda: load_application_configuration(config_path=unknown_root_path, environment_snapshot={}),
    )

    unknown_service_payload = copy.deepcopy(example_payload)
    unknown_service_payload["services"]["redis"] = {"url": "redis://redis:6379"}
    unknown_service_path = write_yaml(temporary_directory / "service_inconnu.yaml", unknown_service_payload)
    assert_raises_code(
        "CONFIG_SCHEMA_INVALID",
        lambda: load_application_configuration(config_path=unknown_service_path, environment_snapshot={}),
    )

    secret_inline_payload = copy.deepcopy(example_payload)
    secret_inline_payload["security"]["secrets"]["password"] = "secret-en-clair"
    secret_inline_path = write_yaml(temporary_directory / "secret_inline.yaml", secret_inline_payload)
    assert_raises_code(
        "CONFIG_SECRET_INLINE_REJECTED",
        lambda: load_application_configuration(config_path=secret_inline_path, environment_snapshot={}),
    )

    blank_payload = copy.deepcopy(example_payload)
    blank_payload["services"]["postgres"]["url"] = "   "
    blank_path = write_yaml(temporary_directory / "valeur_blanche.yaml", blank_payload)
    assert_raises_code(
        "CONFIG_KEY_EMPTY",
        lambda: load_application_configuration(config_path=blank_path, environment_snapshot={}),
    )

    required_missing_payload = copy.deepcopy(example_payload)
    del required_missing_payload["deployment"]["hosts"]["spark_inference"]["allowed_client_cidrs"]
    required_missing_path = write_yaml(temporary_directory / "cle_absente.yaml", required_missing_payload)
    assert_raises_code(
        "CONFIG_KEY_MISSING",
        lambda: load_application_configuration(config_path=required_missing_path, environment_snapshot={}),
    )

    assert_raises_code(
        "CONFIG_FILE_REQUIRED",
        lambda: load_application_configuration(config_path=None, environment_snapshot={}),
    )

    assert_raises_code(
        "CONFIG_FILE_UNREADABLE",
        lambda: load_application_configuration(config_path=temporary_directory / "absent.yaml", environment_snapshot={}),
    )

historical_environment_names = (
    "GEMMA_BASE_URL",
    "GEMMA_MODEL",
    "GEMMA_MODEL_REVISION",
    "GEMMA_RUNTIME_VERSION",
    "GEMMA_EXTRA_LEGACY",
    "DATABASE_URL",
    "QDRANT_URL",
    "LLM_GATEWAY_URL",
    "API_PORT",
    "LLM_GATEWAY_PORT",
    "SPARK_ALLOWED_CLIENT_CIDRS",
    "SERVICES_POSTGRES_URL",
)
for environment_name in historical_environment_names:
    assert_raises_code(
        "CONFIG_ENV_INPUT_REJECTED",
        lambda name=environment_name: load_application_configuration(
            config_path=example_path,
            environment_snapshot={name: "valeur-env-interdite"},
        ),
    )

print("Tests unitaires du chargeur de configuration applicative: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_config_loader_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $env:PYTHONIOENCODING = "utf-8"
    $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

if ($LASTEXITCODE -ne 0) {
    throw ($output -join "`n")
}

Write-Host "Tests unitaires du chargeur de configuration applicative: OK"
