$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m008_specification.ps1"
$specPath = Join-Path $repoRoot "docs/specs/m008_conversation_produit.md"

$missingArtifacts = @()

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    $missingArtifacts += "scripts/validate_m008_specification.ps1"
}

if (-not (Test-Path -LiteralPath $specPath -PathType Leaf)) {
    $missingArtifacts += "docs/specs/m008_conversation_produit.md"
}

if ($missingArtifacts.Count -gt 0) {
    throw "Contrat exécutable M-008 absent: $($missingArtifacts -join ', ')"
}

# Given la mission M-008 est de permettre une conversation suivie sans preuve historique implicite.
# When la spécification de conversation produit est publiée.
# Then chaque comportement CV nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.
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

Write-Host "Test d'acceptation de la spécification M-008: OK"
