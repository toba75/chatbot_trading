$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m001_specification.ps1"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m001_spec_unit_" + [System.Guid]::NewGuid().ToString("N"))

$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8
$aGrave = [char] 0x00E0
$cCedilla = [char] 0x00E7
$oCircumflex = [char] 0x00F4

function New-ValidM001SpecificationContent {
    return @"
# M-001 - Fronti$($eGrave)res DDD et contrats publi$($eAcute)s

## Sources canoniques

- ADR consult$($eAcute)es: DDD-ADR-001, DDD-ADR-002, DDD-ADR-003.

## Sc$($eAcute)nario BDD

- Given les sept bounded contexts sont d$($eAcute)finis dans la sp$($eAcute)cification v4.1.
- When la sp$($eAcute)cification M-001 est publi$($eAcute)e.
- Then chaque communication intercontexte nomme son contrat publi$($eAcute), son producteur, son consommateur et le mod$($eGrave)le interne qui reste interdit.

## Langage ubiquitaire M-001

Le langage M-001 publie les termes suivants: bounded context, responsabilit$($eAcute) exclusive, langage publi$($eAcute), propri$($eAcute)taire de donn$($eAcute)es, contrat versionn$($eAcute), fa$($cCedilla)ade applicative, anti-corruption layer.

## Contextes propri$($eAcute)taires

| Code | Bounded context | Responsabilit$($eAcute) exclusive | Propri$($eAcute)taire de donn$($eAcute)es | Mod$($eGrave)le interne interdit |
|---|---|---|---|---|
| SP | Traitement des sources | enregistrer, diagnostiquer, convertir, contr$($oCircumflex)ler et publier les versions documentaires canoniques | source_processing | agr$($eAcute)gats, tables et artefacts internes SP |
| KA | Acc$($eGrave)s aux connaissances | construire les projections de recherche et retourner des preuves candidates tra$($cCedilla)ables | knowledge_access | collections Qdrant, cache d'embeddings et algorithmes de fusion internes |
| EG | Gouvernance des preuves | cr$($eAcute)er, v$($eAcute)rifier, relier et versionner les affirmations et leurs preuves | evidence_governance | graphe de claims et artefacts de v$($eAcute)rification internes |
| RA | Recherche et r$($eAcute)ponse | planifier une recherche, assembler les preuves, analyser les contradictions et produire une r$($eAcute)ponse v$($eAcute)rifi$($eAcute)e | research_answering | jeux de preuves, r$($eAcute)ponses et rapports internes |
| CV | Conversation | conserver la continuit$($eAcute) du dialogue et r$($eAcute)soudre les r$($eAcute)f$($eAcute)rences de suivi | conversation | tours et snapshots de contexte internes |
| SD | Conception de strat$($eAcute)gies | formaliser et compiler des strat$($eAcute)gies candidates attribu$($eAcute)es | strategy_design | sp$($eAcute)cifications et snapshots de strat$($eAcute)gie internes |
| EX | Exp$($eAcute)rimentation | ex$($eAcute)cuter des protocoles reproductibles et conserver tous les r$($eAcute)sultats | experimentation | donn$($eAcute)es d'exp$($eAcute)rience, r$($eAcute)sultats et rapports internes |

## Relations intercontextes publi$($eAcute)es

| Relation | Producteur | Consommateur | Contrat publi$($eAcute) | Type | Mod$($eGrave)le interne interdit |
|---|---|---|---|---|---|
| SP -> KA | SP | KA | CanonicalSourcePublished | Published Language | tables et agr$($eAcute)gats SP internes |
| SP -> EG | SP | EG | CanonicalSourcePublished | Published Language | tables et agr$($eAcute)gats SP internes |
| KA -> RA | KA | RA | SearchEvidence API | Customer/Supplier | Qdrant, embeddings et fusion interne |
| EG -> RA | EG | RA | VerifiedClaimRef | Published Language | revue interne EG et graphe de claims |
| EG -> SD | EG | SD | VerifiedClaimRef | Published Language | revue interne EG et graphe de claims |
| RA -> SD | RA | SD | VerifiedResearchOutcome | Anti-Corruption Layer | brouillons de r$($eAcute)ponse et jeux de preuves RA |
| SD -> EX | SD | EX | StrategySnapshot | Published Language immuable | strat$($eAcute)gie candidate mutable SD |
| CV -> RA | CV | RA | ResolvedQuestion | fa$($cCedilla)ade applicative | historique conversationnel CV |
| CV -> SD | CV | SD | StrategyRequest | fa$($cCedilla)ade applicative | pr$($eAcute)f$($eAcute)rences et tours CV |
| CV -> EX | EX | CV | GetExperiment | fa$($cCedilla)ade applicative | registre interne EX |

## Crit$($eGrave)res d'acceptation

- Aucune relation implicite.
"@
}

function Invoke-M001Validator {
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
    throw "Validateur M-001 absent: scripts/validate_m001_specification.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $validContent = New-ValidM001SpecificationContent
    $validSpecPath = New-TemporarySpec -Name "valid" -Content $validContent
    $validResult = Invoke-M001Validator -SpecPath $validSpecPath
    if ($validResult.ExitCode -ne 0) {
        throw "Une sp$($eAcute)cification M-001 conforme doit $([char] 0x00EA)tre accept$($eAcute)e. Sortie du validateur: $($validResult.Output)"
    }
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Une sp$($eAcute)cification M-001 conforme doit $([char] 0x00EA)tre accept$($eAcute)e."

    $missingContextLine = "\| EG \| Gouvernance des preuves \| cr$($eAcute)er, v$($eAcute)rifier, relier et versionner les affirmations et leurs preuves \| evidence_governance \| graphe de claims et artefacts de v$($eAcute)rification internes \|\r?\n"
    $missingContextSpecPath = New-TemporarySpec `
        -Name "missing-context" `
        -Content ($validContent -replace $missingContextLine, "")
    $missingContextResult = Invoke-M001Validator -SpecPath $missingContextSpecPath
    Assert-ExitCode -Actual $missingContextResult.ExitCode -Expected 1 -Message "Un contexte manquant doit $([char] 0x00EA)tre refus$($eAcute)."
    Assert-OutputContains -Output $missingContextResult.Output -Expected "Contexte manquant: EG" -Message "Le contexte manquant doit $([char] 0x00EA)tre nomm$($eAcute)."

    $missingContractSpecPath = New-TemporarySpec `
        -Name "missing-contract" `
        -Content ($validContent.Replace("| SP -> KA | SP | KA | CanonicalSourcePublished |", "| SP -> KA | SP | KA |  |"))
    $missingContractResult = Invoke-M001Validator -SpecPath $missingContractSpecPath
    Assert-ExitCode -Actual $missingContractResult.ExitCode -Expected 1 -Message "Une relation sans contrat doit $([char] 0x00EA)tre refus$($eAcute)e."
    Assert-OutputContains -Output $missingContractResult.Output -Expected "Relation sans contrat publi$($eAcute): SP -> KA" -Message "La relation sans contrat doit $([char] 0x00EA)tre nomm$($eAcute)e."

    $raOwnerLine = "| RA | Recherche et r$($eAcute)ponse | planifier une recherche, assembler les preuves, analyser les contradictions et produire une r$($eAcute)ponse v$($eAcute)rifi$($eAcute)e | research_answering |"
    $raEmptyOwnerLine = "| RA | Recherche et r$($eAcute)ponse | planifier une recherche, assembler les preuves, analyser les contradictions et produire une r$($eAcute)ponse v$($eAcute)rifi$($eAcute)e |  |"
    $emptyOwnerSpecPath = New-TemporarySpec `
        -Name "empty-owner" `
        -Content ($validContent.Replace($raOwnerLine, $raEmptyOwnerLine))
    $emptyOwnerResult = Invoke-M001Validator -SpecPath $emptyOwnerSpecPath
    Assert-ExitCode -Actual $emptyOwnerResult.ExitCode -Expected 1 -Message "Un propri$($eAcute)taire de donn$($eAcute)es vide doit $([char] 0x00EA)tre refus$($eAcute)."
    Assert-OutputContains -Output $emptyOwnerResult.Output -Expected "Propri$($eAcute)taire de donn$($eAcute)es vide pour RA" -Message "Le propri$($eAcute)taire vide doit $([char] 0x00EA)tre nomm$($eAcute)."

    $cvExLine = "| CV -> EX | EX | CV | GetExperiment | fa$($cCedilla)ade applicative | registre interne EX |"
    $unknownRelationLine = "$cvExLine`n| KA -> EX | KA | EX | SearchEvidence API | Published Language | projection KA interne |"
    $unknownRelationSpecPath = New-TemporarySpec `
        -Name "unknown-relation" `
        -Content ($validContent.Replace($cvExLine, $unknownRelationLine))
    $unknownRelationResult = Invoke-M001Validator -SpecPath $unknownRelationSpecPath
    Assert-ExitCode -Actual $unknownRelationResult.ExitCode -Expected 1 -Message "Une relation absente de la context map v4.1 doit $([char] 0x00EA)tre refus$($eAcute)e."
    Assert-OutputContains -Output $unknownRelationResult.Output -Expected "Relation non pr$($eAcute)sente dans la context map v4.1: KA -> EX" -Message "La relation interdite doit $([char] 0x00EA)tre nomm$($eAcute)e."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Tests unitaires du validateur de sp$($eAcute)cification M-001: OK"
