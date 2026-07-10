$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
from __future__ import annotations

import copy
from pathlib import Path
import sys
import tempfile

import yaml

sys.path.insert(0, sys.argv[1])

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


def write_yaml(path, payload):
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


repo_root = Path(sys.argv[1])
example_path = repo_root / "config" / "application.example.yaml"
example_payload = yaml.safe_load(example_path.read_text(encoding="utf-8-sig"))

# Given un processus applicatif reçoit --config config/application.yaml.
# When le fichier est lisible, conforme et qu'aucune variable homonyme n'est présente.
# Then le chargeur retourne une configuration validée et aucun accès à l'environnement ne pilote l'application.
validated_configuration = load_application_configuration(
    config_path=example_path,
    environment_snapshot={},
)
assert_equal(
    validated_configuration.services.postgres.url,
    "postgresql+psycopg://app@postgres/app",
    "La configuration validée doit exposer l'URL PostgreSQL du fichier.",
)
assert_equal(
    validated_configuration.services.llm_gateway.spark_endpoint_url,
    "https://spark-inference.home.arpa/v1",
    "La configuration validée doit exposer l'endpoint Spark du fichier.",
)
assert_equal(
    validated_configuration.models.llm.served_model_name,
    "gemma-4-31b-it-nvfp4",
    "La configuration validée doit exposer le modèle servi du fichier.",
)
assert_true(
    len(validated_configuration.configuration_hash) == 64
    and all(character in "0123456789abcdef" for character in validated_configuration.configuration_hash),
    "La configuration validée doit produire un hash SHA-256 hexadécimal.",
)
assert_equal(
    validated_configuration.configuration_hash,
    load_application_configuration(config_path=example_path, environment_snapshot={}).configuration_hash,
    "Le hash de configuration doit être stable pour un même fichier.",
)

with tempfile.TemporaryDirectory(prefix="ost_m013_config_loader_acceptance_") as temporary_directory_name:
    temporary_directory = Path(temporary_directory_name)

    assert_raises_code(
        "CONFIG_FILE_REQUIRED",
        lambda: load_application_configuration(config_path="", environment_snapshot={}),
    )

    assert_raises_code(
        "CONFIG_FILE_UNREADABLE",
        lambda: load_application_configuration(
            config_path=temporary_directory / "application.absente.yaml",
            environment_snapshot={},
        ),
    )

    assert_raises_code(
        "CONFIG_FILE_UNREADABLE",
        lambda: load_application_configuration(
            config_path=temporary_directory,
            environment_snapshot={},
        ),
    )

    invalid_schema_payload = copy.deepcopy(example_payload)
    invalid_schema_payload["services"]["api"]["port"] = "8080"
    invalid_schema_path = write_yaml(temporary_directory / "schema_invalide.yaml", invalid_schema_payload)
    assert_raises_code(
        "CONFIG_SCHEMA_INVALID",
        lambda: load_application_configuration(
            config_path=invalid_schema_path,
            environment_snapshot={},
        ),
    )

    missing_key_payload = copy.deepcopy(example_payload)
    del missing_key_payload["services"]["postgres"]["url"]
    missing_key_path = write_yaml(temporary_directory / "cle_obligatoire_absente.yaml", missing_key_payload)
    assert_raises_code(
        "CONFIG_KEY_MISSING",
        lambda: load_application_configuration(
            config_path=missing_key_path,
            environment_snapshot={},
        ),
    )

    empty_key_payload = copy.deepcopy(example_payload)
    empty_key_payload["models"]["llm"]["runtime_version"] = ""
    empty_key_path = write_yaml(temporary_directory / "cle_vide.yaml", empty_key_payload)
    assert_raises_code(
        "CONFIG_KEY_EMPTY",
        lambda: load_application_configuration(
            config_path=empty_key_path,
            environment_snapshot={},
        ),
    )

    placeholder_payload = copy.deepcopy(example_payload)
    placeholder_payload["models"]["llm"]["model_revision"] = "TO_BE_FILLED"
    placeholder_path = write_yaml(temporary_directory / "placeholder.yaml", placeholder_payload)
    assert_raises_code(
        "CONFIG_KEY_EMPTY",
        lambda: load_application_configuration(
            config_path=placeholder_path,
            environment_snapshot={},
        ),
    )

    assert_raises_code(
        "CONFIG_ENV_INPUT_REJECTED",
        lambda: load_application_configuration(
            config_path=example_path,
            environment_snapshot={"DATABASE_URL": "postgresql://env/interdit"},
        ),
    )

print("Test d'acceptation du chargeur de configuration applicative: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_config_loader_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation du chargeur de configuration applicative: OK"
