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
$compose = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "deploy\local-compose\compose.yaml")
$dockerfile = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "deploy\local-compose\Dockerfile")
$runbookPath = Join-Path $repoRoot "docs\runbooks\api_orchestratrice.md"
$auditPath = Join-Path $repoRoot "docs\governance\m013_fastapi_audit.md"

# When le lancement local et le service Compose sont audités.
Assert-Contains $pyproject 'api = "app.platform.orchestrator_command:main"' "Commande projet api absente."
Assert-Contains $compose "  orchestrator-api:" "Service Compose orchestrator-api absent."
Assert-Contains $compose "      - api" "Compose ne lance pas le point d'entrée Uvicorn dédié."
Assert-Contains $compose "      - --config" "Compose ne transmet pas la configuration unique."
Assert-Contains $compose "      - /workspace/config/application.yaml" "Chemin de configuration Compose invalide."
Assert-Contains $compose 'http://127.0.0.1:8080/ready' "Healthcheck readiness HTTP absent."
Assert-Contains $dockerfile "COPY uv.lock ./uv.lock" "Le verrou uv n'est pas copié dans l'image."
if ($compose.Contains("app.platform.local_runtime") -and $compose.IndexOf("app.platform.local_runtime", $compose.IndexOf("  orchestrator-api:")) -lt $compose.IndexOf("  llm-gateway:")) {
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
foreach ($marker in @("uv run api --config", "/health", "/ready", "/openapi.json", "rollback", "ADR-019")) {
    Assert-Contains $runbook $marker "Runbook API incomplet."
}
foreach ($marker in @("M13-FastAPI", "configuration_hash", "trace_id", "PostgreSQL", "PDF réel", "aucun fallback")) {
    Assert-Contains $audit $marker "Rapport d'audit incomplet."
}

# Then un seul runtime public sert les contrats avec une procédure reproductible.
Write-Host "Test d'acceptation déploiement orchestrator-api: OK"
