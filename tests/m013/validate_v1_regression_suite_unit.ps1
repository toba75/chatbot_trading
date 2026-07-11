$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m013_regression.ps1"
$temporaryRoot = Join-Path $repoRoot (".tmp_m013_regression_unit_" + [System.Guid]::NewGuid().ToString("N"))

function Invoke-Validator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot
    )

    $suitePath = Join-Path $ProjectRoot "docs/evaluation/m013/v1_regression_suite.json"
    $decisionsPath = Join-Path $ProjectRoot "docs/governance/m013_v1_gap_decisions.md"
    $sourceGapReportPath = Join-Path $ProjectRoot "docs/governance/m012_v1_gap_report.md"
    $matrixPath = Join-Path $ProjectRoot "docs/traceability/matrix.md"
    $testGatePath = Join-Path $ProjectRoot "scripts/test.ps1"
    $lintGatePath = Join-Path $ProjectRoot "scripts/lint.ps1"

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File $validatorPath `
            -SuitePath $suitePath `
            -DecisionsPath $decisionsPath `
            -SourceGapReportPath $sourceGapReportPath `
            -MatrixPath $matrixPath `
            -TestGatePath $testGatePath `
            -LintGatePath $lintGatePath 2>&1
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    return [pscustomobject] @{
        ExitCode = $LASTEXITCODE
        Output = ($output -join "`n")
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

function New-FixtureProject {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    $projectRoot = Join-Path $temporaryRoot $Name
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/evaluation/m013") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/evaluation/m012") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/governance") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/traceability") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "scripts") -Force | Out-Null

    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/evaluation/m013/v1_regression_suite.json") -Destination (Join-Path $projectRoot "docs/evaluation/m013/v1_regression_suite.json")
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/evaluation/m012") -Destination (Join-Path $projectRoot "docs/evaluation") -Recurse -Force
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/governance/m013_v1_gap_decisions.md") -Destination (Join-Path $projectRoot "docs/governance/m013_v1_gap_decisions.md")
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/governance/m012_v1_gap_report.md") -Destination (Join-Path $projectRoot "docs/governance/m012_v1_gap_report.md")
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/traceability/matrix.md") -Destination (Join-Path $projectRoot "docs/traceability/matrix.md")
    Copy-Item -LiteralPath (Join-Path $repoRoot "scripts/test.ps1") -Destination (Join-Path $projectRoot "scripts/test.ps1")
    Copy-Item -LiteralPath (Join-Path $repoRoot "scripts/lint.ps1") -Destination (Join-Path $projectRoot "scripts/lint.ps1")

    return $projectRoot
}

function Assert-ValidatorFails {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $true)]
        [scriptblock] $Mutate,

        [Parameter(Mandatory = $true)]
        [string] $ExpectedMessage
    )

    $projectRoot = New-FixtureProject -Name $Name
    & $Mutate $projectRoot
    $result = Invoke-Validator -ProjectRoot $projectRoot

    if ($result.ExitCode -eq 0) {
        throw "Le cas RED $Name doit échouer."
    }

    Assert-OutputContains `
        -Output $result.Output `
        -Expected $ExpectedMessage `
        -Message "Le cas RED $Name doit nommer la règle violée."
}

function Remove-TemporaryRoot {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    for ($attempt = 1; $attempt -le 5; $attempt++) {
        try {
            Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
            return
        }
        catch {
            if ($attempt -eq 5) {
                throw
            }
            Start-Sleep -Milliseconds (200 * $attempt)
        }
    }
}

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur de régression V1 M-013 absent: scripts/validate_m013_regression.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $validProjectRoot = New-FixtureProject -Name "valid"
    $validResult = Invoke-Validator -ProjectRoot $validProjectRoot
    if ($validResult.ExitCode -ne 0) {
        throw "La fixture valide T-004 doit réussir. Sortie: $($validResult.Output)"
    }
    Assert-OutputContains `
        -Output $validResult.Output `
        -Expected "Suite de régression V1 M-013 valide" `
        -Message "La fixture valide doit annoncer le GREEN T-004."

    Assert-ValidatorFails `
        -Name "critere-non-couvert" `
        -ExpectedMessage "critère non couvert: V1-CV-CONVERSATION-PRODUIT" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/evaluation/m013/v1_regression_suite.json"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("V1-CV-CONVERSATION-PRODUIT", "V1-CV-CONVERSATION-ABSENTE") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "commande-manquante" `
        -ExpectedMessage "commande manquante: V1-EX-BACKTESTS-REPRODUCTIBLES" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/evaluation/m013/v1_regression_suite.json"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("powershell -NoProfile -ExecutionPolicy Bypass -File .\\tests\\m011\\validate_experiment_reproducibility_acceptance.ps1", "") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "fixture-non-declaree" `
        -ExpectedMessage "fixture non déclarée: FIX-M013-CV-INCONNUE" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/evaluation/m013/v1_regression_suite.json"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path) -replace '("journey_id": "V1-PARCOURS-CONVERSATION"[\s\S]*?"fixture_id": ")FIX-M013-CV-CONVERSATION-0001', '$1FIX-M013-CV-INCONNUE' |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "contrat-interne" `
        -ExpectedMessage "dépendance directe à un stockage interne" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/evaluation/m013/v1_regression_suite.json"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("app/contracts/source_references.py", "app/source_processing/adapters/in_memory_source_repository.py") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "resultat-sans-preuve" `
        -ExpectedMessage "résultat sans preuve: V1-CV-CONVERSATION-PRODUIT" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/evaluation/m013/v1_regression_suite.json"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path) -replace '("criterion_id": "V1-CV-CONVERSATION-PRODUIT"[\s\S]*?"evidence_marker": ")CVRUN-M012-CRITERIA-0001', '$1CVRUN-M012-ABSENT' |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "ecart-non-relie" `
        -ExpectedMessage "écart non relié: V1-KA-RECHERCHE-PAGES" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/evaluation/m013/v1_regression_suite.json"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace('"gap_decision_context": "KA"', '"gap_decision_context": "INCONNU"') |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "payload-sensible" `
        -ExpectedMessage "Payload sensible M-013 exposé: PROMPT_COMPLET_INTERDIT_M013" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/evaluation/m013/v1_regression_suite.json"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("Suite de régression V1", "PROMPT_COMPLET_INTERDIT_M013 Suite de régression V1") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }
}
finally {
    Remove-TemporaryRoot -Path $temporaryRoot
}

Write-Host "Tests unitaires T-004 suite de régression V1 M-013: OK"

