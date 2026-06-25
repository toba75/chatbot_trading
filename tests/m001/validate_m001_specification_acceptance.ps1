$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m001_specification.ps1"
$specPath = Join-Path $repoRoot "docs/specs/m001_frontieres_ddd_contrats_publies.md"

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur M-001 absent: scripts/validate_m001_specification.ps1"
}

# Given les sept bounded contexts sont definis dans la specification v4.1.
# When la specification M-001 est publiee.
# Then chaque communication intercontexte nomme son contrat publie, son producteur,
# son consommateur et le modele interne qui reste interdit.
$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $validatorPath -Path $specPath 2>&1
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
}

if ($LASTEXITCODE -ne 0) {
    throw ($output -join "`n")
}

Write-Host "Test d'acceptation de la specification M-001: OK"
