$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m006_specification.ps1"
$temporaryRoot = Join-Path $repoRoot (".tmp/ost_m006_spec_unit_" + [System.Guid]::NewGuid().ToString("N"))
$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8
$aGrave = [char] 0x00E0
$capitalEAcute = [char] 0x00C9

function New-ValidM006SpecificationContent {
    $canonicalSpecPath = Join-Path $repoRoot "docs/specs/m006_claims_verifiables.md"
    if (-not (Test-Path -LiteralPath $canonicalSpecPath -PathType Leaf)) {
        throw "Spécification canonique M-006 absente pour le fixture unitaire: docs/specs/m006_claims_verifiables.md"
    }

    return Get-Content -Raw -LiteralPath $canonicalSpecPath
}

function Invoke-M006SpecificationValidator {
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
    $Content | Set-Content -LiteralPath $specPath
    return $specPath
}

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur de spécification M-006 absent: scripts/validate_m006_specification.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $validContent = New-ValidM006SpecificationContent
    $validSpecPath = New-TemporarySpec -Name "valid" -Content $validContent
    $validResult = Invoke-M006SpecificationValidator -SpecPath $validSpecPath
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Une spécification M-006 conforme doit être acceptée."

    $missingSectionSpecPath = New-TemporarySpec `
        -Name "missing-mission-eg" `
        -Content ($validContent.Replace("## Mission EG", "## Mission incomplète"))
    $missingSectionResult = Invoke-M006SpecificationValidator -SpecPath $missingSectionSpecPath
    Assert-ExitCode -Actual $missingSectionResult.ExitCode -Expected 1 -Message "Une section obligatoire absente doit être refusée."
    Assert-OutputContains -Output $missingSectionResult.Output -Expected "Section obligatoire absente: ## Mission EG" -Message "La section absente doit être nommée."

    $missingInvariantSpecPath = New-TemporarySpec `
        -Name "missing-invariant" `
        -Content ($validContent.Replace("Une affirmation VERIFIED DOIT posséder au moins une preuve directe admissible.", "Une affirmation vérifiée peut être acceptée sans preuve directe."))
    $missingInvariantResult = Invoke-M006SpecificationValidator -SpecPath $missingInvariantSpecPath
    Assert-ExitCode -Actual $missingInvariantResult.ExitCode -Expected 1 -Message "Un invariant critique absent doit être refusé."
    Assert-OutputContains -Output $missingInvariantResult.Output -Expected "Une affirmation VERIFIED DOIT posséder au moins une preuve directe admissible." -Message "L'invariant absent doit être nommé."

    $missingAdrSpecPath = New-TemporarySpec `
        -Name "missing-adr" `
        -Content ($validContent.Replace("DDD-ADR-003", "DDD-ADR-003-RETIR$($capitalEAcute)E"))
    $missingAdrResult = Invoke-M006SpecificationValidator -SpecPath $missingAdrSpecPath
    Assert-ExitCode -Actual $missingAdrResult.ExitCode -Expected 1 -Message "Une ADR documentaire absente doit être refusée."
    Assert-OutputContains -Output $missingAdrResult.Output -Expected "ADR applicable absente: DDD-ADR-003" -Message "L'ADR absente doit être nommée."

    $missingSourceLocatorSpecPath = New-TemporarySpec `
        -Name "missing-source-locator" `
        -Content ($validContent.Replace("SourceLocator", "SourcePointer"))
    $missingSourceLocatorResult = Invoke-M006SpecificationValidator -SpecPath $missingSourceLocatorSpecPath
    Assert-ExitCode -Actual $missingSourceLocatorResult.ExitCode -Expected 1 -Message "SourceLocator doit être obligatoire dans les preuves publiques."
    Assert-OutputContains -Output $missingSourceLocatorResult.Output -Expected "SourceLocator" -Message "Le SourceLocator absent doit être nommé."

    $missingApiSpecPath = New-TemporarySpec `
        -Name "missing-claims-api" `
        -Content ($validContent.Replace("POST /v1/claims/{claim_id}/verify", "POST /v1/claims/{claim_id}/decide"))
    $missingApiResult = Invoke-M006SpecificationValidator -SpecPath $missingApiSpecPath
    Assert-ExitCode -Actual $missingApiResult.ExitCode -Expected 1 -Message "L'API de vérification des claims doit être obligatoire."
    Assert-OutputContains -Output $missingApiResult.Output -Expected "POST /v1/claims/{claim_id}/verify" -Message "L'endpoint absent doit être nommé."

    $missingPublicErrorSpecPath = New-TemporarySpec `
        -Name "missing-public-error" `
        -Content ($validContent.Replace("CLAIM_SCOPE_EXCEEDS_EVIDENCE", "CLAIM_SCOPE_BROAD"))
    $missingPublicErrorResult = Invoke-M006SpecificationValidator -SpecPath $missingPublicErrorSpecPath
    Assert-ExitCode -Actual $missingPublicErrorResult.ExitCode -Expected 1 -Message "Les erreurs publiques M-006 doivent être obligatoires."
    Assert-OutputContains -Output $missingPublicErrorResult.Output -Expected "CLAIM_SCOPE_EXCEEDS_EVIDENCE" -Message "L'erreur publique absente doit être nommée."

    $scoreVerdictSpecPath = New-TemporarySpec `
        -Name "score-verdict" `
        -Content ($validContent + "`nLe score NLI devient le verdict métier du claim.`n")
    $scoreVerdictResult = Invoke-M006SpecificationValidator -SpecPath $scoreVerdictSpecPath
    Assert-ExitCode -Actual $scoreVerdictResult.ExitCode -Expected 1 -Message "La confusion score et verdict doit être refusée."
    Assert-OutputContains -Output $scoreVerdictResult.Output -Expected "Score traité comme verdict métier interdit" -Message "La confusion score/verdict doit être nommée."

    $directQdrantSpecPath = New-TemporarySpec `
        -Name "direct-qdrant" `
        -Content ($validContent + "`nEG lit Qdrant directement pour vérifier une affirmation.`n")
    $directQdrantResult = Invoke-M006SpecificationValidator -SpecPath $directQdrantSpecPath
    Assert-ExitCode -Actual $directQdrantResult.ExitCode -Expected 1 -Message "L'accès EG direct à Qdrant doit être refusé."
    Assert-OutputContains -Output $directQdrantResult.Output -Expected "Accès EG direct à Qdrant interdit" -Message "L'accès direct doit être nommé."
}
finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

Write-Host "Tests unitaires du validateur de spécification M-006: OK"
