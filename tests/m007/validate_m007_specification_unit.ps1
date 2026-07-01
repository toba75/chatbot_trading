$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m007_specification.ps1"
$temporaryRoot = Join-Path $repoRoot (".tmp/ost_m007_spec_unit_" + [System.Guid]::NewGuid().ToString("N"))
$capitalEAcute = [char] 0x00C9

function New-ValidM007SpecificationContent {
    $canonicalSpecPath = Join-Path $repoRoot "docs/specs/m007_reponse_documentaire_verifiee.md"
    if (-not (Test-Path -LiteralPath $canonicalSpecPath -PathType Leaf)) {
        throw "Spécification canonique M-007 absente pour le fixture unitaire: docs/specs/m007_reponse_documentaire_verifiee.md"
    }

    return Get-Content -Raw -Encoding UTF8 -LiteralPath $canonicalSpecPath
}

function Invoke-M007SpecificationValidator {
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
    throw "Validateur de spécification M-007 absent: scripts/validate_m007_specification.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $validContent = New-ValidM007SpecificationContent
    $validSpecPath = New-TemporarySpec -Name "valid" -Content $validContent
    $validResult = Invoke-M007SpecificationValidator -SpecPath $validSpecPath
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Une spécification M-007 conforme doit être acceptée."

    $missingSectionSpecPath = New-TemporarySpec `
        -Name "missing-mission-ra" `
        -Content ($validContent.Replace("## Mission RA", "## Mission incomplète"))
    $missingSectionResult = Invoke-M007SpecificationValidator -SpecPath $missingSectionSpecPath
    Assert-ExitCode -Actual $missingSectionResult.ExitCode -Expected 1 -Message "Une section obligatoire absente doit être refusée."
    Assert-OutputContains -Output $missingSectionResult.Output -Expected "Section obligatoire absente: ## Mission RA" -Message "La section absente doit être nommée."

    $missingInvariantSpecPath = New-TemporarySpec `
        -Name "missing-supported-invariant" `
        -Content ($validContent.Replace("Une réponse SUPPORTED exige que chaque assertion importante conservée soit supportée.", "Une réponse SUPPORTED peut conserver une assertion importante non supportée."))
    $missingInvariantResult = Invoke-M007SpecificationValidator -SpecPath $missingInvariantSpecPath
    Assert-ExitCode -Actual $missingInvariantResult.ExitCode -Expected 1 -Message "Un invariant critique absent doit être refusé."
    Assert-OutputContains -Output $missingInvariantResult.Output -Expected "Une réponse SUPPORTED exige que chaque assertion importante conservée soit supportée." -Message "L'invariant absent doit être nommé."

    $missingStatusSpecPath = New-TemporarySpec `
        -Name "missing-support-status" `
        -Content ($validContent.Replace("CONFLICTING_EVIDENCE", "CONFLICTING_DOCUMENTS"))
    $missingStatusResult = Invoke-M007SpecificationValidator -SpecPath $missingStatusSpecPath
    Assert-ExitCode -Actual $missingStatusResult.ExitCode -Expected 1 -Message "Un statut de support absent doit être refusé."
    Assert-OutputContains -Output $missingStatusResult.Output -Expected "CONFLICTING_EVIDENCE" -Message "Le statut absent doit être nommé."

    $missingCitationSpecPath = New-TemporarySpec `
        -Name "missing-citation" `
        -Content ($validContent.Replace("Citation", "ReferenceOpaque"))
    $missingCitationResult = Invoke-M007SpecificationValidator -SpecPath $missingCitationSpecPath
    Assert-ExitCode -Actual $missingCitationResult.ExitCode -Expected 1 -Message "La citation ouvrable doit être obligatoire."
    Assert-OutputContains -Output $missingCitationResult.Output -Expected "Citation" -Message "La citation absente doit être nommée."

    $missingPublicErrorSpecPath = New-TemporarySpec `
        -Name "missing-public-error" `
        -Content ($validContent.Replace("ANSWER_ASSERTION_UNSUPPORTED", "ANSWER_ASSERTION_WEAK"))
    $missingPublicErrorResult = Invoke-M007SpecificationValidator -SpecPath $missingPublicErrorSpecPath
    Assert-ExitCode -Actual $missingPublicErrorResult.ExitCode -Expected 1 -Message "Les erreurs publiques M-007 doivent être obligatoires."
    Assert-OutputContains -Output $missingPublicErrorResult.Output -Expected "ANSWER_ASSERTION_UNSUPPORTED" -Message "L'erreur publique absente doit être nommée."

    $missingAdrSpecPath = New-TemporarySpec `
        -Name "missing-adr" `
        -Content ($validContent.Replace("DDD-ADR-007", "DDD-ADR-007-RETIR$($capitalEAcute)E"))
    $missingAdrResult = Invoke-M007SpecificationValidator -SpecPath $missingAdrSpecPath
    Assert-ExitCode -Actual $missingAdrResult.ExitCode -Expected 1 -Message "Une ADR applicable absente doit être refusée."
    Assert-OutputContains -Output $missingAdrResult.Output -Expected "ADR applicable absente: DDD-ADR-007" -Message "L'ADR absente doit être nommée."

    $draftPublishedSpecPath = New-TemporarySpec `
        -Name "draft-published" `
        -Content ($validContent + "`nLe brouillon de réponse est publié comme réponse finale immuable.`n")
    $draftPublishedResult = Invoke-M007SpecificationValidator -SpecPath $draftPublishedSpecPath
    Assert-ExitCode -Actual $draftPublishedResult.ExitCode -Expected 1 -Message "La confusion entre brouillon et réponse publiée doit être refusée."
    Assert-OutputContains -Output $draftPublishedResult.Output -Expected "Confusion brouillon/réponse publiée interdite" -Message "La confusion brouillon/réponse doit être nommée."

    $directQdrantSpecPath = New-TemporarySpec `
        -Name "direct-qdrant" `
        -Content ($validContent + "`nRA lit Qdrant directement pour assembler le jeu de preuves.`n")
    $directQdrantResult = Invoke-M007SpecificationValidator -SpecPath $directQdrantSpecPath
    Assert-ExitCode -Actual $directQdrantResult.ExitCode -Expected 1 -Message "L'accès RA direct à Qdrant doit être refusé."
    Assert-OutputContains -Output $directQdrantResult.Output -Expected "Accès RA direct à Qdrant interdit" -Message "L'accès direct Qdrant doit être nommé."

    $directEgRegistrySpecPath = New-TemporarySpec `
        -Name "direct-eg-registry" `
        -Content ($validContent + "`nRA lit le registre EG interne directement pour vérifier la réponse.`n")
    $directEgRegistryResult = Invoke-M007SpecificationValidator -SpecPath $directEgRegistrySpecPath
    Assert-ExitCode -Actual $directEgRegistryResult.ExitCode -Expected 1 -Message "L'accès RA direct au registre EG interne doit être refusé."
    Assert-OutputContains -Output $directEgRegistryResult.Output -Expected "Accès RA direct au registre EG interne interdit" -Message "L'accès direct EG doit être nommé."
}
finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

Write-Host "Tests unitaires du validateur de spécification M-007: OK"
