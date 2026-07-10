$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m013_config_environment.ps1"
$temporaryRoot = Join-Path $repoRoot (".tmp/ost_m013_config_environment_unit_" + [System.Guid]::NewGuid().ToString("N"))

function Invoke-EnvironmentValidator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $RootPath
    )

    if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
        throw "Validateur environnement M13-config absent: scripts/validate_m013_config_environment.ps1"
    }

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $validatorPath -RootPath $RootPath 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    return [pscustomobject] @{
        ExitCode = $exitCode
        Output = ($output -join "`n")
    }
}

function Write-Fixture {
    param(
        [Parameter(Mandatory = $true)]
        [string] $RelativePath,

        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    $path = Join-Path $temporaryRoot $RelativePath
    New-Item -ItemType Directory -Path (Split-Path -Parent $path) -Force | Out-Null
    Set-Content -Encoding UTF8 -LiteralPath $path -Value $Content
}

function Reset-FixtureRoot {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Path $temporaryRoot | Out-Null
}

function Assert-GreenFixture {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    $result = Invoke-EnvironmentValidator -RootPath $temporaryRoot
    if ($result.ExitCode -ne 0) {
        throw "Fixture $Name attendue GREEN. Sortie obtenue: $($result.Output)"
    }
}

function Assert-RedFixture {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $true)]
        [string] $ExpectedFragment
    )

    $result = Invoke-EnvironmentValidator -RootPath $temporaryRoot
    if ($result.ExitCode -ne 1) {
        throw "Fixture $Name attendue RED. Code obtenu: $($result.ExitCode). Sortie: $($result.Output)"
    }
    if (-not $result.Output.Contains("CONFIG_ENV_INPUT_REJECTED")) {
        throw "Fixture $Name sans code CONFIG_ENV_INPUT_REJECTED. Sortie: $($result.Output)"
    }
    if (-not $result.Output.Contains($ExpectedFragment)) {
        throw "Fixture $Name sans fragment attendu '$ExpectedFragment'. Sortie: $($result.Output)"
    }
}

try {
    Reset-FixtureRoot
    Write-Fixture -RelativePath "app/platform/local_runtime.py" -Content @'
import os

def load(path):
    return load_application_configuration(config_path=path, environment_snapshot=dict(os.environ))
'@
    Write-Fixture -RelativePath "app/platform/configuration/__init__.py" -Content @'
CONFIG_ENV_INPUT_REJECTED = "CONFIG_ENV_INPUT_REJECTED"
_HISTORICAL_ENVIRONMENT_KEYS = ("DATABASE_URL", "QDRANT_URL", "LLM_GATEWAY_URL")
_HISTORICAL_ENVIRONMENT_PREFIXES = ("GEMMA_",)
'@
    Write-Fixture -RelativePath "app/platform/local_compose.py" -Content @'
FORBIDDEN_APPLICATION_ENVIRONMENT_KEYS = frozenset(("DATABASE_URL", "QDRANT_URL", "LLM_GATEWAY_URL"))
FORBIDDEN_APPLICATION_ENVIRONMENT_PREFIXES = ("GEMMA_",)
'@
    Write-Fixture -RelativePath "deploy/local-compose/compose.yaml" -Content @'
services:
  edge-gateway:
    environment:
      CADDY_ADMIN: "${CADDY_ADMIN?CADDY_ADMIN requis}"
  postgres:
    environment:
      POSTGRES_DB: "${POSTGRES_DB?POSTGRES_DB requis}"
      POSTGRES_USER: "${POSTGRES_USER?POSTGRES_USER requis}"
      POSTGRES_PASSWORD_FILE: "/run/secrets/postgres_password"
'@
    Write-Fixture -RelativePath "scripts/test.ps1" -Content @'
if ($env:OST_M013_PRECONDITION_ACCEPTANCE_RUNNING -eq "1") {
    Write-Host "Garde de récursion technique."
}
'@
    Write-Fixture -RelativePath "app/platform/security/network_boundary.py" -Content @'
VLLM_SECRET_MARKERS = ("GEMMA", "VLLM", "OPENAI_API_KEY", "LLM_API_KEY")
'@
    Write-Fixture -RelativePath "scripts/validate_m013_security.ps1" -Content @'
$secretPatterns = @("GEMMA_API_KEY\s*=", "VLLM_API_KEY\s*=")
'@
    Write-Fixture -RelativePath "docs/specs/m013_config_configuration_applicative.md" -Content @'
Les clés historiques GEMMA_BASE_URL, DATABASE_URL et QDRANT_URL sont refusées.
'@
    Write-Fixture -RelativePath "docs/tasks/milestone_013-config/0006.md" -Content @'
La tâche documente os.environ, getenv, process.env, .env, env_file et environment: comme entrées à bloquer.
'@
    Write-Fixture -RelativePath "tests/m013_config/fixture_negative.ps1" -Content @'
$env:DATABASE_URL = "fixture négative"
'@
    Assert-GreenFixture -Name "exceptions techniques nommées"

    Reset-FixtureRoot
    Write-Fixture -RelativePath ".env" -Content "DATABASE_URL=postgresql://interdit`n"
    Assert-RedFixture -Name "fichier .env" -ExpectedFragment ".env"

    Reset-FixtureRoot
    Write-Fixture -RelativePath "scripts/bad_launcher.ps1" -Content '$url = $env:LLM_GATEWAY_URL'
    Assert-RedFixture -Name "script shell applicatif" -ExpectedFragment "LLM_GATEWAY_URL"

    Reset-FixtureRoot
    Write-Fixture -RelativePath "scripts/bad_launcher_upper_env.ps1" -Content '$url = $Env:CUSTOM_RUNTIME_FLAG'
    Assert-RedFixture -Name "script shell applicatif Env majuscule" -ExpectedFragment "CUSTOM_RUNTIME_FLAG"

    Reset-FixtureRoot
    Write-Fixture -RelativePath "scripts/bad_launcher_braced_env.ps1" -Content '$url = ${env:CUSTOM_RUNTIME_FLAG}'
    Assert-RedFixture -Name "script shell applicatif env accolade" -ExpectedFragment "CUSTOM_RUNTIME_FLAG"

    Reset-FixtureRoot
    Write-Fixture -RelativePath "scripts/bad_launcher_provider_env.ps1" -Content 'Get-Item Env:CUSTOM_RUNTIME_FLAG'
    Assert-RedFixture -Name "script shell applicatif provider Env" -ExpectedFragment "CUSTOM_RUNTIME_FLAG"

    Reset-FixtureRoot
    Write-Fixture -RelativePath "scripts/bad_launcher_dotnet_env.ps1" -Content '[Environment]::GetEnvironmentVariable("CUSTOM_RUNTIME_FLAG")'
    Assert-RedFixture -Name "script shell applicatif Environment dotnet" -ExpectedFragment "CUSTOM_RUNTIME_FLAG"

    Reset-FixtureRoot
    Write-Fixture -RelativePath "app/platform/local_runtime.py" -Content @'
import os

def load(path):
    snapshot = dict(os.environ)
    return load_application_configuration(config_path=path, environment_snapshot=snapshot)
'@
    Assert-RedFixture -Name "exception os.environ élargie" -ExpectedFragment "app/platform/local_runtime.py:4"

    Reset-FixtureRoot
    Write-Fixture -RelativePath "app/platform/reject_registry.py" -Content 'FORBIDDEN = ("GEMMA_SECRET_BACKDOOR",)'
    Assert-RedFixture -Name "clé historique hors registre autorisé" -ExpectedFragment "GEMMA_SECRET_BACKDOOR"

    Reset-FixtureRoot
    Write-Fixture -RelativePath "deploy/local-compose/compose.yaml" -Content @'
services:
  qdrant:
    environment:
      QDRANT__SERVICE__GRPC_PORT: "${QDRANT_GRPC_PORT?QDRANT_GRPC_PORT requis}"
'@
    Assert-RedFixture -Name "environment non allowlisté" -ExpectedFragment "QDRANT__SERVICE__GRPC_PORT"
}
finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

Write-Host "Tests unitaires rejet environnement M13-config: OK"
