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

    if ($normalizedPath -match '^app/[^/]+/adapters/http(?:/|\.py$)') {
        return $true
    }

    $explicitHttpAdapterPaths = @(
        "app/source_processing/adapters/query_http.py",
        "app/source_processing/adapters/original_http.py"
    )
    foreach ($explicitPath in $explicitHttpAdapterPaths) {
        if ($normalizedPath.Equals($explicitPath, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }

    return $false
}

Assert-Condition `
    -Condition (Test-HttpFrameworkImportAllowed -RelativePath "app/platform/http/orchestrator_api.py") `
    -Message "Un adaptateur HTTP de platform doit pouvoir importer FastAPI/Uvicorn."
Assert-Condition `
    -Condition (Test-HttpFrameworkImportAllowed -RelativePath "app/source_processing/adapters/http/document_http.py") `
    -Message "Un adaptateur HTTP explicite de bounded context doit pouvoir importer FastAPI/Uvicorn."
Assert-Condition `
    -Condition (Test-HttpFrameworkImportAllowed -RelativePath "app/source_processing/adapters/query_http.py") `
    -Message "L'adaptateur HTTP SP des read-models doit pouvoir importer FastAPI/Uvicorn."
Assert-Condition `
    -Condition (Test-HttpFrameworkImportAllowed -RelativePath "app/source_processing/adapters/original_http.py") `
    -Message "L'adaptateur HTTP SP de l'original doit pouvoir importer FastAPI/Uvicorn."
Assert-Condition `
    -Condition (-not (Test-HttpFrameworkImportAllowed -RelativePath "app/source_processing/adapters/postgres_document_persistence.py")) `
    -Message "Un adaptateur SP non HTTP ne doit pas pouvoir importer FastAPI/Uvicorn."
Assert-Condition `
    -Condition (-not (Test-HttpFrameworkImportAllowed -RelativePath "app/knowledge/adapters/query_http.py")) `
    -Message "Le nom query_http.py ne doit pas créer une autorisation générique intercontexte."
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
