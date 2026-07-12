param(
    [Parameter(Mandatory = $false)]
    [string] $SpecificationPath,

    [Parameter(Mandatory = $false)]
    [string] $AdrPath,

    [Parameter(Mandatory = $false)]
    [string] $AdrIndexPath
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$expectedAdr018Sha256 = "4FDA78DF7ACC0D0A5C31E9ECA419515029E0A2876A839FF707337F3D03D72992"

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

function Resolve-RepositoryFile {
    param(
        [string] $CandidatePath,
        [Parameter(Mandatory = $true)]
        [string] $DefaultRelativePath,
        [Parameter(Mandatory = $true)]
        [string] $Label
    )

    if ([string]::IsNullOrWhiteSpace($CandidatePath)) {
        $fullPath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $DefaultRelativePath))
    }
    elseif ([System.IO.Path]::IsPathRooted($CandidatePath)) {
        $fullPath = [System.IO.Path]::GetFullPath($CandidatePath)
    }
    else {
        $fullPath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $CandidatePath))
    }

    $repositoryPrefix = $repoRoot.TrimEnd("\", "/") + [System.IO.Path]::DirectorySeparatorChar
    Assert-Condition `
        -Condition $fullPath.StartsWith($repositoryPrefix, [System.StringComparison]::OrdinalIgnoreCase) `
        -Message "Chemin hors dépôt interdit ($Label): $fullPath"
    Assert-Condition `
        -Condition (Test-Path -LiteralPath $fullPath -PathType Leaf) `
        -Message "Fichier requis absent ($Label): $fullPath"
    return $fullPath
}

function Assert-Markers {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,
        [Parameter(Mandatory = $true)]
        [string[]] $Markers,
        [Parameter(Mandatory = $true)]
        [string] $Label
    )

    foreach ($marker in $Markers) {
        Assert-Condition -Condition $Content.Contains($marker) -Message "$Label incomplet: $marker"
    }
}

$resolvedSpecificationPath = Resolve-RepositoryFile `
    -CandidatePath $SpecificationPath `
    -DefaultRelativePath "docs/specs/m013_fastapi_api_orchestratrice.md" `
    -Label "spécification"
$resolvedAdrPath = Resolve-RepositoryFile `
    -CandidatePath $AdrPath `
    -DefaultRelativePath "docs/adr/ADR-019-api-orchestratrice-fastapi-uvicorn.md" `
    -Label "ADR-019"
$resolvedAdrIndexPath = Resolve-RepositoryFile `
    -CandidatePath $AdrIndexPath `
    -DefaultRelativePath "docs/adr/index.md" `
    -Label "index ADR"
$adr018Path = Resolve-RepositoryFile `
    -DefaultRelativePath "docs/adr/ADR-018-ui-exclusivement-via-api-orchestratrice.md" `
    -Label "ADR-018"

$specificationContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedSpecificationPath
$adrContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedAdrPath
$adrIndexContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedAdrIndexPath

Assert-Markers -Label "Spécification M13-FastAPI" -Content $specificationContent -Markers @(
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
    "aucun service locator",
    "aucun fallback silencieux",
    "migration progressive",
    "HTTP_FRAMEWORK_IMPORT_FORBIDDEN",
    "pyproject.toml",
    "uv.lock"
)

Assert-Markers -Label "ADR-019" -Content $adrContent -Markers @(
    "**Statut :** Acceptée",
    "FastAPI",
    "Uvicorn",
    "application ASGI",
    "composition root",
    "service locator",
    "migration progressive",
    "aucune migration big bang",
    "ADR-018",
    "pyproject.toml",
    "uv.lock"
)

Assert-Markers -Label "Index ADR" -Content $adrIndexContent -Markers @(
    "[ADR-019](ADR-019-api-orchestratrice-fastapi-uvicorn.md)",
    "Prochaine ADR technique: ADR-024"
)

$actualAdr018Sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $adr018Path).Hash
Assert-Condition `
    -Condition ($actualAdr018Sha256 -eq $expectedAdr018Sha256) `
    -Message "ADR-018 a été modifiée alors que T-002 doit la conserver inchangée."

Write-Host "Spécification M13-FastAPI valide: FastAPI, Uvicorn, composition ASGI, frontières DDD et migration progressive contrôlés."
