param(
    [Parameter(Mandatory = $false)]
    [string] $ComposePath,

    [Parameter(Mandatory = $false)]
    [string] $TopologyPath,

    [Parameter(Mandatory = $false)]
    [string] $SparkFirewallPath,

    [Parameter(Mandatory = $false)]
    [string] $ApplicationConfigPath
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonValidatorPath = Join-Path $PSScriptRoot "validate_network_boundary.py"
$pythonPreflightPath = Join-Path $PSScriptRoot "require_python.ps1"

if (-not (Test-Path -LiteralPath $pythonValidatorPath -PathType Leaf)) {
    throw "Validateur Python absent: scripts/validate_network_boundary.py"
}

if (-not (Test-Path -LiteralPath $pythonPreflightPath -PathType Leaf)) {
    throw "Préflight Python absent: scripts/require_python.ps1"
}

if (-not $PSBoundParameters.ContainsKey("ComposePath")) {
    $ComposePath = Join-Path $repoRoot "deploy/local-compose/compose.yaml"
}

if (-not $PSBoundParameters.ContainsKey("TopologyPath")) {
    $TopologyPath = Join-Path $repoRoot "app/platform/topology_registry.json"
}

if (-not $PSBoundParameters.ContainsKey("SparkFirewallPath")) {
    $SparkFirewallPath = Join-Path $repoRoot "deploy/spark-firewall/network-boundary.json"
}

if (-not $PSBoundParameters.ContainsKey("ApplicationConfigPath")) {
    $ApplicationConfigPath = Join-Path $repoRoot "config/application.example.yaml"
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
    --compose-path $ComposePath `
    --topology-path $TopologyPath `
    --spark-firewall-path $SparkFirewallPath `
    --application-config-path $ApplicationConfigPath `
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
