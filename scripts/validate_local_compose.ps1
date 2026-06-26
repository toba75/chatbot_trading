param(
    [Parameter(Mandatory = $false)]
    [string] $Path
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonValidatorPath = Join-Path $PSScriptRoot "validate_local_compose.py"
$pythonPreflightPath = Join-Path $PSScriptRoot "require_python.ps1"

if (-not (Test-Path -LiteralPath $pythonValidatorPath -PathType Leaf)) {
    throw "Validateur Python absent: scripts/validate_local_compose.py"
}

if (-not (Test-Path -LiteralPath $pythonPreflightPath -PathType Leaf)) {
    throw "Préflight Python absent: scripts/require_python.ps1"
}

if (-not $PSBoundParameters.ContainsKey("Path")) {
    $Path = Join-Path $repoRoot "deploy/local-compose/compose.yaml"
}

. $pythonPreflightPath
$pythonExecutable = Get-RequiredPythonExecutable

$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$output = & $pythonExecutable `
    -B `
    $pythonValidatorPath `
    --path $Path `
    2>&1

$exitCode = $LASTEXITCODE
if ($null -eq $exitCode) {
    $exitCode = 1
}
$ErrorActionPreference = $previousErrorActionPreference
foreach ($line in $output) {
    Write-Host $line
}

exit $exitCode
