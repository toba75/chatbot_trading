$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_adr_system.ps1"
$adrSourceDir = Join-Path $repoRoot "docs/adr"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m000_adr_acceptance_" + [System.Guid]::NewGuid().ToString("N"))

function New-TemporaryProject {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    $projectRoot = Join-Path $temporaryRoot $Name
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "scripts") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/specs") -Force | Out-Null
    Copy-Item -LiteralPath $validatorPath -Destination (Join-Path $projectRoot "scripts/validate_adr_system.ps1")
    Copy-Item -LiteralPath $adrSourceDir -Destination (Join-Path $projectRoot "docs/adr") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md") -Destination (Join-Path $projectRoot "docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md")
    return $projectRoot
}

function Invoke-Validator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot
    )

    $scriptPath = Join-Path $ProjectRoot "scripts/validate_adr_system.ps1"
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $scriptPath 2>&1
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    return [pscustomobject] @{
        ExitCode = $LASTEXITCODE
        Output = ($output -join "`n")
    }
}

function Assert-ExitCode {
    param(
        [Parameter(Mandatory = $true)]
        [int] $Actual,

        [Parameter(Mandatory = $true)]
        [int] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if ($Actual -ne $Expected) {
        throw "$Message Code obtenu: $Actual"
    }
}

function Initialize-GitBaseline {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot
    )

    & git -C $ProjectRoot init -b master 2>$null | Out-Null
    & git -C $ProjectRoot -c core.autocrlf=false -c user.email="m000@example.test" -c user.name="M000" add . 2>$null | Out-Null
    & git -C $ProjectRoot -c core.autocrlf=false -c user.email="m000@example.test" -c user.name="M000" commit -m "baseline adr" 2>$null | Out-Null
}

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur ADR absent: scripts/validate_adr_system.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    # Given la spécification v4.1 liste les décisions techniques et DDD structurantes.
    # When la validation du registre ADR est exécutée.
    # Then chaque ADR versionnée respecte le format attendu, apparaît dans l'index et correspond à une décision référencée ou explicitement ajoutée.
    $validProjectRoot = New-TemporaryProject -Name "valid"
    $validResult = Invoke-Validator -ProjectRoot $validProjectRoot
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Le registre ADR canonique complet doit être accepté."

    $missingIndexProjectRoot = New-TemporaryProject -Name "missing-index"
    $indexPath = Join-Path $missingIndexProjectRoot "docs/adr/index.md"
    (Get-Content -Raw -Encoding UTF8 -LiteralPath $indexPath).Replace("](ADR-001-artefacts-canoniques.md)", "](ADR-001-artefacts-canoniques-manquante.md)") |
        Set-Content -Encoding UTF8 -LiteralPath $indexPath
    $missingIndexResult = Invoke-Validator -ProjectRoot $missingIndexProjectRoot
    Assert-ExitCode -Actual $missingIndexResult.ExitCode -Expected 1 -Message "Une ADR absente de l'index canonique doit être refusée."

    $unknownStatusProjectRoot = New-TemporaryProject -Name "unknown-status"
    $adrPath = Join-Path $unknownStatusProjectRoot "docs/adr/ADR-001-artefacts-canoniques.md"
    (Get-Content -Raw -Encoding UTF8 -LiteralPath $adrPath) -replace "\*\*Statut\s*:\*\*\s*.+", "**Statut :** Indecise" |
        Set-Content -Encoding UTF8 -LiteralPath $adrPath
    $unknownStatusResult = Invoke-Validator -ProjectRoot $unknownStatusProjectRoot
    Assert-ExitCode -Actual $unknownStatusResult.ExitCode -Expected 1 -Message "Un statut ADR non autorisé doit être refusé."

    $missingDecisionProjectRoot = New-TemporaryProject -Name "missing-section-3-decision"
    $specPath = Join-Path $missingDecisionProjectRoot "docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md"
    (Get-Content -Raw -Encoding UTF8 -LiteralPath $specPath).Replace("## ADR DDD structurantes", "### ADR-011 - Decision structurante non materialisee`n`n## ADR DDD structurantes") |
        Set-Content -Encoding UTF8 -LiteralPath $specPath
    $missingDecisionResult = Invoke-Validator -ProjectRoot $missingDecisionProjectRoot
    Assert-ExitCode -Actual $missingDecisionResult.ExitCode -Expected 1 -Message "Une décision structurante de la section 3 sans ADR matérialisée doit être refusée."

    $acceptedDecisionChangeProjectRoot = New-TemporaryProject -Name "accepted-decision-change"
    Initialize-GitBaseline -ProjectRoot $acceptedDecisionChangeProjectRoot
    $acceptedAdrPath = Join-Path $acceptedDecisionChangeProjectRoot "docs/adr/ADR-001-artefacts-canoniques.md"
    $acceptedAdrLines = [System.Collections.Generic.List[string]] (Get-Content -Encoding UTF8 -LiteralPath $acceptedAdrPath)
    $decisionHeadingIndex = -1
    $nextHeadingIndex = -1
    for ($index = 0; $index -lt $acceptedAdrLines.Count; $index++) {
        if ($acceptedAdrLines[$index] -match "^## D.cision$") {
            $decisionHeadingIndex = $index
            continue
        }

        if (($decisionHeadingIndex -ge 0) -and ($index -gt $decisionHeadingIndex) -and ($acceptedAdrLines[$index] -match "^##\s+")) {
            $nextHeadingIndex = $index
            break
        }
    }

    if (($decisionHeadingIndex -lt 0) -or ($nextHeadingIndex -lt 0)) {
        throw "Section Décision introuvable dans la fixture ADR."
    }

    $modifiedAdrLines = New-Object System.Collections.Generic.List[string]
    for ($index = 0; $index -le $decisionHeadingIndex; $index++) {
        $modifiedAdrLines.Add($acceptedAdrLines[$index])
    }
    $modifiedAdrLines.Add("")
    $modifiedAdrLines.Add("La decision acceptee est modifiee sans ADR remplacante.")
    for ($index = $nextHeadingIndex; $index -lt $acceptedAdrLines.Count; $index++) {
        $modifiedAdrLines.Add($acceptedAdrLines[$index])
    }
    Set-Content -Encoding UTF8 -LiteralPath $acceptedAdrPath -Value $modifiedAdrLines
    $acceptedDecisionChangeResult = Invoke-Validator -ProjectRoot $acceptedDecisionChangeProjectRoot
    Assert-ExitCode -Actual $acceptedDecisionChangeResult.ExitCode -Expected 1 -Message "Une ADR acceptée modifiée dans sa décision sans remplacement explicite doit être refusée."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Test d'acceptation du registre ADR canonique: OK"
