$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m003_specification.ps1"
$specPath = Join-Path $repoRoot "docs/specs/m003_source_enregistree_diagnostiquee_routee.md"
$eAcute = [char] 0x00E9

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur de sp$($eAcute)cification M-003 absent: scripts/validate_m003_specification.ps1"
}

# Given la spécification v4.1 définit SP comme propriétaire du diagnostic et du routage documentaire.
# When la spécification M-003 est publiée.
# Then chaque comportement M-003 nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.
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

Write-Host "Test d'acceptation de la sp$($eAcute)cification M-003: OK"
