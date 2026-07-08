$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m013_antipatterns.ps1"
$temporaryRoot = Join-Path $repoRoot (".tmp_m013_antipatterns_unit_" + [System.Guid]::NewGuid().ToString("N"))

function Invoke-Validator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot
    )

    $reviewPath = Join-Path $ProjectRoot "docs/governance/m013_antipattern_review.md"
    $specificationPath = Join-Path $ProjectRoot "docs/specs/m013_durcissement_acceptation_v1.md"
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
            -ReviewPath $reviewPath `
            -SpecificationPath $specificationPath `
            -MatrixPath $matrixPath `
            -TestGatePath $testGatePath `
            -LintGatePath $lintGatePath 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    return [pscustomobject] @{
        ExitCode = $exitCode
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
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "scripts") -Force | Out-Null

    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/governance") -Destination (Join-Path $projectRoot "docs/governance") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/specs") -Destination (Join-Path $projectRoot "docs/specs") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/traceability") -Destination (Join-Path $projectRoot "docs/traceability") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "scripts/test.ps1") -Destination (Join-Path $projectRoot "scripts/test.ps1")
    Copy-Item -LiteralPath (Join-Path $repoRoot "scripts/lint.ps1") -Destination (Join-Path $projectRoot "scripts/lint.ps1")

    return $projectRoot
}

function Edit-FixtureFile {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [scriptblock] $Edit
    )

    $content = Get-Content -Raw -Encoding UTF8 -LiteralPath $Path
    $updated = & $Edit $content
    Set-Content -Encoding UTF8 -LiteralPath $Path -Value $updated
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

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur anti-patterns V1 M-013 absent: scripts/validate_m013_antipatterns.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null
try {
    # Given la revue T-011 publie les anti-patterns interdits et les questions ouvertes contrôlées.
    # When le validateur inspecte la revue, les gates et la matrice.
    # Then il refuse les absences de contrôle, revues incomplètes, questions résolues sans ADR,
    # violations réseau, fallback LLM, Qdrant autorité, historique factuel, suppression de résultats
    # négatifs, prompts persistants, checkpoint sans benchmark, contexte 256K par défaut et microservice imposé.
    $validProjectRoot = New-FixtureProject -Name "valid"
    $validResult = Invoke-Validator -ProjectRoot $validProjectRoot
    if ($validResult.ExitCode -ne 0) {
        throw "La fixture valide T-011 doit réussir. Sortie: $($validResult.Output)"
    }
    Assert-OutputContains `
        -Output $validResult.Output `
        -Expected "Anti-patterns V1 M-013 valides" `
        -Message "La fixture valide doit annoncer le GREEN T-011."

    Assert-ValidatorFails `
        -Name "antipattern-absent-de-controle" `
        -ExpectedMessage "Anti-pattern obligatoire absent: résultat négatif supprimé" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_antipattern_review.md"
            Edit-FixtureFile -Path $path -Edit { param($content) $content.Replace("Résultat négatif supprimé", "Résultat défavorable archivé") }
        }

    Assert-ValidatorFails `
        -Name "controle-absent" `
        -ExpectedMessage "Contrôle obligatoire absent: CTRL-M013-RETENTION-001" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_antipattern_review.md"
            Edit-FixtureFile -Path $path -Edit { param($content) $content.Replace("CTRL-M013-RETENTION-001", "CTRL-M013-RETENTION-SUPPRIME") }
        }

    Assert-ValidatorFails `
        -Name "revue-sans-date" `
        -ExpectedMessage "Date de revue obligatoire" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_antipattern_review.md"
            Edit-FixtureFile -Path $path -Edit { param($content) $content.Replace("Date de revue: 2026-07-08", "Date de revue: ") }
        }

    Assert-ValidatorFails `
        -Name "revue-sans-perimetre" `
        -ExpectedMessage "Périmètre de revue obligatoire" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_antipattern_review.md"
            Edit-FixtureFile -Path $path -Edit { param($content) $content.Replace("Périmètre revu: section 23", "Périmètre revu: ") }
        }

    Assert-ValidatorFails `
        -Name "revue-sans-preuve" `
        -ExpectedMessage "Preuve de revue obligatoire absente: docs/governance/m013_retention_policy.md" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_antipattern_review.md"
            Edit-FixtureFile -Path $path -Edit { param($content) $content.Replace("docs/governance/m013_retention_policy.md", "docs/governance/preuve_absente.md") }
        }

    Assert-ValidatorFails `
        -Name "question-resolue-sans-adr" `
        -ExpectedMessage "Question ouverte résolue sans ADR: Sécurité inter-hôtes" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_antipattern_review.md"
            Edit-FixtureFile -Path $path -Edit { param($content) $content.Replace("| Sécurité inter-hôtes | ouverte contrôlée | Non tranchée | ADR requise si résolution future |", "| Sécurité inter-hôtes | résolue | mTLS obligatoire | Non requise |") }
        }

    foreach ($case in @(
        @{ Name = "violation-vllm-lan"; Marker = "vLLM exposé à tout le LAN sans filtrage par adresse source"; Message = "Violation active interdite: vLLM exposé à tout le LAN sans filtrage par adresse source" },
        @{ Name = "fallback-llm"; Marker = "fallback LLM silencieux"; Message = "Violation active interdite: fallback LLM silencieux" },
        @{ Name = "qdrant-source-verite"; Marker = "Qdrant source de vérité"; Message = "Violation active interdite: Qdrant source de vérité" },
        @{ Name = "historique-conversationnel-factuel"; Marker = "historique conversationnel factuel"; Message = "Violation active interdite: historique conversationnel factuel" },
        @{ Name = "resultat-negatif-supprime"; Marker = "résultat négatif supprimé"; Message = "Violation active interdite: résultat négatif supprimé" },
        @{ Name = "prompt-complet-persistant"; Marker = "prompt complet persistant"; Message = "Violation active interdite: prompt complet persistant" },
        @{ Name = "checkpoint-quantifie-sans-benchmark"; Marker = "checkpoint quantifié sans benchmark"; Message = "Violation active interdite: checkpoint quantifié sans benchmark" },
        @{ Name = "contexte-256k-par-defaut"; Marker = "contexte 256K par défaut"; Message = "Violation active interdite: contexte 256K par défaut" },
        @{ Name = "microservice-par-contexte-impose"; Marker = "microservice par contexte imposé"; Message = "Violation active interdite: microservice par contexte imposé" }
    )) {
        Assert-ValidatorFails `
            -Name $case.Name `
            -ExpectedMessage $case.Message `
            -Mutate {
                param($projectRoot)
                $path = Join-Path $projectRoot "docs/governance/m013_antipattern_review.md"
                Add-Content -Encoding UTF8 -LiteralPath $path -Value "`nViolation active: $($case.Marker)"
            }
    }
}
finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

Write-Host "Tests unitaires du validateur anti-patterns V1 M-013: OK"

