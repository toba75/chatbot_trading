param(
    [Parameter(Mandatory = $false)]
    [string] $AcceptanceTestPath
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

$defaultAcceptanceTestPaths = @(
    "tests/m013/validate_m013_reality_product_unit.ps1",
    "tests/m013/validate_llm_gateway_real_spark_acceptance.ps1",
    "tests/m013/validate_m013_reality_product_acceptance.ps1"
)
$requiredTraceabilityPaths = @(
    "docs/tasks/milestone_013/0013_ancrer_gateway_llm_chemin_reel.md",
    "docs/specs/m013_reality_closure.md",
    "docs/adr/ADR-015-provenance-llm-declaree-gateway.md",
    "app/platform/local_runtime.py",
    "app/platform/llm_gateway/__init__.py"
)

function Resolve-RepoPath {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Path
    }

    return (Join-Path $repoRoot $Path)
}

function Assert-RequiredFile {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    $resolvedPath = Resolve-RepoPath -Path $Path
    if (-not (Test-Path -LiteralPath $resolvedPath -PathType Leaf)) {
        throw "Fichier M13-reality requis absent: $Path"
    }

    return $resolvedPath
}

$effectiveAcceptanceTestPaths = @()
if ([string]::IsNullOrWhiteSpace($AcceptanceTestPath)) {
    $effectiveAcceptanceTestPaths = $defaultAcceptanceTestPaths
}
else {
    $effectiveAcceptanceTestPaths = @($AcceptanceTestPath)
}

foreach ($path in $requiredTraceabilityPaths) {
    Assert-RequiredFile -Path $path | Out-Null
}

foreach ($effectiveAcceptanceTestPath in $effectiveAcceptanceTestPaths) {
    $resolvedAcceptanceTestPath = Assert-RequiredFile -Path $effectiveAcceptanceTestPath
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File $resolvedAcceptanceTestPath 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0) {
        throw ($output -join "`n")
    }
}

Write-Host "Validation M13-reality chemin réel chat et LLM valide."
