$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m012_traceability.ps1"

function Assert-OutputContains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Output,

        [Parameter(Mandatory = $true)]
        [string] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if (-not $Output.Contains($Expected)) {
        throw "$Message Sortie obtenue: $Output"
    }
}

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur de traçabilité M-012 absent: scripts/validate_m012_traceability.ps1"
}

# Given M-012 a livré corpus, annotations, benchmarks, décisions et rapports.
# When la traçabilité M-012 est validée sur le dépôt réel.
# Then chaque exigence relie test, commande, artefact, ADR et écart V1 exploitable.
$output = & powershell -NoProfile -ExecutionPolicy Bypass -File $validatorPath 2>&1
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    throw "La traçabilité M-012 doit être GREEN. Code obtenu: $exitCode. Sortie: $($output -join "`n")"
}

$outputText = $output -join "`n"
Assert-OutputContains `
    -Output $outputText `
    -Expected "Traçabilité M-012 valide" `
    -Message "Le validateur M-012 doit annoncer la traçabilité validée."
Assert-OutputContains `
    -Output $outputText `
    -Expected "12 exigence(s)" `
    -Message "Le validateur M-012 doit couvrir toutes les exigences du milestone."
Assert-OutputContains `
    -Output $outputText `
    -Expected "8 écart(s) V1" `
    -Message "Le validateur M-012 doit couvrir les écarts SP, KA, EG, RA, CV, SD, LLM et EX."

if ($outputText.Contains("Ã")) {
    throw "La sortie de traçabilité M-012 contient du mojibake."
}

Write-Host "Test d'acceptation T-012 traçabilité M-012: OK"

