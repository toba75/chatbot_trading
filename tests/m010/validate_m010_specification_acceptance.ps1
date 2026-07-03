$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m010_specification.ps1"
$specPath = Join-Path $repoRoot "docs/specs/m010_strategie_candidate_attribuee.md"

$missingArtifacts = @()

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    $missingArtifacts += "scripts/validate_m010_specification.ps1"
}

if (-not (Test-Path -LiteralPath $specPath -PathType Leaf)) {
    $missingArtifacts += "docs/specs/m010_strategie_candidate_attribuee.md"
}

if ($missingArtifacts.Count -gt 0) {
    throw "Contrat exécutable M-010 absent: $($missingArtifacts -join ', ')"
}

# Given la mission M-010 est de formaliser une hypothèse de stratégie attribuée et vérifiable.
# When la spécification de stratégie candidate est publiée.
# Then chaque comportement M-010 nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.
$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $validatorPath -Path $specPath 2>&1
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
}

if ($LASTEXITCODE -ne 0) {
    throw "Spécification M-010 invalide. Sortie: $($output -join "`n")"
}

$joinedOutput = $output -join "`n"
if (-not $joinedOutput.Contains("Spécification M-010 valide")) {
    throw "Le validateur M-010 doit confirmer explicitement la validité de la spécification. Sortie: $joinedOutput"
}

Write-Host "Test d'acceptation de spécification M-010: OK"
