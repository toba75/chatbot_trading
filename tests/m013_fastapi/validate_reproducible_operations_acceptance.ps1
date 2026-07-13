$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

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

# Given un clone propre, un commit Git précis et les migrations livrées dans ce commit.
# When l'exploitant valide puis construit la stack M13-FastAPI.
# Then l'interpréteur, les images, le schéma et les commandes sont verrouillés sans recette hôte implicite.
$gate = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "scripts\validate_m013_fastapi.ps1")
$dockerfile = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "deploy\local-compose\Dockerfile")
$compose = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "deploy\local-compose\compose.yaml")
$runbook = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "docs\runbooks\api_orchestratrice.md")
$audit = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "docs\governance\m013_fastapi_audit.md")

foreach ($marker in @(
    'M013_FASTAPI_UV_REQUIRED',
    'uv sync --frozen --no-dev',
    'UV_PROJECT_ENVIRONMENT',
    'M013_FASTAPI_PYTHON',
    'M013_FASTAPI_TEMP_ENVIRONMENT',
    'M013_FASTAPI_LOCKED_PYTHON_REQUIRED',
    'M013_FASTAPI_PROJECT_VERSION_REQUIRED',
    'from importlib.metadata import version'
)) {
    Assert-Contains $gate $marker "Bootstrap verrouillé de la gate absent."
}
Assert-NotContains $gate 'Join-Path $repoRoot ".venv\Scripts"' "La gate reproductible ne doit pas écrire la .venv partagée."
Assert-NotContains $gate '--no-install-project' "La gate isolée doit installer le projet et sa métadonnée de version."

Assert-Contains $dockerfile 'ghcr.io/astral-sh/uv@sha256:' "Image uv non épinglée par digest."
Assert-Contains $dockerfile 'python:3.12.8-slim-bookworm@sha256:' "Image Python non épinglée par digest."
Assert-Contains $dockerfile 'ARG OSTRADING_IMAGE_REVISION' "Révision d'image obligatoire absente."
Assert-Contains $dockerfile 'ARG OSTRADING_POSTGRES_SCHEMA_VERSION' "Version de schéma obligatoire absente."
Assert-Contains $dockerfile 'org.opencontainers.image.revision="${OSTRADING_IMAGE_REVISION}"' "Label de révision immuable absent."
Assert-Contains $dockerfile 'org.ostrading.postgres-schema-version="${OSTRADING_POSTGRES_SCHEMA_VERSION}"' "Label de schéma dynamique absent."
Assert-NotContains $dockerfile 'pip install --no-cache-dir uv' "Le bootstrap uv téléchargé sans preuve d'intégrité reste actif."

Assert-Contains $compose 'schema-${OSTRADING_POSTGRES_SCHEMA_VERSION?OSTRADING_POSTGRES_SCHEMA_VERSION requis}-${OSTRADING_IMAGE_REVISION?OSTRADING_IMAGE_REVISION requis}' "Tag image commit+schéma obligatoire absent."
Assert-Contains $compose 'OSTRADING_IMAGE_REVISION: "${OSTRADING_IMAGE_REVISION?OSTRADING_IMAGE_REVISION requis}"' "Build arg de révision absent."
Assert-Contains $compose 'OSTRADING_POSTGRES_SCHEMA_VERSION: "${OSTRADING_POSTGRES_SCHEMA_VERSION?OSTRADING_POSTGRES_SCHEMA_VERSION requis}"' "Build arg de schéma absent."

foreach ($marker in @(
    '$sourceCommit = (git rev-parse HEAD).Trim()',
    '$schemaVersion = $Matches.version',
    '[System.Environment]::SetEnvironmentVariable',
    '[System.IO.Path]::GetTempPath()',
    'finally',
    'docker compose -f .\deploy\local-compose\compose.yaml config',
    'docker compose -f .\deploy\local-compose\compose.yaml up --build',
    'validate_m013_fastapi.ps1 -Mode Live',
    '127.0.0.1',
    'REFUS_BIND_PUBLIC'
)) {
    Assert-Contains $runbook $marker "Procédure Compose reproductible ou garde-fou réseau absent."
}
foreach ($forbiddenEnvironmentInput in @(
    '$env:OST_EDGE_HTTPS_PORT',
    '$env:CADDY_ADMIN',
    '$env:OSTRADING_IMAGE_REVISION',
    '$env:OSTRADING_POSTGRES_SCHEMA_VERSION',
    '$env:TEMP'
)) {
    Assert-NotContains $runbook $forbiddenEnvironmentInput "Le runbook ne doit pas publier d'entrée environnement opérationnelle."
}
Assert-NotContains $runbook 'uv run api --config' "La recette hôte non reproductible reste documentée."
Assert-NotContains $runbook '--no-install-project' "Le runbook ne doit pas décrire une installation sans le projet."
Assert-Contains $runbook 'chatbot-trading` en version `0.1.0' "La preuve de métadonnée du paquet installé manque au runbook."
Assert-Contains $runbook 'POST /v1/documents' "Contrat OpenAPI de création absent."
Assert-Contains $runbook '201 application/json' "Média OpenAPI de création imprécis."
Assert-Contains $runbook 'GET /v1/documents/{document_id}/original' "Contrat OpenAPI de restitution absent."
Assert-Contains $runbook '200 application/pdf' "Média OpenAPI PDF 200 imprécis."

foreach ($marker in @(
    "## $([char]0x00C9)tat courant",
    '## Preuves historiques',
    'deploy/postgres/migrations/*.sql',
    'org.opencontainers.image.revision',
    'validate_m013_fastapi.ps1 -Mode Live',
    'scripts/test.ps1',
    'chatbot-trading` en version `0.1.0',
    'non concluant'
)) {
    Assert-Contains $audit $marker "Audit courant/historique incomplet."
}

Write-Host "Test d'acceptation des opérations reproductibles M13-FastAPI: OK"
