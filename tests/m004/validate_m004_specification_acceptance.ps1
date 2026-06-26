$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m004_specification.ps1"
$specPath = Join-Path $repoRoot "docs/specs/m004_version_canonique_publiee.md"
$eAcute = [char] 0x00E9

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur de sp$($eAcute)cification M-004 absent: scripts/validate_m004_specification.ps1"
}

# Given une source M-003 enregistrée, diagnostiquée et routée.
# When la spécification M-004 est publiée.
# Then chaque comportement de version canonique nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.
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

Write-Host "Test d'acceptation de la sp$($eAcute)cification M-004: OK"
