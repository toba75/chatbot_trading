param(
    [Parameter(Mandatory = $true)]
    [string] $AppRoot,

    [Parameter(Mandatory = $true)]
    [string] $ContextRegistryPath,

    [Parameter(Mandatory = $true)]
    [string] $SpecificationPath
)

$ErrorActionPreference = "Stop"

$pythonValidatorPath = Join-Path $PSScriptRoot "validate_architecture_boundaries.py"

if (-not (Test-Path -LiteralPath $pythonValidatorPath -PathType Leaf)) {
    throw "Validateur Python absent: scripts/validate_architecture_boundaries.py"
}

$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$output = & python `
    -B `
    $pythonValidatorPath `
    --app-root $AppRoot `
    --context-registry-path $ContextRegistryPath `
    --specification-path $SpecificationPath `
    2>&1

$exitCode = $LASTEXITCODE
$ErrorActionPreference = $previousErrorActionPreference
foreach ($line in $output) {
    Write-Host $line
}

exit $exitCode
