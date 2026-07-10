$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m013_config_traceability.ps1"

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
    throw "Validateur de traçabilité M13-config absent: scripts/validate_m013_config_traceability.ps1"
}

# Given M13-config a migré configuration, gateway, Compose, scans et runbooks.
# When la traçabilité M13-config est validée sur le dépôt réel.
# Then chaque exigence ADR-016 relie source, test, commande, code, documentation, audit et gate.
$output = & powershell -NoProfile -ExecutionPolicy Bypass -File $validatorPath 2>&1
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    throw "La traçabilité M13-config doit être GREEN. Code obtenu: $exitCode. Sortie: $($output -join "`n")"
}

$outputText = $output -join "`n"
Assert-OutputContains `
    -Output $outputText `
    -Expected "Traçabilité M13-config valide" `
    -Message "Le validateur M13-config doit annoncer la traçabilité validée."
Assert-OutputContains `
    -Output $outputText `
    -Expected "8 exigence(s)" `
    -Message "Le validateur M13-config doit couvrir toutes les exigences ADR-016."
Assert-OutputContains `
    -Output $outputText `
    -Expected "V1 non acceptée" `
    -Message "Le validateur M13-config doit rappeler que la V1 complète n'est pas acceptée."

if ($outputText.Contains("Ã")) {
    throw "La sortie de traçabilité M13-config contient du mojibake."
}

Write-Host "Test d'acceptation T-008 traçabilité M13-config: OK"
