$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
from __future__ import annotations

import inspect
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, sys.argv[1])

import app.platform.configuration as configuration_module
from app.platform.configuration import (
    ApplicationConfigurationError,
    load_application_configuration,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Obtenu: {actual!r}. Attendu: {expected!r}.")


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


def write_configuration(path, content):
    path.write_text(content, encoding="utf-8")
    return path


def reorder_root_sections(content, ordered_names):
    blocks = {}
    current_name = None
    current_lines = []

    for line in content.strip().splitlines():
        if line != "" and not line.startswith(" ") and line.endswith(":"):
            if current_name is not None:
                blocks[current_name] = "\n".join(current_lines)
            current_name = line[:-1]
            current_lines = [line]
            continue
        if current_name is not None:
            current_lines.append(line)

    if current_name is not None:
        blocks[current_name] = "\n".join(current_lines)

    missing_sections = [name for name in ordered_names if name not in blocks]
    if len(missing_sections) > 0:
        raise AssertionError(f"Sections racines absentes du fixture: {missing_sections!r}")

    return "\n\n".join(blocks[name] for name in ordered_names) + "\n"


repo_root = Path(sys.argv[1])
example_path = repo_root / "config" / "application.example.yaml"
example_text = example_path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")

signature = inspect.signature(load_application_configuration)
for parameter_name in ("config_path", "environment_snapshot"):
    parameter = signature.parameters[parameter_name]
    if parameter.default is not inspect.Parameter.empty:
        raise AssertionError(f"Valeur par défaut interdite pour {parameter_name}.")

source = inspect.getsource(configuration_module)
for forbidden_fragment in ("os.environ", "getenv("):
    if forbidden_fragment in source:
        raise AssertionError(f"Fragment interdit dans le chargeur: {forbidden_fragment}")

validated_configuration = load_application_configuration(
    config_path=example_path,
    environment_snapshot={},
)

# Parse YAML: les value objects exposent les valeurs de configuration typées.
assert_equal(validated_configuration.deployment.topology, "two_host_local", "Topologie non chargée.")
assert_equal(
    validated_configuration.deployment.hosts.docker_local.bind_host,
    "127.0.0.1",
    "Binding hôte utilisateur non chargé.",
)
assert_equal(
    validated_configuration.deployment.hosts.docker_local.container_listen_host,
    "0.0.0.0",
    "Adresse d'écoute conteneur non chargée.",
)
assert_equal(
    validated_configuration.deployment.hosts.spark_inference.endpoint_hosts,
    ("192.168.1.120",),
    "Hôte Spark réel déclaré non chargé.",
)
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

    reordered_yaml_path = write_configuration(
        temporary_directory / "application_reordonnee.yaml",
        reorder_root_sections(
            example_text,
            (
                "runtime",
                "observability",
                "quality_gates",
                "security",
                "paths",
                "models",
                "services",
                "deployment",
            ),
        ),
    )
    original_yaml_path = write_configuration(
        temporary_directory / "application_originale.yaml",
        example_text,
    )
    assert_equal(
        load_application_configuration(config_path=reordered_yaml_path, environment_snapshot={}).configuration_hash,
        load_application_configuration(config_path=original_yaml_path, environment_snapshot={}).configuration_hash,
        "Le hash doit dépendre du contenu validé et non de l'ordre YAML.",
    )

    invalid_yaml_path = temporary_directory / "yaml_invalide.yaml"
    invalid_yaml_path.write_text("services: [", encoding="utf-8")
    assert_raises_code(
        "CONFIG_SCHEMA_INVALID",
        lambda: load_application_configuration(config_path=invalid_yaml_path, environment_snapshot={}),
    )

    invalid_type_cases = (
        (
            "port_chaine",
            example_text.replace("    port: 8080\n", '    port: "8080"\n', 1),
        ),
        (
            "concurrence_zero",
            example_text.replace("    concurrency: 2\n", "    concurrency: 0\n", 1),
        ),
        (
            "exposition_booleen_chaine",
            example_text.replace("  allow_public_bind: false\n", '  allow_public_bind: "false"\n', 1),
        ),
    )
    for mutation_name, mutated_text in invalid_type_cases:
        invalid_type_path = write_configuration(temporary_directory / f"{mutation_name}.yaml", mutated_text)
        assert_raises_code(
            "CONFIG_SCHEMA_INVALID",
            lambda path=invalid_type_path: load_application_configuration(
                config_path=path,
                environment_snapshot={},
            ),
        )

    unknown_root_path = write_configuration(
        temporary_directory / "section_inconnue.yaml",
        example_text + "\nenvironment:\n  DATABASE_URL: postgresql://interdit\n",
    )
    assert_raises_code(
        "CONFIG_SCHEMA_INVALID",
        lambda: load_application_configuration(config_path=unknown_root_path, environment_snapshot={}),
    )

    unknown_service_path = write_configuration(
        temporary_directory / "service_inconnu.yaml",
        example_text.replace("services:\n", "services:\n  redis:\n    url: redis://redis:6379\n", 1),
    )
    assert_raises_code(
        "CONFIG_SCHEMA_INVALID",
        lambda: load_application_configuration(config_path=unknown_service_path, environment_snapshot={}),
    )

    secret_inline_path = write_configuration(
        temporary_directory / "secret_inline.yaml",
        example_text.replace("  secrets:\n", "  secrets:\n    password: secret-en-clair\n", 1),
    )
    assert_raises_code(
        "CONFIG_SECRET_INLINE_REJECTED",
        lambda: load_application_configuration(config_path=secret_inline_path, environment_snapshot={}),
    )

    blank_path = write_configuration(
        temporary_directory / "valeur_blanche.yaml",
        example_text.replace("    url: postgresql+psycopg://app@postgres/app\n", '    url: "   "\n', 1),
    )
    assert_raises_code(
        "CONFIG_KEY_EMPTY",
        lambda: load_application_configuration(config_path=blank_path, environment_snapshot={}),
    )

    required_missing_path = write_configuration(
        temporary_directory / "cle_absente.yaml",
        example_text.replace("      allowed_client_cidrs:\n        - 192.168.1.20/32\n", "", 1),
    )
    assert_raises_code(
        "CONFIG_KEY_MISSING",
        lambda: load_application_configuration(config_path=required_missing_path, environment_snapshot={}),
    )

    host_non_loopback_path = write_configuration(
        temporary_directory / "host_non_loopback.yaml",
        example_text.replace("      bind_host: 127.0.0.1\n", "      bind_host: 192.168.1.20\n", 1),
    )
    assert_raises_code(
        "CONFIG_SCHEMA_INVALID",
        lambda: load_application_configuration(config_path=host_non_loopback_path, environment_snapshot={}),
    )

    host_public_path = write_configuration(
        temporary_directory / "host_public.yaml",
        example_text.replace("      bind_host: 127.0.0.1\n", "      bind_host: 0.0.0.0\n", 1),
    )
    assert_raises_code(
        "CONFIG_SCHEMA_INVALID",
        lambda: load_application_configuration(config_path=host_public_path, environment_snapshot={}),
    )

    spark_non_declare_path = write_configuration(
        temporary_directory / "spark_non_declare.yaml",
        example_text.replace(
            "    spark_endpoint_url: http://192.168.1.120:8000/v1\n",
            "    spark_endpoint_url: http://192.168.1.121:8000/v1\n",
            1,
        ),
    )
    assert_raises_code(
        "CONFIG_SCHEMA_INVALID",
        lambda: load_application_configuration(config_path=spark_non_declare_path, environment_snapshot={}),
    )

    spark_path_invalide_path = write_configuration(
        temporary_directory / "spark_path_invalide.yaml",
        example_text.replace(
            "    spark_endpoint_url: http://192.168.1.120:8000/v1\n",
            "    spark_endpoint_url: http://192.168.1.120:8000/chat\n",
            1,
        ),
    )
    assert_raises_code(
        "CONFIG_SCHEMA_INVALID",
        lambda: load_application_configuration(config_path=spark_path_invalide_path, environment_snapshot={}),
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
