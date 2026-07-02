$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m009_specification.ps1"
$specPath = Join-Path $repoRoot "docs/specs/m009_recherche_approfondie_multi_sources.md"

$missingArtifacts = @()

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    $missingArtifacts += "scripts/validate_m009_specification.ps1"
}

if (-not (Test-Path -LiteralPath $specPath -PathType Leaf)) {
    $missingArtifacts += "docs/specs/m009_recherche_approfondie_multi_sources.md"
}

if ($missingArtifacts.Count -gt 0) {
    throw "Contrat exécutable M-009 absent: $($missingArtifacts -join ', ')"
}

# Given la mission M-009 est d'analyser plusieurs sources sans effacer nuances, limites et contradictions.
# When la spécification de recherche approfondie est publiée.
# Then chaque comportement M-009 nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.
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

Write-Host "Test d'acceptation de la spécification M-009: OK"
