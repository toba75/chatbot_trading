$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

function Assert-Contains {
    param([string] $Content, [string] $Expected, [string] $Message)
    if (-not $Content.Contains($Expected)) {
        throw "$Message Valeur attendue: $Expected"
    }
}

# Given l'application ASGI et les contrats documentaires sont GREEN.
$pyproject = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "pyproject.toml")
$uvLock = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "uv.lock")
$compose = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "deploy\local-compose\compose.yaml")
$dockerfile = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "deploy\local-compose\Dockerfile")
$caddyfile = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "deploy\local-compose\Caddyfile")
$runbookPath = Join-Path $repoRoot "docs\runbooks\api_orchestratrice.md"
$auditPath = Join-Path $repoRoot "docs\governance\m013_fastapi_audit.md"

# When le lancement local et le service Compose sont audités.
Assert-Contains $pyproject 'api = "app.platform.orchestrator_command:main"' "Commande projet api absente."
Assert-Contains $pyproject 'pypdf==6.14.2' "Version corrigée pypdf absente."
Assert-Contains $pyproject 'python-multipart==0.0.32' "Version corrigée python-multipart absente."
Assert-Contains $uvLock 'pypdf", specifier = "==6.14.2"' "Verrou pypdf corrigé absent."
Assert-Contains $uvLock 'python-multipart", specifier = "==0.0.32"' "Verrou python-multipart corrigé absent."
if ($uvLock.Contains('pypdf", specifier = "==6.10.2"') -or $uvLock.Contains('python-multipart", specifier = "==0.0.22"')) {
    throw "Une version vulnérable reste verrouillée."
}
Assert-Contains $compose "  orchestrator-api:" "Service Compose orchestrator-api absent."
Assert-Contains $compose "      - api" "Compose ne lance pas le point d'entrée Uvicorn dédié."
Assert-Contains $compose "      - --config" "Compose ne transmet pas la configuration unique."
Assert-Contains $compose "      - /workspace/config/application.yaml" "Chemin de configuration Compose invalide."
Assert-Contains $compose 'http://127.0.0.1:8080/ready' "Healthcheck readiness HTTP absent."
Assert-Contains $compose 'ostrading/orchestrator-api:0.1.0-m013-fastapi-schema-003' "Tag image/schéma M13-FastAPI absent."
Assert-Contains $caddyfile 'max_size 54MB' "Limite agrégée Caddy absente."
Assert-Contains $dockerfile "COPY uv.lock ./uv.lock" "Le verrou uv n'est pas copié dans l'image."
Assert-Contains $dockerfile "AS builder" "Étape builder Docker absente."
Assert-Contains $dockerfile "AS runtime" "Étape runtime Docker absente."
Assert-Contains $dockerfile 'org.ostrading.postgres-schema-version="003"' "Version de schéma absente de l'image."
Assert-Contains $dockerfile "COPY --chown=ostrading:ostrading deploy/postgres/migrations ./deploy/postgres/migrations" "Migrations non embarquées dans l'image."
$runtimeBlock = $dockerfile.Substring($dockerfile.IndexOf("AS runtime"))
if ($runtimeBlock.Contains("pip install") -or $runtimeBlock.Contains(" uv sync")) {
    throw "Le runtime Docker ne doit ni installer uv ni résoudre les dépendances."
}
$orchestratorBlock = [regex]::Match(
    $compose,
    '(?ms)^  orchestrator-api:\r?\n(?<block>.*?)(?=^  [a-z0-9-]+:\r?$)'
).Groups['block'].Value
if ([string]::IsNullOrWhiteSpace($orchestratorBlock)) {
    throw "Bloc Compose orchestrator-api illisible."
}
Assert-Contains $orchestratorBlock "      timeout: 300s" "Timeout healthcheck non aligné avec request_seconds."
Assert-Contains $orchestratorBlock "      start_period: 120s" "Budget startup healthcheck non aligné."
Assert-Contains $orchestratorBlock "    stop_grace_period: 30s" "Budget shutdown Compose non aligné."
Assert-Contains $orchestratorBlock '/tmp:size=128m,mode=1777' "tmpfs borné du double spool multipart absent."
if ($orchestratorBlock.Contains("app.platform.local_runtime")) {
    throw "L'ancien runtime local reste actif pour orchestrator-api."
}
if (-not (Test-Path -LiteralPath $runbookPath -PathType Leaf)) {
    throw "Runbook API orchestratrice absent: docs/runbooks/api_orchestratrice.md"
}
if (-not (Test-Path -LiteralPath $auditPath -PathType Leaf)) {
    throw "Rapport d'audit M13-FastAPI absent: docs/governance/m013_fastapi_audit.md"
}
$runbook = Get-Content -Raw -Encoding UTF8 $runbookPath
$audit = Get-Content -Raw -Encoding UTF8 $auditPath
foreach ($marker in @("uv run api --config", "api --config /workspace/config/application.yaml", "exec -T orchestrator-api", "python -m app.platform.postgres_migrations", "/health", "/ready", "/openapi.json", "rollback", "ADR-019", "ADR-020", "ADR-021")) {
    Assert-Contains $runbook $marker "Runbook API incomplet."
}
foreach ($marker in @("M13-FastAPI", "configuration_hash", "trace_id", "PostgreSQL", "PDF", "fallback")) {
    Assert-Contains $audit $marker "Rapport d'audit incomplet."
}

# Then un seul runtime public sert les contrats avec une procédure reproductible.
Write-Host "Test d'acceptation déploiement orchestrator-api: OK"
