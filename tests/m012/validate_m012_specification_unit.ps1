$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m012_specification.ps1"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m012_specification_unit_" + [System.Guid]::NewGuid().ToString("N"))

function New-ValidM012SpecificationContent {
    $canonicalSpecPath = Join-Path $repoRoot "docs/specs/m012_evaluation_pilote_calibration.md"
    if (-not (Test-Path -LiteralPath $canonicalSpecPath -PathType Leaf)) {
        throw "Spécification canonique M-012 absente pour le fixture unitaire: docs/specs/m012_evaluation_pilote_calibration.md"
    }

    return Get-Content -Raw -Encoding UTF8 -LiteralPath $canonicalSpecPath
}

function Invoke-M012SpecificationValidator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $SpecPath
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $validatorPath -Path $SpecPath 2>&1
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

function New-TemporarySpec {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    $specPath = Join-Path $temporaryRoot "$Name.md"
    $Content | Set-Content -Encoding UTF8 -LiteralPath $specPath
    return $specPath
}

function Assert-M012RejectedSpec {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $ExpectedOutput,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    $specPath = New-TemporarySpec -Name $Name -Content $Content
    $result = Invoke-M012SpecificationValidator -SpecPath $specPath
    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message $Message
    Assert-OutputContains -Output $result.Output -Expected $ExpectedOutput -Message "Le refus doit nommer l'écart attendu."
}

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur de spécification M-012 absent: scripts/validate_m012_specification.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $validContent = New-ValidM012SpecificationContent
    $validSpecPath = New-TemporarySpec -Name "valid" -Content $validContent
    $validResult = Invoke-M012SpecificationValidator -SpecPath $validSpecPath
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Une spécification M-012 conforme doit être acceptée."

    Assert-M012RejectedSpec `
        -Name "mission-absente" `
        -Content ($validContent.Replace("## Mission M-012", "## Mission incomplète")) `
        -ExpectedOutput "Section obligatoire absente: ## Mission M-012" `
        -Message "Une mission M-012 absente doit être refusée."

    Assert-M012RejectedSpec `
        -Name "artefacts-absents" `
        -Content ($validContent.Replace("PilotCorpus", "CorpusPilote")) `
        -ExpectedOutput "Artefact M-012 attendu absent: PilotCorpus" `
        -Message "Les artefacts d'évaluation doivent être obligatoires."

    Assert-M012RejectedSpec `
        -Name "corpus-non-borne" `
        -Content ($validContent.Replace("50 à 100 PDF", "un nombre libre de PDF")) `
        -ExpectedOutput "Borne de corpus pilote absente: 50 à 100 PDF" `
        -Message "Le corpus pilote non borné doit être refusé."

    Assert-M012RejectedSpec `
        -Name "annotations-page-absentes" `
        -Content ($validContent.Replace("PageAnnotation", "AnnotationPage")) `
        -ExpectedOutput "Artefact M-012 attendu absent: PageAnnotation" `
        -Message "Les annotations page par page doivent être obligatoires."

    Assert-M012RejectedSpec `
        -Name "metriques-sp-absentes" `
        -Content ($validContent.Replace("source_canonical_version_ratio", "source_version_ratio")) `
        -ExpectedOutput "Métrique SP M-012 absente: source_canonical_version_ratio" `
        -Message "Les métriques SP normatives doivent être obligatoires."

    Assert-M012RejectedSpec `
        -Name "metriques-ka-absentes" `
        -Content ($validContent.Replace("knowledge_recall_at_20", "knowledge_recall_final")) `
        -ExpectedOutput "Métrique KA M-012 absente: knowledge_recall_at_20" `
        -Message "Les métriques KA normatives doivent être obligatoires."

    Assert-M012RejectedSpec `
        -Name "metriques-eg-absentes" `
        -Content ($validContent.Replace("evidence_claim_verified_rate", "evidence_claim_rate")) `
        -ExpectedOutput "Métrique EG M-012 absente: evidence_claim_verified_rate" `
        -Message "Les métriques EG normatives doivent être obligatoires."

    Assert-M012RejectedSpec `
        -Name "metriques-ra-absentes" `
        -Content ($validContent.Replace("answer_support_status_rate", "answer_status_rate")) `
        -ExpectedOutput "Métrique RA M-012 absente: answer_support_status_rate" `
        -Message "Les métriques RA normatives doivent être obligatoires."

    Assert-M012RejectedSpec `
        -Name "criteres-cv-absents" `
        -Content ($validContent.Replace("absence d'usage factuel de l'historique brut", "usage libre de l'historique conversationnel")) `
        -ExpectedOutput "Critère CV M-012 absent: absence d'usage factuel de l'historique brut" `
        -Message "Les critères CV V1 doivent être obligatoires."

    Assert-M012RejectedSpec `
        -Name "metriques-sd-absentes" `
        -Content ($validContent.Replace("strategy_compilable_rate", "strategy_rate")) `
        -ExpectedOutput "Métrique SD M-012 absente: strategy_compilable_rate" `
        -Message "Les métriques SD normatives doivent être obligatoires."

    Assert-M012RejectedSpec `
        -Name "benchmark-llm-absent" `
        -Content ($validContent.Replace("nvidia/Gemma-4-31B-IT-NVFP4", "nvidia/Gemma-4-reference")) `
        -ExpectedOutput "Benchmark LLM M-012 absent: nvidia/Gemma-4-31B-IT-NVFP4" `
        -Message "Le benchmark LLM par chemin réel doit être obligatoire."

    Assert-M012RejectedSpec `
        -Name "benchmark-ex-absent" `
        -Content ($validContent.Replace("experiment_reproducible_rate", "experiment_rate")) `
        -ExpectedOutput "Métrique EX M-012 absente: experiment_reproducible_rate" `
        -Message "Le benchmark EX doit être obligatoire."

    Assert-M012RejectedSpec `
        -Name "decision-calibration-absente" `
        -Content ($validContent.Replace("## Décisions de calibration", "## Décisions reportées")) `
        -ExpectedOutput "Section obligatoire absente: ## Décisions de calibration" `
        -Message "La décision de calibration doit être obligatoire."

    Assert-M012RejectedSpec `
        -Name "rapport-ecarts-v1-absent" `
        -Content ($validContent.Replace("## Rapport d'écarts V1", "## Rapport final")) `
        -ExpectedOutput "Section obligatoire absente: ## Rapport d'écarts V1" `
        -Message "Le rapport d'écarts V1 doit être obligatoire."

    Assert-M012RejectedSpec `
        -Name "erreurs-publiques-absentes" `
        -Content ($validContent.Replace("## Erreurs publiques", "## Erreurs internes")) `
        -ExpectedOutput "Section obligatoire absente: ## Erreurs publiques" `
        -Message "Les erreurs publiques doivent être obligatoires."

    Assert-M012RejectedSpec `
        -Name "gates-absents" `
        -Content ($validContent.Replace("powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m012_specification.ps1", "powershell -File .\scripts\validate_m012_specification.ps1")) `
        -ExpectedOutput "Commande de validation absente: powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m012_specification.ps1" `
        -Message "Les commandes de validation normatives doivent être obligatoires."

    Assert-M012RejectedSpec `
        -Name "exclusion-fallbacks-absente" `
        -Content ($validContent.Replace("Aucun fallback silencieux n'est autorisé dans M-012.", "Un comportement alternatif peut être appliqué par l'évaluateur.")) `
        -ExpectedOutput "Exclusion M-012 absente: Aucun fallback silencieux n'est autorisé dans M-012." `
        -Message "L'exclusion des fallbacks silencieux doit être obligatoire."
}
finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

Write-Host "Tests unitaires du validateur de spécification M-012: OK"
