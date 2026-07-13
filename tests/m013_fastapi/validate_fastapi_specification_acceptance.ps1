$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$adrPath = Join-Path $repoRoot "docs/adr/ADR-019-api-orchestratrice-fastapi-uvicorn.md"
$adrIndexPath = Join-Path $repoRoot "docs/adr/index.md"
$specificationPath = Join-Path $repoRoot "docs/specs/m013_fastapi_api_orchestratrice.md"
$validatorPath = Join-Path $repoRoot "scripts/validate_m013_fastapi_specification.ps1"
$journalPath = Join-Path $repoRoot "docs/tasks/milestone_013-fastapi/journal.md"

function Assert-Condition {
    param(
        [Parameter(Mandatory = $true)]
        [bool] $Condition,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if (-not $Condition) {
        throw $Message
    }
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

    Assert-Condition -Condition $Content.Contains($Expected) -Message $Message
}

# Given l'API orchestratrice est servie par un routeur conditionnel partagé.
# When la décision de frontière HTTP est publiée.
# Then framework, serveur, composition, responsabilités interdites et migration sont explicites et vérifiables.
foreach ($requiredFile in @(
    [ordered] @{ Path = $adrPath; Label = "ADR-019" },
    [ordered] @{ Path = $adrIndexPath; Label = "index ADR" },
    [ordered] @{ Path = $specificationPath; Label = "spécification M13-FastAPI" },
    [ordered] @{ Path = $validatorPath; Label = "validateur M13-FastAPI" },
    [ordered] @{ Path = $journalPath; Label = "journal M13-FastAPI" }
)) {
    Assert-Condition `
        -Condition (Test-Path -LiteralPath $requiredFile.Path -PathType Leaf) `
        -Message "Livrable T-002 absent ($($requiredFile.Label)): $($requiredFile.Path)"
}

$adrContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $adrPath
$adrIndexContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $adrIndexPath
$specificationContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $specificationPath
$journalContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $journalPath

foreach ($marker in @(
    "# ADR-019 - API orchestratrice FastAPI et Uvicorn",
    "**Statut :** Acceptée",
    "FastAPI",
    "Uvicorn",
    "application ASGI",
    "composition root",
    "routeur conditionnel partagé",
    "service locator",
    "migration progressive",
    "aucune migration big bang",
    "pyproject.toml",
    "uv.lock",
    "ADR-018"
)) {
    Assert-Contains -Content $adrContent -Expected $marker -Message "ADR-019 incomplète: $marker"
}

Assert-Contains `
    -Content $adrIndexContent `
    -Expected "[ADR-019](ADR-019-api-orchestratrice-fastapi-uvicorn.md)" `
    -Message "ADR-019 absente de l'index canonique."
Assert-Contains `
    -Content $adrIndexContent `
    -Expected "Prochaine ADR technique: ADR-026" `
    -Message "Prochain numéro ADR technique non actualisé."

foreach ($marker in @(
    "# Spécification M13-FastAPI - API orchestratrice ASGI",
    "Given l'API orchestratrice est aujourd'hui servie par un routeur conditionnel partagé",
    "When la décision de frontière HTTP est publiée",
    "Then le framework, le serveur, la composition, les responsabilités interdites et la stratégie de migration sont explicites et vérifiables",
    "FastAPI",
    "Uvicorn",
    "application ASGI",
    "composition root",
    "app/platform",
    "adaptateurs HTTP autorisés",
    "aucune logique métier",
    "aucun fallback silencieux",
    "aucun service locator",
    "migration progressive",
    "pyproject.toml",
    "uv.lock",
    "HTTP_FRAMEWORK_IMPORT_FORBIDDEN"
)) {
    Assert-Contains -Content $specificationContent -Expected $marker -Message "Spécification M13-FastAPI incomplète: $marker"
}

foreach ($marker in @(
    "## T-002 - Frontière HTTP publique",
    "Statut: IMPLÉMENTÉE",
    "ADR-019",
    "test(architecture): couvrir frontiere asgi orchestratrice",
    "docs(architecture): decider fastapi uvicorn ADR-019"
)) {
    Assert-Contains -Content $journalContent -Expected $marker -Message "Journal T-002 incomplet: $marker"
}

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $validatorOutput = & powershell -NoProfile -ExecutionPolicy Bypass -File $validatorPath 2>&1
    $validatorExitCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
}

$joinedValidatorOutput = $validatorOutput -join "`n"
Assert-Condition `
    -Condition ($validatorExitCode -eq 0) `
    -Message "Validateur M13-FastAPI RED. Code: $validatorExitCode. Sortie: $joinedValidatorOutput"
Assert-Contains `
    -Content $joinedValidatorOutput `
    -Expected "Spécification M13-FastAPI valide" `
    -Message "Le validateur M13-FastAPI n'annonce pas son succès."

Write-Host "Test d'acceptation de spécification M13-FastAPI: OK"
