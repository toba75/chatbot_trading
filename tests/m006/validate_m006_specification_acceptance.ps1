$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m006_specification.ps1"
$specPath = Join-Path $repoRoot "docs/specs/m006_claims_verifiables.md"

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur de spécification M-006 absent: scripts/validate_m006_specification.ps1"
}

if (-not (Test-Path -LiteralPath $specPath -PathType Leaf)) {
    throw "Spécification M-006 absente: docs/specs/m006_claims_verifiables.md"
}

# Given des preuves candidates KA avec SourceLocator résolvable.
# When la spécification M-006 est publiée.
# Then chaque comportement de claim nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.
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

Write-Host "Test d'acceptation de la spécification M-006: OK"
