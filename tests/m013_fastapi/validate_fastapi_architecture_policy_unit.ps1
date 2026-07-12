$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$appRoot = Join-Path $repoRoot "app"

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

function Test-HttpFrameworkImportAllowed {
    param(
        [Parameter(Mandatory = $true)]
        [string] $RelativePath
    )

    $normalizedPath = $RelativePath.Replace("\", "/")
    if ($normalizedPath.StartsWith("app/platform/", [System.StringComparison]::OrdinalIgnoreCase)) {
        return $true
    }

    return $normalizedPath -match '^app/[^/]+/adapters/http(?:/|\.py$)'
}

Assert-Condition `
    -Condition (Test-HttpFrameworkImportAllowed -RelativePath "app/platform/http/orchestrator_api.py") `
    -Message "Un adaptateur HTTP de platform doit pouvoir importer FastAPI/Uvicorn."
Assert-Condition `
    -Condition (Test-HttpFrameworkImportAllowed -RelativePath "app/source_processing/adapters/http/document_http.py") `
    -Message "Un adaptateur HTTP explicite de bounded context doit pouvoir importer FastAPI/Uvicorn."
Assert-Condition `
    -Condition (-not (Test-HttpFrameworkImportAllowed -RelativePath "app/source_processing/domain/document.py")) `
    -Message "Le domaine ne doit jamais importer FastAPI/Uvicorn."
Assert-Condition `
    -Condition (-not (Test-HttpFrameworkImportAllowed -RelativePath "app/knowledge/application/search_knowledge.py")) `
    -Message "La couche application ne doit jamais importer FastAPI/Uvicorn."

$forbiddenImports = @()
$frameworkImportPattern = '(?m)^\s*(?:from\s+(?:fastapi|uvicorn)(?:\.|\s)|import\s+(?:fastapi|uvicorn)(?:\.|\s|$))'
foreach ($pythonFile in Get-ChildItem -LiteralPath $appRoot -Recurse -File -Filter "*.py") {
    $relativePath = $pythonFile.FullName.Substring($repoRoot.Length).TrimStart("\", "/").Replace("\", "/")
    $content = Get-Content -Raw -Encoding UTF8 -LiteralPath $pythonFile.FullName
    if ($content -match $frameworkImportPattern -and -not (Test-HttpFrameworkImportAllowed -RelativePath $relativePath)) {
        $forbiddenImports += $relativePath
    }
}

Assert-Condition `
    -Condition ($forbiddenImports.Count -eq 0) `
    -Message "HTTP_FRAMEWORK_IMPORT_FORBIDDEN: import FastAPI/Uvicorn hors app/platform ou adaptateur HTTP autorisé: $($forbiddenImports -join ', ')"

Write-Host "Tests unitaires de politique d'architecture FastAPI/Uvicorn: OK"
