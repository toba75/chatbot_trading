$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$adrDir = Join-Path $repoRoot "docs/adr"
$specPath = Join-Path $repoRoot "docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md"

$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8
$cCedilla = [char] 0x00E7
$oCircumflex = [char] 0x00F4

$requiredFiles = @(
    "README.md",
    "TEMPLATE.md",
    "index.md"
)

$allowedStatuses = @(
    "Propos$($eAcute)e",
    "Accept$($eAcute)e",
    "Remplac$($eAcute)e",
    "D$($eAcute)pr$($eAcute)ci$($eAcute)e",
    "Rejet$($eAcute)e"
)

$requiredMetadataLabels = @(
    "Statut",
    "Date",
    "D$($eAcute)cideurs",
    "Remplace",
    "Remplac$($eAcute)e par",
    "Source"
)

$requiredSectionHeadings = @(
    "Contexte",
    "D$($eAcute)cision",
    "Cons$($eAcute)quences",
    "Impact d'impl$($eAcute)mentation",
    "Liens de tra$($cCedilla)abilit$($eAcute)"
)

function Assert-PathExists {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $Message,

        [Parameter(Mandatory = $true)]
        [string] $PathType
    )

    if (-not (Test-Path -LiteralPath $Path -PathType $PathType)) {
        throw $Message
    }
}

function Assert-Regex {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $Pattern,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if ($Content -notmatch $Pattern) {
        throw $Message
    }
}

function Get-RequiredMetadataValue {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $Label,

        [Parameter(Mandatory = $true)]
        [string] $FileName
    )

    $pattern = "(?m)^\*\*" + [regex]::Escape($Label) + "\s*:\*\*\s*(?<value>\S.*)$"
    $match = [regex]::Match($Content, $pattern)
    if (-not $match.Success) {
        throw "Champ ADR obligatoire absent ou vide dans ${FileName}: $Label"
    }

    return $match.Groups["value"].Value.Trim()
}

function Assert-AllowedStatus {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Status,

        [Parameter(Mandatory = $true)]
        [string] $Context
    )

    if ($allowedStatuses -notcontains $Status) {
        throw "Statut ADR non autoris$($eAcute) dans ${Context}: $Status"
    }
}

function Assert-AdrDate {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Date,

        [Parameter(Mandatory = $true)]
        [string] $Context
    )

    $parsedDate = [datetime]::MinValue
    if (-not [datetime]::TryParseExact($Date, "yyyy-MM-dd", [System.Globalization.CultureInfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::None, [ref] $parsedDate)) {
        throw "Date ADR invalide dans ${Context}: $Date"
    }
}

function Get-AdrReferences {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Value
    )

    $trimmedValue = $Value.Trim()
    if ($trimmedValue -in @("Aucun", "Aucune")) {
        return @()
    }

    $referenceListPattern = "^(?:DDD-)?ADR-\d{3}(?:\s*[;,]\s*(?:DDD-)?ADR-\d{3})*$"
    if ($trimmedValue -notmatch $referenceListPattern) {
        throw "R$($eAcute)f$($eAcute)rence ADR invalide: $Value"
    }

    $matches = [regex]::Matches($trimmedValue, "(?:DDD-)?ADR-\d{3}")
    return @($matches | ForEach-Object { $_.Value })
}

function Get-SpecSection3DecisionIds {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    $decisionIds = New-Object System.Collections.Generic.List[string]
    $insideSection3 = $false
    $lines = Get-Content -Encoding UTF8 -LiteralPath $Path

    foreach ($line in $lines) {
        if ($line -match "^#\s+3\.\s+") {
            $insideSection3 = $true
            continue
        }

        if ($insideSection3 -and $line -match "^#\s+\d+\.\s+") {
            break
        }

        if ($insideSection3 -and $line -match "^###\s+(?<id>(?:DDD-)?ADR-\d{3})\s+") {
            $decisionIds.Add($Matches["id"])
        }
    }

    if ($decisionIds.Count -eq 0) {
        throw "La section 3 de la sp$($eAcute)cification ne r$($eAcute)f$($eGrave)rence aucune ADR."
    }

    return $decisionIds
}

function Convert-ReferenceListToKey {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [string[]] $References
    )

    return (@($References) | Sort-Object) -join ","
}

function Get-MarkdownSectionContent {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $Heading
    )

    $lines = @($Content -split "`r?`n")
    $sectionLines = New-Object System.Collections.Generic.List[string]
    $insideSection = $false

    foreach ($line in $lines) {
        if ($line -match ("^##\s+" + [regex]::Escape($Heading) + "\s*$")) {
            $insideSection = $true
            continue
        }

        if ($insideSection -and $line -match "^##\s+") {
            break
        }

        if ($insideSection) {
            $sectionLines.Add($line)
        }
    }

    if (-not $insideSection) {
        throw "Section introuvable pour comparaison ADR: $Heading"
    }

    return (($sectionLines -join "`n").Trim())
}

function Get-GitMasterFileContent {
    param(
        [Parameter(Mandatory = $true)]
        [string] $RepositoryRoot,

        [Parameter(Mandatory = $true)]
        [string] $RelativePath
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $output = & git -C $RepositoryRoot show "master:$RelativePath" 2>&1
        $showExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($showExitCode -ne 0) {
        throw "Lecture Git impossible pour master:${RelativePath}: $($output -join ' ')"
    }

    return [pscustomobject] @{
        Content = ($output -join "`n")
    }
}

function Get-GitMasterAdrPathSet {
    param(
        [Parameter(Mandatory = $true)]
        [string] $RepositoryRoot
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $output = & git -C $RepositoryRoot ls-tree -r --name-only master -- docs/adr 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0) {
        throw "Lecture Git impossible pour la liste ADR de master: $($output -join ' ')"
    }

    $paths = New-Object System.Collections.Generic.HashSet[string]
    foreach ($line in $output) {
        $path = $line.Trim()
        if ($path -ne "") {
            [void] $paths.Add($path.Replace("\", "/"))
        }
    }

    return $paths
}

function Assert-GitMasterReference {
    param(
        [Parameter(Mandatory = $true)]
        [string] $RepositoryRoot
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $output = & git -C $RepositoryRoot rev-parse --verify "master^{commit}" 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0) {
        throw "R$($eAcute)f$($eAcute)rence Git master indisponible pour contr$($oCircumflex)ler les ADR accept$($eAcute)es: $($output -join ' ')"
    }
}

Assert-PathExists -Path $adrDir -PathType "Container" -Message "Le r$($eAcute)pertoire docs/adr est absent."
Assert-PathExists -Path $specPath -PathType "Leaf" -Message "La sp$($eAcute)cification v4.1 est absente: docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md"

foreach ($fileName in $requiredFiles) {
    $path = Join-Path $adrDir $fileName
    Assert-PathExists -Path $path -PathType "Leaf" -Message "Le fichier ADR obligatoire est absent: docs/adr/$fileName"
}

$adrFiles = Get-ChildItem -LiteralPath $adrDir -File |
    Where-Object { $_.Name -notin $requiredFiles } |
    Sort-Object Name

if ($adrFiles.Count -eq 0) {
    throw "Aucune ADR n'est pr$($eAcute)sente dans docs/adr."
}

$indexContent = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $adrDir "index.md")
$technicalNumbers = New-Object System.Collections.Generic.HashSet[int]
$dddNumbers = New-Object System.Collections.Generic.HashSet[int]
$adrByFileName = @{}
$adrById = @{}
$adrTitlesByFileName = @{}
$adrDatesByFileName = @{}
$adrStatusesByFileName = @{}
$adrReplacementById = @{}
$adrReplacedById = @{}

foreach ($adrFile in $adrFiles) {
    if ($adrFile.Name -notmatch "^(?<family>ADR|DDD-ADR)-(?<number>\d{3})-[a-z0-9]+(-[a-z0-9]+)*\.md$") {
        throw "Nom ADR invalide: $($adrFile.Name)"
    }

    $family = $Matches["family"]
    $numberText = $Matches["number"]
    $number = [int] $numberText
    if ($family -eq "ADR") {
        $numberSet = $technicalNumbers
    }
    else {
        $numberSet = $dddNumbers
    }

    if (-not $numberSet.Add($number)) {
        throw "Num$($eAcute)ro ADR dupliqu$($eAcute) dans la famille ${family}: $numberText"
    }

    $id = "$family-$numberText"
    $content = Get-Content -Raw -Encoding UTF8 -LiteralPath $adrFile.FullName

    $titleMatch = [regex]::Match($content, "(?m)^# $([regex]::Escape($id)) - (?<title>.+)$")
    if (-not $titleMatch.Success) {
        throw "Titre ADR invalide ou absent: $($adrFile.Name)"
    }

    foreach ($label in $requiredMetadataLabels) {
        [void] (Get-RequiredMetadataValue -Content $content -Label $label -FileName $adrFile.Name)
    }

    foreach ($heading in $requiredSectionHeadings) {
        Assert-Regex -Content $content -Pattern "(?m)^## $([regex]::Escape($heading))\s*$" -Message "ADR incompl$($eGrave)te ($($adrFile.Name)): section manquante '## $heading'"
    }

    $status = Get-RequiredMetadataValue -Content $content -Label "Statut" -FileName $adrFile.Name
    Assert-AllowedStatus -Status $status -Context $adrFile.Name
    $date = Get-RequiredMetadataValue -Content $content -Label "Date" -FileName $adrFile.Name
    Assert-AdrDate -Date $date -Context $adrFile.Name

    $replaces = Get-RequiredMetadataValue -Content $content -Label "Remplace" -FileName $adrFile.Name
    $replacedBy = Get-RequiredMetadataValue -Content $content -Label "Remplac$($eAcute)e par" -FileName $adrFile.Name

    $adrByFileName[$adrFile.Name] = $adrFile
    $adrById[$id] = $adrFile
    $adrTitlesByFileName[$adrFile.Name] = $titleMatch.Groups["title"].Value.Trim()
    $adrDatesByFileName[$adrFile.Name] = $date
    $adrStatusesByFileName[$adrFile.Name] = $status
    $adrReplacementById[$id] = @(Get-AdrReferences -Value $replaces)
    $adrReplacedById[$id] = @(Get-AdrReferences -Value $replacedBy)
}

$indexRows = @($indexContent -split "`r?`n" | Where-Object { $_ -match "^\|\s*\[(?:DDD-)?ADR-\d{3}\]\(" })
$indexedFiles = New-Object System.Collections.Generic.HashSet[string]
$indexedStatusesByFileName = @{}

foreach ($row in $indexRows) {
    $rowMatch = [regex]::Match($row, "^\|\s*\[(?<id>(?:DDD-)?ADR-\d{3})\]\((?<file>[^)]+)\)\s*\|\s*(?<title>[^|]+)\|\s*(?<status>[^|]+)\|\s*(?<date>[^|]+)\|\s*(?<replaces>[^|]+)\|\s*(?<replacedBy>[^|]+)\|")
    if (-not $rowMatch.Success) {
        throw "Ligne d'index ADR invalide: $row"
    }

    $id = $rowMatch.Groups["id"].Value.Trim()
    $fileName = $rowMatch.Groups["file"].Value.Trim()
    $status = $rowMatch.Groups["status"].Value.Trim()
    $title = $rowMatch.Groups["title"].Value.Trim()
    $date = $rowMatch.Groups["date"].Value.Trim()
    $replaces = $rowMatch.Groups["replaces"].Value.Trim()
    $replacedBy = $rowMatch.Groups["replacedBy"].Value.Trim()

    if ($fileName -notmatch "^(ADR|DDD-ADR)-\d{3}-[a-z0-9]+(-[a-z0-9]+)*\.md$") {
        throw "Lien d'index ADR invalide: $fileName"
    }

    if (-not $adrByFileName.ContainsKey($fileName)) {
        throw "L'index r$($eAcute)f$($eGrave)rence une ADR absente: $fileName"
    }

    if (-not $indexedFiles.Add($fileName)) {
        throw "ADR dupliqu$($eAcute)e dans l'index: $fileName"
    }

    if (-not $fileName.StartsWith("$id-")) {
        throw "Identifiant d'index incoh$($eAcute)rent pour ${fileName}: $id"
    }

    Assert-AllowedStatus -Status $status -Context "index ${fileName}"
    Assert-AdrDate -Date $date -Context "index ${fileName}"

    if ($adrStatusesByFileName[$fileName] -ne $status) {
        throw "Statut incoh$($eAcute)rent entre l'ADR et l'index pour ${fileName}."
    }

    if ($adrTitlesByFileName[$fileName] -ne $title) {
        throw "Titre incoh$($eAcute)rent entre l'ADR et l'index pour ${fileName}."
    }

    if ($adrDatesByFileName[$fileName] -ne $date) {
        throw "Date incoh$($eAcute)rente entre l'ADR et l'index pour ${fileName}."
    }

    $indexedStatusesByFileName[$fileName] = $status
    $indexReplacementReferences = @(Get-AdrReferences -Value $replaces)
    $indexReplacedByReferences = @(Get-AdrReferences -Value $replacedBy)

    if ((Convert-ReferenceListToKey -References $adrReplacementById[$id]) -ne (Convert-ReferenceListToKey -References $indexReplacementReferences)) {
        throw "Champ Remplace incoh$($eAcute)rent entre l'ADR et l'index pour ${fileName}."
    }

    if ((Convert-ReferenceListToKey -References $adrReplacedById[$id]) -ne (Convert-ReferenceListToKey -References $indexReplacedByReferences)) {
        throw "Champ Remplac$($eAcute)e par incoh$($eAcute)rent entre l'ADR et l'index pour ${fileName}."
    }
}

foreach ($adrFile in $adrFiles) {
    if (-not $indexedFiles.Contains($adrFile.Name)) {
        throw "ADR absente de l'index: $($adrFile.Name)"
    }
}

foreach ($id in $adrReplacementById.Keys) {
    foreach ($referencedId in $adrReplacementById[$id]) {
        if (-not $adrById.ContainsKey($referencedId)) {
            throw "ADR remplac$($eAcute)e introuvable pour ${id}: $referencedId"
        }
    }

    foreach ($referencedId in $adrReplacedById[$id]) {
        if (-not $adrById.ContainsKey($referencedId)) {
            throw "ADR rempla$($cCedilla)ante introuvable pour ${id}: $referencedId"
        }
    }

    $fileName = $adrById[$id].Name
    if ($adrStatusesByFileName[$fileName] -eq "Remplac$($eAcute)e" -and $adrReplacedById[$id].Count -eq 0) {
        throw "ADR remplac$($eAcute)e sans champ 'Remplac$($eAcute)e par' renseign$($eAcute): $id"
    }
}

foreach ($id in $adrReplacementById.Keys) {
    foreach ($replacedId in $adrReplacementById[$id]) {
        if ($adrReplacedById[$replacedId] -notcontains $id) {
            throw "Relation ADR asym$($eAcute)trique: $id remplace $replacedId, mais $replacedId ne d$($eAcute)clare pas 'Remplac$($eAcute)e par' $id."
        }
    }

    foreach ($replacementId in $adrReplacedById[$id]) {
        if ($adrReplacementById[$replacementId] -notcontains $id) {
            throw "Relation ADR asym$($eAcute)trique: $id est remplac$($eAcute)e par $replacementId, mais $replacementId ne d$($eAcute)clare pas 'Remplace' $id."
        }
    }
}

Assert-GitMasterReference -RepositoryRoot $repoRoot
$masterAdrPaths = Get-GitMasterAdrPathSet -RepositoryRoot $repoRoot

foreach ($id in $adrById.Keys) {
    $adrFile = $adrById[$id]

    $relativePath = "docs/adr/$($adrFile.Name)"

    if (-not $masterAdrPaths.Contains($relativePath)) {
        continue
    }

    $masterFile = Get-GitMasterFileContent -RepositoryRoot $repoRoot -RelativePath $relativePath
    $masterContent = $masterFile.Content
    $masterStatusMatch = [regex]::Match($masterContent, "(?m)^\*\*Statut\s*:\*\*\s*(?<status>\S.*)$")
    if ((-not $masterStatusMatch.Success) -or ($masterStatusMatch.Groups["status"].Value.Trim() -ne "Accept$($eAcute)e")) {
        continue
    }

    $currentContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $adrFile.FullName
    $currentDecision = Get-MarkdownSectionContent -Content $currentContent -Heading "D$($eAcute)cision"
    $masterDecision = Get-MarkdownSectionContent -Content $masterContent -Heading "D$($eAcute)cision"

    if ($currentDecision -ne $masterDecision) {
        throw "ADR accept$($eAcute)e modifi$($eAcute)e silencieusement dans sa section D$($eAcute)cision: $id"
    }
}

Assert-Regex -Content $indexContent -Pattern "(?m)^## R.gles de maintenance\s*$" -Message "L'index ADR ne contient pas les r$($eGrave)gles de maintenance."

if ($technicalNumbers.Count -eq 0) {
    throw "Aucune ADR technique n'est pr$($eAcute)sente."
}

if ($dddNumbers.Count -eq 0) {
    throw "Aucune DDD-ADR n'est pr$($eAcute)sente."
}

$nextTechnical = ($technicalNumbers | Measure-Object -Maximum).Maximum + 1
$nextDdd = ($dddNumbers | Measure-Object -Maximum).Maximum + 1
$expectedNextTechnical = "Prochaine ADR technique: ADR-{0:000}" -f $nextTechnical
$expectedNextDdd = "Prochaine DDD-ADR: DDD-ADR-{0:000}" -f $nextDdd

if ($indexContent -notmatch [regex]::Escape($expectedNextTechnical)) {
    throw "L'index ADR ne d$($eAcute)clare pas la prochaine ADR technique attendue: $expectedNextTechnical"
}

if ($indexContent -notmatch [regex]::Escape($expectedNextDdd)) {
    throw "L'index ADR ne d$($eAcute)clare pas la prochaine DDD-ADR attendue: $expectedNextDdd"
}

$specDecisionIds = Get-SpecSection3DecisionIds -Path $specPath
$specDecisionSet = New-Object System.Collections.Generic.HashSet[string]

foreach ($id in $specDecisionIds) {
    if (-not $specDecisionSet.Add($id)) {
        throw "D$($eAcute)cision ADR dupliqu$($eAcute)e dans la section 3 de la sp$($eAcute)cification: $id"
    }

    if (-not $adrById.ContainsKey($id)) {
        throw "D$($eAcute)cision structurante de la section 3 sans ADR mat$($eAcute)rialis$($eAcute)e: $id"
    }
}

Write-Host "Syst$($eGrave)me ADR valide: $($adrFiles.Count) ADR contr$($oCircumflex)l$($eAcute)es, $($specDecisionIds.Count) d$($eAcute)cisions section 3 mat$($eAcute)rialis$($eAcute)es."
