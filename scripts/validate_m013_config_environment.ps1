param(
    [Parameter(Mandatory = $false)]
    [string] $RootPath
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonPreflightPath = Join-Path $PSScriptRoot "require_python.ps1"
$pythonValidatorPath = Join-Path $PSScriptRoot "validate_m013_config_environment.py"

if (-not (Test-Path -LiteralPath $pythonPreflightPath -PathType Leaf)) {
    throw "Préflight Python absent: scripts/require_python.ps1"
}

if (-not (Test-Path -LiteralPath $pythonValidatorPath -PathType Leaf)) {
    throw "Validateur Python absent: scripts/validate_m013_config_environment.py"
}

if ([string]::IsNullOrWhiteSpace($RootPath)) {
    $RootPath = $repoRoot
}

. $pythonPreflightPath
$pythonExecutable = Get-RequiredPythonExecutable

$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $output = & $pythonExecutable -B $pythonValidatorPath --root $RootPath 2>&1
    $exitCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
}

foreach ($line in $output) {
    Write-Host $line
}

exit $exitCode
