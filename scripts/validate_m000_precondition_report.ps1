param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string] $Path
)

$ErrorActionPreference = "Stop"

function Assert-Condition {
    param(
        [Parameter(Mandatory = $true)]
        [bool] $Condition,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Assert-ReportMatch {
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

function Get-PreconditionRows {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    $rows = @()

    foreach ($line in ($Content -split "`r?`n")) {
        $match = [regex]::Match($line, '^\|\s*`([^`]*)`\s*\|\s*`([^`]*)`\s*\|\s*`([^`]*)`\s*\|')

        if ($match.Success) {
            $rows += [pscustomobject] @{
                Item = $match.Groups[1].Value.Trim()
                DateUtc = $match.Groups[2].Value.Trim()
                Result = $match.Groups[3].Value.Trim()
                Line = $line
            }
        }
    }

    return $rows
}

function Assert-RequiredRow {
    param(
        [Parameter(Mandatory = $true)]
        [object[]] $Rows,

        [Parameter(Mandatory = $true)]
        [string] $Item,

        [Parameter(Mandatory = $true)]
        [string] $ExpectedResult
    )

    $matchingRows = @($Rows | Where-Object { $_.Item -eq $Item })

    if ($matchingRows.Count -ne 1) {
        throw "L'entrée obligatoire est absente ou dupliquée: $Item"
    }

    if ($matchingRows[0].Result -ne $ExpectedResult) {
        throw "Résultat inattendu pour '$Item'. Attendu: $ExpectedResult. Obtenu: $($matchingRows[0].Result)"
    }
}

if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    throw "Rapport de précondition absent: $Path"
}

$resolvedPath = Resolve-Path -LiteralPath $Path
$content = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedPath

Assert-ReportMatch `
    -Content $content `
    -Pattern '\*\*.*master.*:\*\*\s*`[0-9a-f]{40}`' `
    -Message "La révision master observée est absente ou invalide."

Assert-ReportMatch `
    -Content $content `
    -Pattern 'Given.*`master`.*v4\.1.*ADR\.' `
    -Message "Le Given du scénario BDD est absent."

Assert-ReportMatch `
    -Content $content `
    -Pattern 'When.*M-000.*\.' `
    -Message "Le When du scénario BDD est absent."

Assert-ReportMatch `
    -Content $content `
    -Pattern 'Then.*validations existantes.*commandes absentes.*versionn.*ambigu.*\.' `
    -Message "Le Then du scénario BDD est absent."

$rows = @(Get-PreconditionRows -Content $content)

if ($rows.Count -eq 0) {
    throw "Aucune entrée datée de précondition n'a été trouvée."
}

foreach ($row in $rows) {
    Assert-Condition `
        -Condition (-not [string]::IsNullOrWhiteSpace($row.Item)) `
        -Message "Une entrée de précondition contient un libellé vide."

    Assert-Condition `
        -Condition (-not [string]::IsNullOrWhiteSpace($row.DateUtc)) `
        -Message "Une entrée de précondition n'est pas datée: $($row.Line)"

    Assert-Condition `
        -Condition ($row.DateUtc -match '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$') `
        -Message "Date UTC invalide pour '$($row.Item)': $($row.DateUtc)"

    Assert-Condition `
        -Condition (($row.Result -eq "GREEN") -or ($row.Result -eq "RED")) `
        -Message "État inconnu pour '$($row.Item)': $($row.Result)"
}

Assert-RequiredRow `
    -Rows $rows `
    -Item "git fetch origin --prune" `
    -ExpectedResult "GREEN"

Assert-RequiredRow `
    -Rows $rows `
    -Item "git ls-tree -r --name-only master -- docs/tasks docs/adr docs/specs" `
    -ExpectedResult "GREEN"

Assert-RequiredRow `
    -Rows $rows `
    -Item "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_adr_system.ps1" `
    -ExpectedResult "GREEN"

Assert-RequiredRow `
    -Rows $rows `
    -Item ".\scripts\test.ps1" `
    -ExpectedResult "RED"

Assert-RequiredRow `
    -Rows $rows `
    -Item ".\scripts\lint.ps1" `
    -ExpectedResult "RED"

Assert-RequiredRow `
    -Rows $rows `
    -Item "docs/tasks/milestone_000 dans master" `
    -ExpectedResult "RED"

Write-Host "Rapport de précondition M-000 valide: $($rows.Count) entrées contrôlées."
