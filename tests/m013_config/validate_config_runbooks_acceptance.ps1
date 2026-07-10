$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$configurationRunbookPath = Join-Path $repoRoot "docs/runbooks/configuration_applicative.md"
$localOperationsRunbookPath = Join-Path $repoRoot "docs/runbooks/exploitation_locale.md"
$composeReadmePath = Join-Path $repoRoot "deploy/local-compose/README.md"

function Get-DocumentContent {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Document attendu absent: $Path"
    }

    return (Get-Content -Raw -Encoding UTF8 -LiteralPath $Path).TrimStart([char] 0xFEFF)
}

function Assert-Contains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if (-not $Content.Contains($Expected)) {
        throw $Message
    }
}

function Assert-NotContains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $Forbidden,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if ($Content.Contains($Forbidden)) {
        throw $Message
    }
}

function Assert-MigrationOnlyHistoricalEntries {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    $allowedSections = @(
        "## Mapping de migration",
        "## Entrées rejetées"
    )
    $currentSection = ""
    $historicalPatterns = @(
        "GEMMA_",
        "DATABASE_URL",
        "QDRANT_URL",
        "LLM_GATEWAY_URL",
        "env_file",
        ".env",
        "environment:"
    )

    $lines = $Content -split "`r?`n"
    for ($index = 0; $index -lt $lines.Count; $index++) {
        $line = $lines[$index]
        if ($line.StartsWith("## ")) {
            $currentSection = $line.Trim()
        }

        foreach ($pattern in $historicalPatterns) {
            if ($line.Contains($pattern) -and -not ($allowedSections -contains $currentSection)) {
                throw "Entrée historique hors mapping ou rejet ligne $($index + 1): $line"
            }
        }
    }
}

# Given un exploitant local lit les runbooks après M13-config.
# When il prépare et démarre la pile V1.
# Then chaque commande utilise --config ou Compose déjà configuré, les anciennes
# entrées sont présentées comme rejetées ou à migrer, et la preuve d'audit cite
# le fichier chargé.
$configurationRunbook = Get-DocumentContent -Path $configurationRunbookPath
$localOperationsRunbook = Get-DocumentContent -Path $localOperationsRunbookPath
$composeReadme = Get-DocumentContent -Path $composeReadmePath

foreach ($marker in @(
    "# Runbook configuration applicative M13-config",
    "M13Config-Runbook-ApplicationConfiguration-1.0",
    "Given un exploitant local lit les runbooks après M13-config.",
    "When il prépare et démarre la pile V1.",
    'Then chaque commande utilise `--config`, les anciennes variables sont présentées comme entrées rejetées, et la preuve d''audit cite le fichier chargé.',
    'Copier `config/application.example.yaml` vers `config/application.yaml`',
    "config/application.schema.json",
    "load_application_configuration",
    "docker compose -f .\deploy\local-compose\compose.yaml up --build",
    "configuration_hash",
    "config_hash",
    "secret hors Git",
    "config/secrets/local/",
    "## Mapping de migration",
    "## Entrées rejetées"
)) {
    Assert-Contains -Content $configurationRunbook -Expected $marker -Message "Marqueur runbook configuration absent: $marker"
}

foreach ($mapping in @(
    '| `DATABASE_URL` | `services.postgres.url` |',
    '| `QDRANT_URL` | `services.qdrant.url` |',
    '| `LLM_GATEWAY_URL` | `services.llm_gateway.url` |',
    '| `GEMMA_BASE_URL` | `services.llm_gateway.spark_endpoint_url` |',
    '| `GEMMA_MODEL_REVISION` | `models.llm.model_revision` |',
    '| `GEMMA_API_KEY_FILE` | `security.secrets.llm_gateway_api_key_path` |',
    '| `GEMMA_CA_BUNDLE` | `security.secrets.tls_ca_certificate_path` |'
)) {
    Assert-Contains -Content $configurationRunbook -Expected $mapping -Message "Mapping de migration absent: $mapping"
}

Assert-MigrationOnlyHistoricalEntries -Content $configurationRunbook

foreach ($commandMarker in @(
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_application_config_loader_acceptance.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_config_environment.ps1",
    "python -m app.platform.local_runtime serve-http llm-gateway 8090 --config .\config\application.yaml"
)) {
    Assert-Contains -Content $configurationRunbook -Expected $commandMarker -Message "Commande vérifiée absente ou sans --config: $commandMarker"
}

foreach ($forbiddenSecret in @(
    "BEGIN PRIVATE KEY",
    "Authorization: Bearer",
    "sk-",
    "api_key: ",
    "password: secret",
    "token: "
)) {
    Assert-NotContains -Content $configurationRunbook -Forbidden $forbiddenSecret -Message "Secret factice ou secret en clair interdit dans le runbook: $forbiddenSecret"
}

Assert-Contains -Content $localOperationsRunbook -Expected "config/application.yaml" -Message "Runbook exploitation locale sans fichier applicatif."
Assert-Contains -Content $localOperationsRunbook -Expected "--config" -Message "Runbook exploitation locale sans rappel --config."
Assert-Contains -Content $localOperationsRunbook -Expected "hash de configuration" -Message "Runbook exploitation locale sans preuve de hash de configuration."
Assert-Contains -Content $composeReadme -Expected "--config /workspace/config/application.yaml" -Message "README Compose sans commande applicative --config."
Assert-Contains -Content $composeReadme -Expected "config/application.yaml" -Message "README Compose sans configuration applicative."

Write-Host "Test d'acceptation runbooks configuration M13-config: OK"
