$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$adrDir = Join-Path $repoRoot "docs/adr"

$requiredFiles = @(
    "README.md",
    "TEMPLATE.md",
    "index.md"
)

if (-not (Test-Path -LiteralPath $adrDir -PathType Container)) {
    throw "Le répertoire docs/adr est absent."
}

foreach ($fileName in $requiredFiles) {
    $path = Join-Path $adrDir $fileName
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Le fichier ADR obligatoire est absent: docs/adr/$fileName"
    }
}

$allowedStatusPattern = "^(Propos.e|Accept.e|Remplac.e|D.pr.ci.e|Rejet.e)$"
$adrFiles = Get-ChildItem -LiteralPath $adrDir -File |
    Where-Object { $_.Name -notin $requiredFiles } |
    Sort-Object Name

if ($adrFiles.Count -eq 0) {
    throw "Aucune ADR n'est présente dans docs/adr."
}

$indexContent = Get-Content -Raw -Encoding UTF8 (Join-Path $adrDir "index.md")
$technicalNumbers = New-Object System.Collections.Generic.HashSet[int]
$dddNumbers = New-Object System.Collections.Generic.HashSet[int]

foreach ($adrFile in $adrFiles) {
    if ($adrFile.Name -notmatch "^(ADR|DDD-ADR)-(\d{3})-[a-z0-9]+(-[a-z0-9]+)*\.md$") {
        throw "Nom ADR invalide: $($adrFile.Name)"
    }

    $family = $Matches[1]
    $number = [int]$Matches[2]
    if ($family -eq "ADR") {
        $numberSet = $technicalNumbers
    }
    else {
        $numberSet = $dddNumbers
    }

    if (-not $numberSet.Add($number)) {
        throw "Numéro ADR dupliqué dans la famille ${family}: $($Matches[2])"
    }

    $content = Get-Content -Raw -Encoding UTF8 $adrFile.FullName
    $requiredPatterns = @(
        "^# $family-\d{3} - .+",
        "\*\*Statut\s*:\*\*",
        "\*\*Date\s*:\*\*",
        "\*\*D.cideurs\s*:\*\*",
        "\*\*Source\s*:\*\*",
        "## Contexte",
        "## D.cision",
        "## Cons.quences",
        "## Impact d'impl.mentation",
        "## Liens de tra.abilit."
    )

    foreach ($pattern in $requiredPatterns) {
        if ($content -notmatch $pattern) {
            throw "ADR incomplète ($($adrFile.Name)): motif manquant '$pattern'"
        }
    }

    $statusMatch = [regex]::Match($content, "\*\*Statut\s*:\*\*\s*(.+)")
    if (-not $statusMatch.Success) {
        throw "Statut ADR introuvable: $($adrFile.Name)"
    }

    $status = $statusMatch.Groups[1].Value.Trim()
    if ($status -notmatch $allowedStatusPattern) {
        throw "Statut ADR non autorisé dans $($adrFile.Name): $status"
    }

    if ($indexContent -notmatch [regex]::Escape("]($($adrFile.Name))")) {
        throw "ADR absente de l'index: $($adrFile.Name)"
    }
}

if ($indexContent -notmatch "## R.gles de maintenance") {
    throw "L'index ADR ne contient pas les règles de maintenance."
}

if ($indexContent -notmatch "Prochaine ADR technique") {
    throw "L'index ADR ne déclare pas la prochaine ADR technique."
}

if ($indexContent -notmatch "Prochaine DDD-ADR") {
    throw "L'index ADR ne déclare pas la prochaine DDD-ADR."
}

Write-Host "Système ADR valide: $($adrFiles.Count) ADR contrôlées."
