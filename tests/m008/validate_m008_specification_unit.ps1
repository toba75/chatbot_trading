$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m008_specification.ps1"
$temporaryRoot = Join-Path $repoRoot (".tmp/ost_m008_spec_unit_" + [System.Guid]::NewGuid().ToString("N"))

function New-ValidM008SpecificationContent {
    $canonicalSpecPath = Join-Path $repoRoot "docs/specs/m008_conversation_produit.md"
    if (-not (Test-Path -LiteralPath $canonicalSpecPath -PathType Leaf)) {
        throw "Spécification canonique M-008 absente pour le fixture unitaire: docs/specs/m008_conversation_produit.md"
    }

    return Get-Content -Raw -Encoding UTF8 -LiteralPath $canonicalSpecPath
}

function Invoke-M008SpecificationValidator {
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

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur de spécification M-008 absent: scripts/validate_m008_specification.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $validContent = New-ValidM008SpecificationContent
    $validSpecPath = New-TemporarySpec -Name "valid" -Content $validContent
    $validResult = Invoke-M008SpecificationValidator -SpecPath $validSpecPath
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Une spécification M-008 conforme doit être acceptée."

    $missingMissionSpecPath = New-TemporarySpec `
        -Name "missing-mission-cv" `
        -Content ($validContent.Replace("## Mission CV", "## Mission incomplète"))
    $missingMissionResult = Invoke-M008SpecificationValidator -SpecPath $missingMissionSpecPath
    Assert-ExitCode -Actual $missingMissionResult.ExitCode -Expected 1 -Message "Une section mission absente doit être refusée."
    Assert-OutputContains -Output $missingMissionResult.Output -Expected "Section obligatoire absente: ## Mission CV" -Message "La section absente doit être nommée."

    $missingAggregateSpecPath = New-TemporarySpec `
        -Name "missing-aggregate" `
        -Content ($validContent.Replace("| Conversation | Créer et nommer", "| ConversationManquante | Créer et nommer"))
    $missingAggregateResult = Invoke-M008SpecificationValidator -SpecPath $missingAggregateSpecPath
    Assert-ExitCode -Actual $missingAggregateResult.ExitCode -Expected 1 -Message "L'agrégat Conversation doit être obligatoire."
    Assert-OutputContains -Output $missingAggregateResult.Output -Expected "Agrégat M-008 attendu absent: Conversation" -Message "L'agrégat absent doit être nommé."

    $missingValueObjectSpecPath = New-TemporarySpec `
        -Name "missing-value-object" `
        -Content ($validContent.Replace("| ConversationContextSnapshot | Contexte compact", "| ConversationContextMemoire | Contexte compact"))
    $missingValueObjectResult = Invoke-M008SpecificationValidator -SpecPath $missingValueObjectSpecPath
    Assert-ExitCode -Actual $missingValueObjectResult.ExitCode -Expected 1 -Message "L'objet-valeur ConversationContextSnapshot doit être obligatoire."
    Assert-OutputContains -Output $missingValueObjectResult.Output -Expected "Objet-valeur M-008 attendu absent: ConversationContextSnapshot" -Message "L'objet-valeur absent doit être nommé."

    $missingModeSpecPath = New-TemporarySpec `
        -Name "missing-mode" `
        -Content ($validContent.Replace("CHAT_DOCUMENTAIRE", "CHAT_NON_DOCUMENTAIRE"))
    $missingModeResult = Invoke-M008SpecificationValidator -SpecPath $missingModeSpecPath
    Assert-ExitCode -Actual $missingModeResult.ExitCode -Expected 1 -Message "Le mode documentaire doit être obligatoire."
    Assert-OutputContains -Output $missingModeResult.Output -Expected "CHAT_DOCUMENTAIRE" -Message "Le mode absent doit être nommé."

    $missingEndpointSpecPath = New-TemporarySpec `
        -Name "missing-endpoint" `
        -Content ($validContent.Replace("POST /v1/conversations/{conversation_id}/messages", "POST /v1/conversation-messages"))
    $missingEndpointResult = Invoke-M008SpecificationValidator -SpecPath $missingEndpointSpecPath
    Assert-ExitCode -Actual $missingEndpointResult.ExitCode -Expected 1 -Message "L'endpoint de message conversationnel doit être obligatoire."
    Assert-OutputContains -Output $missingEndpointResult.Output -Expected "POST /v1/conversations/{conversation_id}/messages" -Message "L'endpoint absent doit être nommé."

    $missingPublicErrorSpecPath = New-TemporarySpec `
        -Name "missing-public-error" `
        -Content ($validContent.Replace("CONVERSATION_MODE_UNSUPPORTED", "CONVERSATION_MODE_IMPLICIT"))
    $missingPublicErrorResult = Invoke-M008SpecificationValidator -SpecPath $missingPublicErrorSpecPath
    Assert-ExitCode -Actual $missingPublicErrorResult.ExitCode -Expected 1 -Message "L'erreur publique de mode doit être obligatoire."
    Assert-OutputContains -Output $missingPublicErrorResult.Output -Expected "CONVERSATION_MODE_UNSUPPORTED" -Message "L'erreur publique absente doit être nommée."

    $missingAdrSpecPath = New-TemporarySpec `
        -Name "missing-adr" `
        -Content ($validContent.Replace("DDD-ADR-007", "DDD-ADR-007-RETIREE"))
    $missingAdrResult = Invoke-M008SpecificationValidator -SpecPath $missingAdrSpecPath
    Assert-ExitCode -Actual $missingAdrResult.ExitCode -Expected 1 -Message "Une ADR applicable absente doit être refusée."
    Assert-OutputContains -Output $missingAdrResult.Output -Expected "ADR applicable absente: DDD-ADR-007" -Message "L'ADR absente doit être nommée."

    $historyAsProofSpecPath = New-TemporarySpec `
        -Name "history-as-proof" `
        -Content ($validContent + "`nL'historique conversationnel est une preuve documentaire autonome.`n")
    $historyAsProofResult = Invoke-M008SpecificationValidator -SpecPath $historyAsProofSpecPath
    Assert-ExitCode -Actual $historyAsProofResult.ExitCode -Expected 1 -Message "La confusion historique/preuve doit être refusée."
    Assert-OutputContains -Output $historyAsProofResult.Output -Expected "Historique conversationnel traité comme preuve autonome interdit" -Message "La confusion historique/preuve doit être nommée."

    $fallbackModeSpecPath = New-TemporarySpec `
        -Name "fallback-mode" `
        -Content ($validContent + "`nCV choisit CHAT_DOCUMENTAIRE par défaut si le mode est inconnu.`n")
    $fallbackModeResult = Invoke-M008SpecificationValidator -SpecPath $fallbackModeSpecPath
    Assert-ExitCode -Actual $fallbackModeResult.ExitCode -Expected 1 -Message "Un fallback de mode doit être refusé."
    Assert-OutputContains -Output $fallbackModeResult.Output -Expected "Fallback de mode interdit" -Message "Le fallback de mode doit être nommé."

    $missingRevalidationSpecPath = New-TemporarySpec `
        -Name "missing-revalidation" `
        -Content ($validContent.Replace("Toute assertion historique réutilisée sans VerifiedAnswerVersion est renvoyée à RA pour revalidation avant présentation.", "Toute assertion historique réutilisée est présentée depuis le contexte conversationnel."))
    $missingRevalidationResult = Invoke-M008SpecificationValidator -SpecPath $missingRevalidationSpecPath
    Assert-ExitCode -Actual $missingRevalidationResult.ExitCode -Expected 1 -Message "La revalidation RA des assertions historiques doit être obligatoire."
    Assert-OutputContains -Output $missingRevalidationResult.Output -Expected "Marqueur obligatoire absent: Toute assertion historique réutilisée sans VerifiedAnswerVersion" -Message "La revalidation absente doit être nommée."

    $outcomeConfusionSpecPath = New-TemporarySpec `
        -Name "outcome-confusion" `
        -Content ($validContent + "`nVerifiedResearchOutcome contient answer_text et citations dans le contrat RA.`n")
    $outcomeConfusionResult = Invoke-M008SpecificationValidator -SpecPath $outcomeConfusionSpecPath
    Assert-ExitCode -Actual $outcomeConfusionResult.ExitCode -Expected 1 -Message "La confusion VerifiedResearchOutcome/DTO public RA doit être refusée."
    Assert-OutputContains -Output $outcomeConfusionResult.Output -Expected "Confusion VerifiedResearchOutcome/DTO public RA interdite" -Message "La confusion de contrat RA doit être nommée."
}
finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

Write-Host "Tests unitaires du validateur de spécification M-008: OK"
