$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m005_specification.ps1"
$specPath = Join-Path $repoRoot "docs/specs/m005_projection_connaissance_recherchable.md"

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur de spécification M-005 absent: scripts/validate_m005_specification.ps1"
}

if (-not (Test-Path -LiteralPath $specPath -PathType Leaf)) {
    throw "Spécification M-005 absente: docs/specs/m005_projection_connaissance_recherchable.md"
}

# Given une version canonique M-004 publiée.
# When la spécification M-005 est publiée.
# Then chaque comportement de projection et recherche nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.
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

Write-Host "Test d'acceptation de la spécification M-005: OK"
