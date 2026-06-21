param(
    [Parameter(Mandatory = $false)]
    [string] $Path
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$matrixPath = $Path
$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8
$cCedilla = [char] 0x00E7
$traceabilityLabel = "tra$($cCedilla)abilit$($eAcute)"

$requiredHeaders = @(
    "Exigence",
    "Source",
    "Statut",
    "Test",
    "Commande",
    "Code",
    "ADR",
    "Justification ADR"
)

$allowedStatuses = @(
    "Couvert",
    "Partiel",
    "Planifi$($eAcute)",
    "Hors p$($eAcute)rim$($eGrave)tre M-000"
)

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

function Split-MarkdownRow {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Line
    )

    return @($Line.Trim().Trim("|").Split("|") | ForEach-Object { $_.Trim() })
}

function Assert-RepositoryRelativeFile {
    param(
        [Parameter(Mandatory = $true)]
        [string] $RelativePath,

        [Parameter(Mandatory = $true)]
        [string] $Context
    )

    Assert-Condition `
        -Condition (-not [string]::IsNullOrWhiteSpace($RelativePath)) `
        -Message "Chemin vide dans la matrice: $Context"

    Assert-Condition `
        -Condition (-not [System.IO.Path]::IsPathRooted($RelativePath)) `
        -Message "Chemin absolu interdit dans la matrice ($Context): $RelativePath"

    $normalizedRelativePath = $RelativePath.Replace("/", [System.IO.Path]::DirectorySeparatorChar).Replace("\", [System.IO.Path]::DirectorySeparatorChar)
    $resolvedRepositoryRoot = [System.IO.Path]::GetFullPath($repoRoot)
    $candidatePath = [System.IO.Path]::GetFullPath((Join-Path $resolvedRepositoryRoot $normalizedRelativePath))
    $repositoryPrefix = $resolvedRepositoryRoot.TrimEnd("\", "/") + [System.IO.Path]::DirectorySeparatorChar

    Assert-Condition `
        -Condition ($candidatePath.StartsWith($repositoryPrefix, [System.StringComparison]::OrdinalIgnoreCase)) `
        -Message "Chemin hors dépôt interdit dans la matrice ($Context): $RelativePath"

    Assert-Condition `
        -Condition (Test-Path -LiteralPath $candidatePath -PathType Leaf) `
        -Message "Chemin introuvable dans la matrice ($Context): $RelativePath"
}

function Convert-ToMatrixRelativePath {
    param(
        [Parameter(Mandatory = $true)]
        [string] $RelativePath
    )

    return $RelativePath.TrimStart(".", "/", "\").Replace("\", "/")
}

function Get-ExistingAdrIds {
    $adrDir = Join-Path $repoRoot "docs/adr"

    Assert-Condition `
        -Condition (Test-Path -LiteralPath $adrDir -PathType Container) `
        -Message "Répertoire ADR absent: docs/adr"

    $ids = New-Object System.Collections.Generic.HashSet[string]

    foreach ($file in (Get-ChildItem -LiteralPath $adrDir -File)) {
        $match = [regex]::Match($file.Name, "^(?<id>(?:DDD-)?ADR-\d{3})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
        if ($match.Success) {
            [void] $ids.Add($match.Groups["id"].Value)
        }
    }

    return $ids
}

function Assert-AdrCell {
    param(
        [Parameter(Mandatory = $true)]
        [string] $AdrCell,

        [Parameter(Mandatory = $true)]
        [string] $Justification,

        [Parameter(Mandatory = $true)]
        [System.Collections.Generic.HashSet[string]] $ExistingAdrIds,

        [Parameter(Mandatory = $true)]
        [string] $RequirementId
    )

    if ($AdrCell -eq "Non requise") {
        Assert-Condition `
            -Condition ($Justification -match "^Aucune d$($eAcute)cision structurante") `
            -Message "Justification ADR insuffisante pour ${RequirementId}: $Justification"
        return
    }

    $adrMatches = [regex]::Matches($AdrCell, "(?:DDD-)?ADR-\d{3}")
    Assert-Condition `
        -Condition ($adrMatches.Count -gt 0) `
        -Message "Cellule ADR invalide pour ${RequirementId}: $AdrCell"

    $remainingText = [regex]::Replace($AdrCell, "(?:DDD-)?ADR-\d{3}", "")
    Assert-Condition `
        -Condition (($remainingText -eq "") -or ($remainingText -match "^[\s,;]+$")) `
        -Message "Cellule ADR invalide pour ${RequirementId}: $AdrCell"

    foreach ($match in $adrMatches) {
        $adrId = $match.Value
        Assert-Condition `
            -Condition ($ExistingAdrIds.Contains($adrId)) `
            -Message "ADR inexistante dans la matrice pour ${RequirementId}: $adrId"
    }
}

function Assert-CommandCell {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Command,

        [Parameter(Mandatory = $true)]
        [string] $Status,

        [Parameter(Mandatory = $true)]
        [string] $RequirementId
    )

    $commandPattern = "^powershell\s+-NoProfile\s+-ExecutionPolicy\s+Bypass\s+-File\s+(?<script>\.?[\\/][^\s;|&]+)(?:\s+-Path\s+(?<pathArg>\.?[\\/][^\s;|&]+))?\s*$"

    if ($Status -eq "Couvert") {
        Assert-Condition `
            -Condition ($Command -match $commandPattern) `
            -Message "Exigence couverte sans commande PowerShell vérifiable: $RequirementId"
    }
    elseif ($Command -match "^Non applicable:\s+\S") {
        return
    }
    else {
        Assert-Condition `
            -Condition ($Command -match $commandPattern) `
            -Message "Commande invalide pour ${RequirementId}: $Command"
    }

    $scriptPath = $Matches["script"]
    $scriptPath = Convert-ToMatrixRelativePath -RelativePath $scriptPath

    Assert-RepositoryRelativeFile `
        -RelativePath $scriptPath `
        -Context "commande ${RequirementId}"

    if ($Matches["pathArg"]) {
        $pathArgument = $Matches["pathArg"].TrimStart(".", "/", "\")
        Assert-RepositoryRelativeFile `
            -RelativePath $pathArgument `
            -Context "argument -Path ${RequirementId}"
    }

    return $scriptPath
}

function Assert-M000GateProof {
    param(
        [Parameter(Mandatory = $true)]
        [string] $CodePath,

        [Parameter(Mandatory = $true)]
        [string] $TestPath,

        [Parameter(Mandatory = $false)]
        [AllowNull()]
        [string] $CommandScriptPath,

        [Parameter(Mandatory = $true)]
        [string] $RequirementId
    )

    $normalizedCodePath = Convert-ToMatrixRelativePath -RelativePath $CodePath
    if ($normalizedCodePath -notin @("scripts/test.ps1", "scripts/lint.ps1")) {
        return
    }

    $expectedProofPath = "tests/governance/validate_m000_validation_commands_acceptance.ps1"
    $normalizedTestPath = Convert-ToMatrixRelativePath -RelativePath $TestPath
    $normalizedCommandScriptPath = ""

    if ($null -ne $CommandScriptPath) {
        $normalizedCommandScriptPath = Convert-ToMatrixRelativePath -RelativePath $CommandScriptPath
    }

    Assert-Condition `
        -Condition (($normalizedTestPath -eq $expectedProofPath) -and ($normalizedCommandScriptPath -eq $expectedProofPath)) `
        -Message "Preuve de gate M-000 invalide pour ${RequirementId}: test et commande doivent ex$($eAcute)cuter $expectedProofPath"
}

if (-not $PSBoundParameters.ContainsKey("Path")) {
    $matrixPath = Join-Path $repoRoot "docs/traceability/matrix.md"
}
else {
    Assert-Condition `
        -Condition (-not [string]::IsNullOrWhiteSpace($matrixPath)) `
        -Message "Chemin de matrice vide."

    if (-not [System.IO.Path]::IsPathRooted($matrixPath)) {
        $matrixPath = Join-Path $repoRoot $matrixPath
    }
}

Assert-Condition `
    -Condition (Test-Path -LiteralPath $matrixPath -PathType Leaf) `
    -Message "Matrice de $traceabilityLabel absente: $matrixPath"

$content = Get-Content -Encoding UTF8 -LiteralPath $matrixPath
$headerIndex = -1

for ($index = 0; $index -lt $content.Count; $index++) {
    if ($content[$index] -match "^\|\s*Exigence\s*\|") {
        $headerIndex = $index
        break
    }
}

Assert-Condition `
    -Condition ($headerIndex -ge 0) `
    -Message "En-tête de matrice introuvable."

$headers = Split-MarkdownRow -Line $content[$headerIndex]

Assert-Condition `
    -Condition ($headers.Count -eq $requiredHeaders.Count) `
    -Message "Nombre de colonnes invalide dans la matrice."

for ($index = 0; $index -lt $requiredHeaders.Count; $index++) {
    Assert-Condition `
        -Condition ($headers[$index] -eq $requiredHeaders[$index]) `
        -Message "Colonne invalide dans la matrice. Attendu: $($requiredHeaders[$index]). Obtenu: $($headers[$index])"
}

Assert-Condition `
    -Condition (($headerIndex + 1) -lt $content.Count) `
    -Message "Séparateur de table absent dans la matrice."

$separatorCells = Split-MarkdownRow -Line $content[$headerIndex + 1]
Assert-Condition `
    -Condition (($separatorCells.Count -eq $requiredHeaders.Count) -and (@($separatorCells | Where-Object { $_ -notmatch "^-{3,}$" }).Count -eq 0)) `
    -Message "Séparateur de table invalide dans la matrice."

$existingAdrIds = Get-ExistingAdrIds
$requirementIds = New-Object System.Collections.Generic.HashSet[string]
$rows = New-Object System.Collections.Generic.List[object]

for ($index = $headerIndex + 2; $index -lt $content.Count; $index++) {
    $line = $content[$index]

    if ($line -notmatch "^\|") {
        continue
    }

    $cells = Split-MarkdownRow -Line $line
    Assert-Condition `
        -Condition ($cells.Count -eq $requiredHeaders.Count) `
        -Message "Ligne de matrice avec nombre de cellules invalide: $line"

    for ($cellIndex = 0; $cellIndex -lt $cells.Count; $cellIndex++) {
        Assert-Condition `
            -Condition (-not [string]::IsNullOrWhiteSpace($cells[$cellIndex])) `
            -Message "Cellule vide dans la matrice, colonne $($requiredHeaders[$cellIndex]), ligne $($index + 1)."
    }

    $row = [ordered] @{}
    for ($cellIndex = 0; $cellIndex -lt $requiredHeaders.Count; $cellIndex++) {
        $row[$requiredHeaders[$cellIndex]] = $cells[$cellIndex]
    }

    $requirementId = $row["Exigence"]
    Assert-Condition `
        -Condition ($requirementId -match "^REQ-[A-Z0-9]+(?:-[A-Z0-9]+)*-\d{3}$") `
        -Message "Identifiant d'exigence invalide: $requirementId"

    Assert-Condition `
        -Condition ($requirementIds.Add($requirementId)) `
        -Message "Identifiant d'exigence dupliqué: $requirementId"

    $status = $row["Statut"]
    Assert-Condition `
        -Condition ($allowedStatuses -contains $status) `
        -Message "Statut de traçabilité non autorisé pour ${requirementId}: $status"

    Assert-RepositoryRelativeFile -RelativePath $row["Source"] -Context "source ${requirementId}"
    Assert-RepositoryRelativeFile -RelativePath $row["Test"] -Context "test ${requirementId}"
    Assert-RepositoryRelativeFile -RelativePath $row["Code"] -Context "code ${requirementId}"

    $commandScriptPath = Assert-CommandCell -Command $row["Commande"] -Status $status -RequirementId $requirementId
    Assert-M000GateProof -CodePath $row["Code"] -TestPath $row["Test"] -CommandScriptPath $commandScriptPath -RequirementId $requirementId
    Assert-AdrCell -AdrCell $row["ADR"] -Justification $row["Justification ADR"] -ExistingAdrIds $existingAdrIds -RequirementId $requirementId

    $rows.Add([pscustomobject] $row)
}

Assert-Condition `
    -Condition ($rows.Count -gt 0) `
    -Message "Aucune exigence n'est déclarée dans la matrice de traçabilité."

Write-Host "Matrice de $traceabilityLabel valide: $($rows.Count) exigence(s) contr$([char] 0x00F4)l$($eAcute)e(s)."
