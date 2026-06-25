param(
    [Parameter(Mandatory = $true)]
    [string] $Path
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8
$aGrave = [char] 0x00E0
$cCedilla = [char] 0x00E7

$expectedContexts = @(
    @{ Code = "SP"; Name = "Traitement des sources"; Responsibility = "enregistrer"; Owner = "source_processing" },
    @{ Code = "KA"; Name = "Acc$($eGrave)s aux connaissances"; Responsibility = "construire"; Owner = "knowledge_access" },
    @{ Code = "EG"; Name = "Gouvernance des preuves"; Responsibility = "cr$($eAcute)er"; Owner = "evidence_governance" },
    @{ Code = "RA"; Name = "Recherche et r$($eAcute)ponse"; Responsibility = "planifier"; Owner = "research_answering" },
    @{ Code = "CV"; Name = "Conversation"; Responsibility = "conserver"; Owner = "conversation" },
    @{ Code = "SD"; Name = "Conception de strat$($eAcute)gies"; Responsibility = "formaliser"; Owner = "strategy_design" },
    @{ Code = "EX"; Name = "Exp$($eAcute)rimentation"; Responsibility = "ex$($eAcute)cuter"; Owner = "experimentation" }
)

$expectedRelations = @(
    @{ Key = "SP->KA"; Relation = "SP -> KA"; Contract = "CanonicalSourcePublished"; Producer = "SP"; Consumer = "KA"; Status = "Livr$($eAcute)" },
    @{ Key = "SP->EG"; Relation = "SP -> EG"; Contract = "CanonicalSourcePublished"; Producer = "SP"; Consumer = "EG"; Status = "Livr$($eAcute)" },
    @{ Key = "KA->RA"; Relation = "KA -> RA"; Contract = "SearchEvidence API"; Producer = "KA"; Consumer = "RA"; Status = "R$($eAcute)serv$($eAcute)" },
    @{ Key = "EG->RA"; Relation = "EG -> RA"; Contract = "VerifiedClaimRef"; Producer = "EG"; Consumer = "RA"; Status = "Livr$($eAcute)" },
    @{ Key = "EG->SD"; Relation = "EG -> SD"; Contract = "VerifiedClaimRef"; Producer = "EG"; Consumer = "SD"; Status = "Livr$($eAcute)" },
    @{ Key = "RA->SD"; Relation = "RA -> SD"; Contract = "VerifiedResearchOutcome"; Producer = "RA"; Consumer = "SD"; Status = "Livr$($eAcute)" },
    @{ Key = "SD->EX"; Relation = "SD -> EX"; Contract = "StrategySnapshot"; Producer = "SD"; Consumer = "EX"; Status = "Livr$($eAcute)" },
    @{ Key = "CV->RA"; Relation = "CV -> RA"; Contract = "ResolvedQuestion"; Producer = "CV"; Consumer = "RA"; Status = "R$($eAcute)serv$($eAcute)" },
    @{ Key = "CV->SD"; Relation = "CV -> SD"; Contract = "StrategyRequest"; Producer = "CV"; Consumer = "SD"; Status = "R$($eAcute)serv$($eAcute)" },
    @{ Key = "CV->EX"; Relation = "CV -> EX"; Contract = "GetExperiment"; Producer = "EX"; Consumer = "CV"; Status = "R$($eAcute)serv$($eAcute)" }
)

$requiredTerms = @(
    "bounded context",
    "responsabilit$($eAcute) exclusive",
    "langage publi$($eAcute)",
    "propri$($eAcute)taire de donn$($eAcute)es",
    "contrat versionn$($eAcute)",
    "fa$($cCedilla)ade applicative",
    "anti-corruption layer"
)

$requiredMarkers = @(
    "DDD-ADR-001",
    "DDD-ADR-002",
    "DDD-ADR-003",
    "Given les sept bounded contexts sont d$($eAcute)finis dans la sp$($eAcute)cification v4.1.",
    "When la sp$($eAcute)cification M-001 est publi$($eAcute)e.",
    "Then chaque communication intercontexte nomme son contrat publi$($eAcute), son producteur, son consommateur et le mod$($eGrave)le interne qui reste interdit."
)

function Normalize-M001Cell {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Value
    )

    return ($Value.Trim() -replace "`"", "" -replace "\*\*", "" -replace "<br\s*/?>", " ")
}

function Split-M001MarkdownRow {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Line
    )

    $trimmedLine = $Line.Trim()
    if ($trimmedLine.StartsWith("|")) {
        $trimmedLine = $trimmedLine.Substring(1)
    }
    if ($trimmedLine.EndsWith("|")) {
        $trimmedLine = $trimmedLine.Substring(0, $trimmedLine.Length - 1)
    }

    return @($trimmedLine -split "\|" | ForEach-Object { Normalize-M001Cell -Value $_ })
}

function Test-M001SeparatorRow {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Line
    )

    return ($Line.Trim() -match "^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$")
}

function Read-M001MarkdownTable {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string[]] $Lines,

        [Parameter(Mandatory = $true)]
        [string[]] $RequiredHeaders,

        [Parameter(Mandatory = $true)]
        [string] $TableName
    )

    for ($lineIndex = 0; $lineIndex -lt $Lines.Count; $lineIndex++) {
        if (-not $Lines[$lineIndex].Trim().StartsWith("|")) {
            continue
        }

        $headers = Split-M001MarkdownRow -Line $Lines[$lineIndex]
        $containsAllHeaders = $true
        foreach ($requiredHeader in $RequiredHeaders) {
            if ($headers -notcontains $requiredHeader) {
                $containsAllHeaders = $false
                break
            }
        }

        if (-not $containsAllHeaders) {
            continue
        }

        if (($lineIndex + 1) -ge $Lines.Count -or -not (Test-M001SeparatorRow -Line $Lines[$lineIndex + 1])) {
            throw "Table $TableName invalide: ligne de s$($eAcute)paration absente."
        }

        $rows = @()
        $rowIndex = $lineIndex + 2
        while ($rowIndex -lt $Lines.Count -and $Lines[$rowIndex].Trim().StartsWith("|")) {
            if (Test-M001SeparatorRow -Line $Lines[$rowIndex]) {
                $rowIndex++
                continue
            }

            $cells = Split-M001MarkdownRow -Line $Lines[$rowIndex]
            if ($cells.Count -ne $headers.Count) {
                throw "Table $TableName invalide: nombre de cellules incoh$($eAcute)rent ligne $($rowIndex + 1)."
            }

            $row = @{}
            for ($cellIndex = 0; $cellIndex -lt $headers.Count; $cellIndex++) {
                $key = [string] $headers[$cellIndex]
                $value = [string] $cells[$cellIndex]
                $row[$key] = $value
            }
            $rows += ,$row
            $rowIndex++
        }

        if (@($rows).Count -eq 0) {
            throw "Table $TableName invalide: aucune ligne de donn$($eAcute)es."
        }

        return @($rows)
    }

    throw "Table $TableName absente."
}

function Assert-M001Contains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if (-not $Content.Contains($Expected)) {
        throw $Message
    }
}

function Resolve-M001RepositoryPath {
    param(
        [Parameter(Mandatory = $true)]
        [string] $InputPath,

        [Parameter(Mandatory = $true)]
        [string] $Label
    )

    if ([string]::IsNullOrWhiteSpace($InputPath)) {
        throw "Chemin $Label vide."
    }

    $candidatePath = $InputPath
    if (-not [System.IO.Path]::IsPathRooted($candidatePath)) {
        $candidatePath = Join-Path $repoRoot $candidatePath
    }

    $resolvedRepositoryRoot = [System.IO.Path]::GetFullPath($repoRoot)
    $resolvedCandidatePath = [System.IO.Path]::GetFullPath($candidatePath)
    $repositoryPrefix = $resolvedRepositoryRoot.TrimEnd("\", "/") + [System.IO.Path]::DirectorySeparatorChar

    if (-not $resolvedCandidatePath.StartsWith($repositoryPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Chemin hors depot interdit ($Label): $resolvedCandidatePath"
    }

    return $resolvedCandidatePath
}

function Assert-M001Spec {
    param(
        [Parameter(Mandatory = $true)]
        [string] $SpecPath
    )

    if (-not (Test-Path -LiteralPath $SpecPath -PathType Leaf)) {
        throw "Sp$($eAcute)cification M-001 absente: $SpecPath"
    }

    $content = Get-Content -Raw -Encoding UTF8 -LiteralPath $SpecPath
    $lines = @(Get-Content -Encoding UTF8 -LiteralPath $SpecPath)

    Assert-M001Contains `
        -Content $content `
        -Expected "# M-001 - Fronti$($eGrave)res DDD et contrats publi$($eAcute)s" `
        -Message "Titre M-001 absent ou invalide."

    foreach ($marker in $requiredMarkers) {
        Assert-M001Contains `
            -Content $content `
            -Expected $marker `
            -Message "Marqueur obligatoire absent: $marker"
    }

    foreach ($term in $requiredTerms) {
        Assert-M001Contains `
            -Content $content `
            -Expected $term `
            -Message "Terme du langage ubiquitaire absent: $term"
    }

    $contextRows = Read-M001MarkdownTable `
        -Lines $lines `
        -RequiredHeaders @("Code", "Bounded context", "Responsabilit$($eAcute) exclusive", "Propri$($eAcute)taire de donn$($eAcute)es", "Mod$($eGrave)le interne interdit") `
        -TableName "contextes M-001"

    $contextsByCode = @{}
    foreach ($row in $contextRows) {
        $code = $row["Code"]
        if ([string]::IsNullOrWhiteSpace($code)) {
            throw "Contexte sans code."
        }
        if ($contextsByCode.ContainsKey($code)) {
            throw "Contexte dupliqu$($eAcute): $code"
        }
        $contextsByCode[$code] = $row
    }

    foreach ($expectedContext in $expectedContexts) {
        if (-not $contextsByCode.ContainsKey($expectedContext.Code)) {
            throw "Contexte manquant: $($expectedContext.Code)"
        }

        $row = $contextsByCode[$expectedContext.Code]
        if (-not $row["Bounded context"].Contains($expectedContext.Name)) {
            throw "Nom de contexte invalide pour $($expectedContext.Code)."
        }
        if (-not $row["Responsabilit$($eAcute) exclusive"].Contains($expectedContext.Responsibility)) {
            throw "Responsabilit$($eAcute) exclusive invalide pour $($expectedContext.Code)."
        }
        if ([string]::IsNullOrWhiteSpace($row["Propri$($eAcute)taire de donn$($eAcute)es"])) {
            throw "Propri$($eAcute)taire de donn$($eAcute)es vide pour $($expectedContext.Code)."
        }
        if (-not $row["Propri$($eAcute)taire de donn$($eAcute)es"].Contains($expectedContext.Owner)) {
            throw "Propri$($eAcute)taire de donn$($eAcute)es invalide pour $($expectedContext.Code)."
        }
        if ([string]::IsNullOrWhiteSpace($row["Mod$($eGrave)le interne interdit"])) {
            throw "Mod$($eGrave)le interne interdit vide pour $($expectedContext.Code)."
        }
    }

    foreach ($contextCode in $contextsByCode.Keys) {
        if (@($expectedContexts | Where-Object { $_.Code -eq $contextCode }).Count -eq 0) {
            throw "Contexte non pr$($eAcute)sent dans la sp$($eAcute)cification v4.1: $contextCode"
        }
    }

    $relationRows = Read-M001MarkdownTable `
        -Lines $lines `
        -RequiredHeaders @("Relation", "Producteur", "Consommateur", "Contrat publi$($eAcute)", "Statut M-001", "Type", "Mod$($eGrave)le interne interdit") `
        -TableName "relations M-001"

    $relationsByKey = @{}
    foreach ($row in $relationRows) {
        $relation = ($row["Relation"] -replace "\s+", "")
        if ($relation -notmatch "^[A-Z]{2}->[A-Z]{2}$") {
            throw "Relation invalide: $($row["Relation"])"
        }

        if ($relationsByKey.ContainsKey($relation)) {
            throw "Relation dupliqu$($eAcute)e: $($row["Relation"])"
        }

        if ([string]::IsNullOrWhiteSpace($row["Contrat publi$($eAcute)"])) {
            throw "Relation sans contrat publi$($eAcute): $($row["Relation"])"
        }
        if ($row["Statut M-001"] -notin @("Livr$($eAcute)", "R$($eAcute)serv$($eAcute)")) {
            throw "Statut M-001 invalide pour $($row["Relation"])."
        }

        if ($row["Contrat publi$($eAcute)"] -match "(?i)\b(table|classe|record|agr$($eAcute)gat|schema|sch$($eAcute)ma|postgres|qdrant)\b") {
            throw "Contrat publi$($eAcute) coupl$($eAcute) $($aGrave) un mod$($eGrave)le interne: $($row["Relation"])"
        }

        if ([string]::IsNullOrWhiteSpace($row["Producteur"])) {
            throw "Producteur vide pour la relation: $($row["Relation"])"
        }
        if ([string]::IsNullOrWhiteSpace($row["Consommateur"])) {
            throw "Consommateur vide pour la relation: $($row["Relation"])"
        }
        if ([string]::IsNullOrWhiteSpace($row["Mod$($eGrave)le interne interdit"])) {
            throw "Mod$($eGrave)le interne interdit vide pour la relation: $($row["Relation"])"
        }

        $relationsByKey[$relation] = $row
    }

    foreach ($expectedRelation in $expectedRelations) {
        if (-not $relationsByKey.ContainsKey($expectedRelation.Key)) {
            throw "Relation attendue manquante: $($expectedRelation.Relation)"
        }

        $row = $relationsByKey[$expectedRelation.Key]
        if ($row["Contrat publi$($eAcute)"] -ne $expectedRelation.Contract) {
            throw "Contrat publi$($eAcute) invalide pour $($expectedRelation.Relation)."
        }
        if ($row["Producteur"] -ne $expectedRelation.Producer) {
            throw "Producteur invalide pour $($expectedRelation.Relation)."
        }
        if ($row["Consommateur"] -ne $expectedRelation.Consumer) {
            throw "Consommateur invalide pour $($expectedRelation.Relation)."
        }
        if ($row["Statut M-001"] -ne $expectedRelation.Status) {
            throw "Statut M-001 invalide pour $($expectedRelation.Relation)."
        }
    }

    foreach ($relationKey in $relationsByKey.Keys) {
        if (@($expectedRelations | Where-Object { $_.Key -eq $relationKey }).Count -eq 0) {
            throw "Relation non pr$($eAcute)sente dans la context map v4.1: $($relationsByKey[$relationKey]["Relation"])"
        }
    }
}

$resolvedPath = Resolve-M001RepositoryPath -InputPath $Path -Label "specification M-001"
Assert-M001Spec -SpecPath $resolvedPath

Write-Host "Sp$($eAcute)cification M-001 valide: $($expectedContexts.Count) contexte(s), $($expectedRelations.Count) relation(s) contr$([char] 0x00F4)l$($eAcute)e(s)."
