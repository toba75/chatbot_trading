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

$pythonCommand = $null
try {
    $pythonCommand = @(Get-Command python -CommandType Application -ErrorAction Stop)[0]
}
catch {
    throw "Python 3.10+ requis: executable python introuvable dans PATH."
}

$pythonExecutable = $pythonCommand.Source
if ([string]::IsNullOrWhiteSpace($pythonExecutable)) {
    $pythonExecutable = $pythonCommand.Path
}
if ([string]::IsNullOrWhiteSpace($pythonExecutable)) {
    throw "Python 3.10+ requis: chemin executable python introuvable."
}

$versionOutput = & $pythonExecutable -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.10+ requis: version python illisible."
}
$version = [version] ([string] $versionOutput).Trim()
if ($version -lt ([version] "3.10.0")) {
    throw "Python 3.10+ requis: version detectee $version."
}

$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$output = & $pythonExecutable `
    -B `
    $pythonValidatorPath `
    --app-root $AppRoot `
    --context-registry-path $ContextRegistryPath `
    --specification-path $SpecificationPath `
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
