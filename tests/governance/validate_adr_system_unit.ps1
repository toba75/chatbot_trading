$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_adr_system.ps1"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m000_adr_unit_" + [System.Guid]::NewGuid().ToString("N"))
$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8
$cCedilla = [char] 0x00E7

function New-AdrContent {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Id,

        [Parameter(Mandatory = $true)]
        [string] $Title,

        [Parameter(Mandatory = $true)]
        [string] $Status
    )

    return @"
# $Id - $Title

**Statut :** $Status
**Date :** 2026-06-21
**D$($eAcute)cideurs :** OSTrading
**Remplace :** Aucun
**Remplac$($eAcute)e par :** Aucune
**Source :** `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, section 3, $Id

## Contexte

Contexte de test.

## D$($eAcute)cision

Decision de test.

## Cons$($eAcute)quences

Consequences de test.

## Impact d'impl$($eAcute)mentation

- Modules concernes: gouvernance.
- Configuration concern$($eAcute)e: aucune.
- Tests attendus: tests de gouvernance.
- Milestones concern$($eAcute)es: M-000.

## Liens de tra$($cCedilla)abilit$($eAcute)

- Specification: section 3.
- Plan d'impl$($eAcute)mentation: M-000.
- Tests d'acceptation: tests/governance/validate_adr_system_acceptance.ps1.
- Commits: a renseigner.
"@
}

function New-TemporaryProject {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    $projectRoot = Join-Path $temporaryRoot $Name
    $scriptDir = Join-Path $projectRoot "scripts"
    $adrDir = Join-Path $projectRoot "docs/adr"
    $specDir = Join-Path $projectRoot "docs/specs"

    New-Item -ItemType Directory -Path $scriptDir -Force | Out-Null
    New-Item -ItemType Directory -Path $adrDir -Force | Out-Null
    New-Item -ItemType Directory -Path $specDir -Force | Out-Null

    Copy-Item -LiteralPath $validatorPath -Destination (Join-Path $scriptDir "validate_adr_system.ps1")
    "README ADR" | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $adrDir "README.md")
    "TEMPLATE ADR" | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $adrDir "TEMPLATE.md")

    New-AdrContent -Id "ADR-001" -Title "Artefacts canoniques" -Status "Accept$($eAcute)e" |
        Set-Content -Encoding UTF8 -LiteralPath (Join-Path $adrDir "ADR-001-artefacts-canoniques.md")
    New-AdrContent -Id "DDD-ADR-001" -Title "Monolithe modulaire" -Status "Accept$($eAcute)e" |
        Set-Content -Encoding UTF8 -LiteralPath (Join-Path $adrDir "DDD-ADR-001-monolithe-modulaire.md")

    @"
# Index des ADR

## ADR techniques

| ADR | Titre | Statut | Date | Remplace | Remplac$($eAcute)e par |
|---|---|---|---|---|---|
| [ADR-001](ADR-001-artefacts-canoniques.md) | Artefacts canoniques | Accept$($eAcute)e | 2026-06-21 | Aucun | Aucune |

## ADR DDD

| ADR | Titre | Statut | Date | Remplace | Remplac$($eAcute)e par |
|---|---|---|---|---|---|
| [DDD-ADR-001](DDD-ADR-001-monolithe-modulaire.md) | Monolithe modulaire | Accept$($eAcute)e | 2026-06-21 | Aucun | Aucune |

## Prochains num$($eAcute)ros disponibles

```text
Prochaine ADR technique: ADR-002
Prochaine DDD-ADR: DDD-ADR-002
```

## R$($eGrave)gles de maintenance

- Ajouter chaque nouvelle ADR dans le tableau de sa famille.
"@ | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $adrDir "index.md")

    @'
# 3. Decisions d'architecture consolidees

## ADR techniques

### ADR-001 - Artefacts canoniques

## ADR DDD structurantes

### DDD-ADR-001 - Monolithe modulaire

# 4. Suite
'@ | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $specDir "specification_unifiee_ddd_technique_chatbot_trading_v4_1.md")

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
    $missingMasterProjectRoot = New-TemporaryProject -Name "missing-master"
    $missingMasterResult = Invoke-Validator -ProjectRoot $missingMasterProjectRoot
    Assert-ExitCode -Actual $missingMasterResult.ExitCode -Expected 1 -Message "Un registre ADR valide sans reference master doit echouer explicitement."
    Assert-OutputContains -Output $missingMasterResult.Output -Expected "master indisponible" -Message "L'absence de master doit etre nommee."

    $validProjectRoot = New-TemporaryProject -Name "valid"
    Initialize-GitBaseline -ProjectRoot $validProjectRoot
    $validResult = Invoke-Validator -ProjectRoot $validProjectRoot
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Un registre ADR minimal et complet doit etre accepte."

    $invalidNameProjectRoot = New-TemporaryProject -Name "invalid-name"
    Rename-Item -LiteralPath (Join-Path $invalidNameProjectRoot "docs/adr/ADR-001-artefacts-canoniques.md") -NewName "ADR-01-artefacts-canoniques.md"
    $invalidNameResult = Invoke-Validator -ProjectRoot $invalidNameProjectRoot
    Assert-ExitCode -Actual $invalidNameResult.ExitCode -Expected 1 -Message "Un nom ADR hors format doit etre refuse."

    $invalidDddNameProjectRoot = New-TemporaryProject -Name "invalid-ddd-name"
    Rename-Item -LiteralPath (Join-Path $invalidDddNameProjectRoot "docs/adr/DDD-ADR-001-monolithe-modulaire.md") -NewName "DDD-ADR-01-monolithe-modulaire.md"
    $invalidDddNameResult = Invoke-Validator -ProjectRoot $invalidDddNameProjectRoot
    Assert-ExitCode -Actual $invalidDddNameResult.ExitCode -Expected 1 -Message "Un nom DDD-ADR hors format doit etre refuse."

    $invalidStatusProjectRoot = New-TemporaryProject -Name "invalid-status"
    $adrPath = Join-Path $invalidStatusProjectRoot "docs/adr/ADR-001-artefacts-canoniques.md"
    (Get-Content -Raw -Encoding UTF8 -LiteralPath $adrPath) -replace "\*\*Statut\s*:\*\*\s*.+", "**Statut :** Indecise" |
        Set-Content -Encoding UTF8 -LiteralPath $adrPath
    $invalidStatusResult = Invoke-Validator -ProjectRoot $invalidStatusProjectRoot
    Assert-ExitCode -Actual $invalidStatusResult.ExitCode -Expected 1 -Message "Un statut ADR non autorise doit etre refuse."

    $missingSectionProjectRoot = New-TemporaryProject -Name "missing-section"
    $adrPath = Join-Path $missingSectionProjectRoot "docs/adr/ADR-001-artefacts-canoniques.md"
    (Get-Content -Raw -Encoding UTF8 -LiteralPath $adrPath).Replace("## D$($eAcute)cision", "## D$($eAcute)cision absente") |
        Set-Content -Encoding UTF8 -LiteralPath $adrPath
    $missingSectionResult = Invoke-Validator -ProjectRoot $missingSectionProjectRoot
    Assert-ExitCode -Actual $missingSectionResult.ExitCode -Expected 1 -Message "Une section obligatoire absente doit etre refusee."

    $brokenIndexProjectRoot = New-TemporaryProject -Name "broken-index"
    $indexPath = Join-Path $brokenIndexProjectRoot "docs/adr/index.md"
    (Get-Content -Raw -Encoding UTF8 -LiteralPath $indexPath).Replace("| [ADR-001](ADR-001-artefacts-canoniques.md) |", "| [ADR-001](ADR-001-artefacts-canoniques.md) |`n| [ADR-002](ADR-002-inexistante.md) |") |
        Set-Content -Encoding UTF8 -LiteralPath $indexPath
    $brokenIndexResult = Invoke-Validator -ProjectRoot $brokenIndexProjectRoot
    Assert-ExitCode -Actual $brokenIndexResult.ExitCode -Expected 1 -Message "Un lien d'index vers une ADR inexistante doit etre refuse."

    $replacementMismatchProjectRoot = New-TemporaryProject -Name "replacement-mismatch"
    $dddAdrPath = Join-Path $replacementMismatchProjectRoot "docs/adr/DDD-ADR-001-monolithe-modulaire.md"
    (Get-Content -Raw -Encoding UTF8 -LiteralPath $dddAdrPath).Replace("**Remplace :** Aucun", "**Remplace :** ADR-001") |
        Set-Content -Encoding UTF8 -LiteralPath $dddAdrPath
    $replacementMismatchResult = Invoke-Validator -ProjectRoot $replacementMismatchProjectRoot
    Assert-ExitCode -Actual $replacementMismatchResult.ExitCode -Expected 1 -Message "Un remplacement incoherent entre ADR et index doit etre refuse."

    $asymmetricReplacementProjectRoot = New-TemporaryProject -Name "asymmetric-replacement"
    $adr002Path = Join-Path $asymmetricReplacementProjectRoot "docs/adr/ADR-002-remplacement-asymetrique.md"
    (New-AdrContent -Id "ADR-002" -Title "Remplacement asymetrique" -Status "Accept$($eAcute)e").Replace("**Remplace :** Aucun", "**Remplace :** ADR-001") |
        Set-Content -Encoding UTF8 -LiteralPath $adr002Path
    $indexPath = Join-Path $asymmetricReplacementProjectRoot "docs/adr/index.md"
    $adr002Row = "| [ADR-002](ADR-002-remplacement-asymetrique.md) | Remplacement asymetrique | Accept$($eAcute)e | 2026-06-21 | ADR-001 | Aucune |"
    (Get-Content -Raw -Encoding UTF8 -LiteralPath $indexPath).
        Replace("| [ADR-001](ADR-001-artefacts-canoniques.md) | Artefacts canoniques | Accept$($eAcute)e | 2026-06-21 | Aucun | Aucune |", "| [ADR-001](ADR-001-artefacts-canoniques.md) | Artefacts canoniques | Accept$($eAcute)e | 2026-06-21 | Aucun | Aucune |`n$adr002Row").
        Replace("Prochaine ADR technique: ADR-002", "Prochaine ADR technique: ADR-003") |
        Set-Content -Encoding UTF8 -LiteralPath $indexPath
    $asymmetricReplacementResult = Invoke-Validator -ProjectRoot $asymmetricReplacementProjectRoot
    Assert-ExitCode -Actual $asymmetricReplacementResult.ExitCode -Expected 1 -Message "Une relation ADR Remplace non reciproque doit etre refusee."
    Assert-OutputContains -Output $asymmetricReplacementResult.Output -Expected "Relation ADR asym" -Message "La relation ADR asymetrique doit etre nommee."

    $invalidReplacementFormatProjectRoot = New-TemporaryProject -Name "invalid-replacement-format"
    $adr001Path = Join-Path $invalidReplacementFormatProjectRoot "docs/adr/ADR-001-artefacts-canoniques.md"
    (Get-Content -Raw -Encoding UTF8 -LiteralPath $adr001Path).Replace("**Remplac$($eAcute)e par :** Aucune", "**Remplac$($eAcute)e par :** ADR-002") |
        Set-Content -Encoding UTF8 -LiteralPath $adr001Path
    $adr002Path = Join-Path $invalidReplacementFormatProjectRoot "docs/adr/ADR-002-format-remplacement.md"
    (New-AdrContent -Id "ADR-002" -Title "Format remplacement" -Status "Accept$($eAcute)e").Replace("**Remplace :** Aucun", "**Remplace :** ADR-001 texte libre") |
        Set-Content -Encoding UTF8 -LiteralPath $adr002Path
    $indexPath = Join-Path $invalidReplacementFormatProjectRoot "docs/adr/index.md"
    $adr002Row = "| [ADR-002](ADR-002-format-remplacement.md) | Format remplacement | Accept$($eAcute)e | 2026-06-21 | ADR-001 | Aucune |"
    (Get-Content -Raw -Encoding UTF8 -LiteralPath $indexPath).
        Replace("| [ADR-001](ADR-001-artefacts-canoniques.md) | Artefacts canoniques | Accept$($eAcute)e | 2026-06-21 | Aucun | Aucune |", "| [ADR-001](ADR-001-artefacts-canoniques.md) | Artefacts canoniques | Accept$($eAcute)e | 2026-06-21 | Aucun | ADR-002 |`n$adr002Row").
        Replace("Prochaine ADR technique: ADR-002", "Prochaine ADR technique: ADR-003") |
        Set-Content -Encoding UTF8 -LiteralPath $indexPath
    Initialize-GitBaseline -ProjectRoot $invalidReplacementFormatProjectRoot
    $invalidReplacementFormatResult = Invoke-Validator -ProjectRoot $invalidReplacementFormatProjectRoot
    Assert-ExitCode -Actual $invalidReplacementFormatResult.ExitCode -Expected 1 -Message "Un champ Remplace avec texte libre doit etre refuse."
    Assert-OutputContains -Output $invalidReplacementFormatResult.Output -Expected "ADR invalide" -Message "Le champ Remplace mal forme doit etre nomme."

    $invalidDateProjectRoot = New-TemporaryProject -Name "invalid-date"
    $adrPath = Join-Path $invalidDateProjectRoot "docs/adr/ADR-001-artefacts-canoniques.md"
    (Get-Content -Raw -Encoding UTF8 -LiteralPath $adrPath).Replace("**Date :** 2026-06-21", "**Date :** 2026-99-99") |
        Set-Content -Encoding UTF8 -LiteralPath $adrPath
    $indexPath = Join-Path $invalidDateProjectRoot "docs/adr/index.md"
    (Get-Content -Raw -Encoding UTF8 -LiteralPath $indexPath).Replace("| Artefacts canoniques | Accept$($eAcute)e | 2026-06-21 |", "| Artefacts canoniques | Accept$($eAcute)e | 2026-99-99 |") |
        Set-Content -Encoding UTF8 -LiteralPath $indexPath
    Initialize-GitBaseline -ProjectRoot $invalidDateProjectRoot
    $invalidDateResult = Invoke-Validator -ProjectRoot $invalidDateProjectRoot
    Assert-ExitCode -Actual $invalidDateResult.ExitCode -Expected 1 -Message "Une date ADR calendaire invalide doit etre refusee."
    Assert-OutputContains -Output $invalidDateResult.Output -Expected "Date ADR invalide" -Message "La date ADR invalide doit etre nommee."

    $acceptedDecisionChangeProjectRoot = New-TemporaryProject -Name "accepted-decision-change"
    Initialize-GitBaseline -ProjectRoot $acceptedDecisionChangeProjectRoot
    $acceptedAdrPath = Join-Path $acceptedDecisionChangeProjectRoot "docs/adr/ADR-001-artefacts-canoniques.md"
    (Get-Content -Raw -Encoding UTF8 -LiteralPath $acceptedAdrPath).Replace("Decision de test.", "Decision modifiee sans ADR remplacante.") |
        Set-Content -Encoding UTF8 -LiteralPath $acceptedAdrPath
    $acceptedDecisionChangeResult = Invoke-Validator -ProjectRoot $acceptedDecisionChangeProjectRoot
    Assert-ExitCode -Actual $acceptedDecisionChangeResult.ExitCode -Expected 1 -Message "Une ADR acceptee modifiee dans sa decision doit etre refusee."

    $acceptedStatusChangeProjectRoot = New-TemporaryProject -Name "accepted-status-change"
    Initialize-GitBaseline -ProjectRoot $acceptedStatusChangeProjectRoot
    $acceptedAdrPath = Join-Path $acceptedStatusChangeProjectRoot "docs/adr/ADR-001-artefacts-canoniques.md"
    (Get-Content -Raw -Encoding UTF8 -LiteralPath $acceptedAdrPath).
        Replace("**Statut :** Accept$($eAcute)e", "**Statut :** Propos$($eAcute)e").
        Replace("Decision de test.", "Decision modifiee en changeant le statut courant.") |
        Set-Content -Encoding UTF8 -LiteralPath $acceptedAdrPath
    $indexPath = Join-Path $acceptedStatusChangeProjectRoot "docs/adr/index.md"
    (Get-Content -Raw -Encoding UTF8 -LiteralPath $indexPath).
        Replace("| [ADR-001](ADR-001-artefacts-canoniques.md) | Artefacts canoniques | Accept$($eAcute)e |", "| [ADR-001](ADR-001-artefacts-canoniques.md) | Artefacts canoniques | Propos$($eAcute)e |") |
        Set-Content -Encoding UTF8 -LiteralPath $indexPath
    $acceptedStatusChangeResult = Invoke-Validator -ProjectRoot $acceptedStatusChangeProjectRoot
    Assert-ExitCode -Actual $acceptedStatusChangeResult.ExitCode -Expected 1 -Message "Une ADR acceptee dans master doit rester protegee meme si son statut courant change."
    Assert-OutputContains -Output $acceptedStatusChangeResult.Output -Expected "modifi" -Message "La modification de decision doit etre nommee."

    $missingDecisionProjectRoot = New-TemporaryProject -Name "missing-section-3-decision"
    Initialize-GitBaseline -ProjectRoot $missingDecisionProjectRoot
    $specPath = Join-Path $missingDecisionProjectRoot "docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md"
    (Get-Content -Raw -Encoding UTF8 -LiteralPath $specPath).Replace("# 4. Suite", "### DDD-ADR-002 - Cycle manquant`n`n# 4. Suite") |
        Set-Content -Encoding UTF8 -LiteralPath $specPath
    $missingDecisionResult = Invoke-Validator -ProjectRoot $missingDecisionProjectRoot
    Assert-ExitCode -Actual $missingDecisionResult.ExitCode -Expected 1 -Message "Une decision de la section 3 sans ADR materialisee doit etre refusee."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Tests unitaires du validateur ADR: OK"
