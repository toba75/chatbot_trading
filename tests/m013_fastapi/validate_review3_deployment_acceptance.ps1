$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path

function Assert-Contains {
    param([string] $Content, [string] $Expected, [string] $Message)
    if (-not $Content.Contains($Expected)) {
        throw "$Message Valeur attendue: $Expected"
    }
}

function Assert-NotContains {
    param([string] $Content, [string] $Unexpected, [string] $Message)
    if ($Content.Contains($Unexpected)) {
        throw "$Message Valeur interdite: $Unexpected"
    }
}

# Given un clone propre positionné sur un commit complet M13-FastAPI.
# When l'exploitant prépare la stack finale et son rollback.
# Then le contenu construit, les dépendances, les identités et les paramètres réellement supportés sont stricts.
$pyproject = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "pyproject.toml")
$uvLock = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "uv.lock")
$dockerfile = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "deploy/local-compose/Dockerfile")
$dockerignorePath = Join-Path $repoRoot ".dockerignore"
$compose = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "deploy/local-compose/compose.yaml")
$composeConfigPath = Join-Path $repoRoot "deploy/local-compose/application.compose.yaml"
$schema = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "config/application.schema.json")
$example = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "config/application.example.yaml")
$runtime = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "app/platform/orchestrator_runtime.py")
$gate = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "scripts/validate_m013_fastapi.ps1")

foreach ($marker in @(
    'requires-python = "==3.12.8"',
    'setuptools==80.10.2',
    'pydantic==2.13.4',
    'starlette==1.3.1'
)) {
    Assert-Contains $pyproject $marker "Dépendance directe ou interpréteur non verrouillé."
}
foreach ($marker in @(
    'requires-python = "==3.12.8"',
    'pydantic", specifier = "==2.13.4"',
    'starlette", specifier = "==1.3.1"',
    'setuptools", specifier = "==80.10.2"'
)) {
    Assert-Contains $uvLock $marker "Verrou de dépendance incomplet."
}

foreach ($marker in @(
    'python:3.12.8-slim-bookworm@sha256:',
    'FROM runtime AS orchestrator-api',
    'ENTRYPOINT ["api"]',
    'FROM runtime AS worker-documents',
    'ENTRYPOINT ["python", "-m", "app.source_processing.adapters.worker_runtime"]',
    'org.opencontainers.image.revision="${OSTRADING_IMAGE_REVISION}"',
    'org.ostrading.postgres-schema-version="${OSTRADING_POSTGRES_SCHEMA_VERSION}"'
)) {
    Assert-Contains $dockerfile $marker "Artefact final Docker non reproductible."
}

if (-not (Test-Path -LiteralPath $dockerignorePath -PathType Leaf)) {
    throw "DOCKERIGNORE_ROOT_REQUIRED"
}
$dockerignore = Get-Content -Raw -Encoding UTF8 $dockerignorePath
foreach ($marker in @('.git', '.venv', 'data', '**/secrets', '**/.tmp*', '!app/**', '!pyproject.toml', '!uv.lock', '!deploy/postgres/migrations/**')) {
    Assert-Contains $dockerignore $marker "Contexte Docker insuffisamment borné."
}

if (-not (Test-Path -LiteralPath $composeConfigPath -PathType Leaf)) {
    throw "COMPOSE_CONFIGURATION_REQUIRED"
}
$composeConfig = Get-Content -Raw -Encoding UTF8 $composeConfigPath
foreach ($marker in @(
    'url: postgresql+psycopg://ostrading@postgres/ostrading',
    'url: http://llm-gateway:8090',
    'postgres_password_path: /run/secrets/postgres_password'
)) {
    Assert-Contains $composeConfig $marker "Configuration Compose incohérente."
}
Assert-NotContains $composeConfig '127.0.0.1:8090' "Le conteneur ne doit pas adresser le gateway par loopback."

foreach ($marker in @(
    'POSTGRES_DB: "ostrading"',
    'POSTGRES_USER: "ostrading"',
    './application.compose.yaml:/workspace/config/application.yaml:ro',
    'target: orchestrator-api',
    'target: worker-documents',
    'ostrading/worker-documents:0.1.0-m013-fastapi-schema-${OSTRADING_POSTGRES_SCHEMA_VERSION?OSTRADING_POSTGRES_SCHEMA_VERSION requis}-${OSTRADING_IMAGE_REVISION?OSTRADING_IMAGE_REVISION requis}',
    'replicas: 2'
)) {
    Assert-Contains $compose $marker "Topologie Compose finale incomplète."
}
Assert-NotContains $compose 'POSTGRES_DB?POSTGRES_DB requis' "L'identité PostgreSQL ne doit pas diverger de la configuration montée."
Assert-NotContains $compose 'worker-documents:0.0.0-m002' "Le worker ne doit plus utiliser un tag mutable historique."

foreach ($marker in @('HttpHealthOrchestratorDependency', 'name="llm-gateway"', 'LLM_GATEWAY_NOT_READY')) {
    Assert-Contains $runtime $marker "Readiness llm-gateway absente ou sans code sûr."
}

foreach ($unsupported in @('"metrics"', '"endpoint_path"', '"retention_days"', '"level"')) {
    Assert-NotContains $schema $unsupported "Paramètre d'observabilité sans consommateur encore accepté."
}
foreach ($unsupported in @('  metrics:', '    endpoint_path:', '    retention_days:', '    level:')) {
    Assert-NotContains $example $unsupported "Exemple d'observabilité sans consommateur encore publié."
}
foreach ($marker in @('tracing:', 'enabled: true', 'logs:', 'include_payloads: false')) {
    Assert-Contains $example $marker "Contrat minimal d'observabilité utilisé absent."
}

foreach ($marker in @(
    'tests/m013_fastapi/validate_review3_deployment_acceptance.ps1',
    'tests/m013_fastapi/validate_review3_deployment_live.ps1'
)) {
    Assert-Contains $gate $marker "Preuve de déploiement non enrôlée dans la gate."
}

Write-Host "Test d'acceptation déploiement et reproductibilité revue 3: OK"
