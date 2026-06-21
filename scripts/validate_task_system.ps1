$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$tasksDir = Join-Path $repoRoot "docs/tasks"
$conventionPath = Join-Path $tasksDir "README.md"

$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8
$aGrave = [char] 0x00E0
$aCircumflex = [char] 0x00E2

$allowedRootFiles = @("README.md")
$allowedMilestoneFiles = @("journal.md")

$requiredConventionMarkers = @(
    "docs/tasks/milestone_NNN",
    "NNNN_slug.md",
    "0001_verifier_precondition_green.md",
    "Given",
    "When",
    "Then",
    "Commit RED",
    "Commit GREEN",
    "Commandes de validation",
    "slug"
)

$requiredHeadings = @(
    "Milestone",
    "Contexte DDD",
    "Blocages Ou Pr$($eAcute)conditions",
    "T$($aCircumflex)ches"
)

$requiredSingleLineFields = @(
    "But m$($eAcute)tier",
    "Port$($eAcute)e DDD",
    "Tests d'acceptation $($aGrave) $($eAcute)crire",
    "Tests unitaires $($aGrave) $($eAcute)crire",
    "Impl$($eAcute)mentation attendue",
    "Invariants et garde-fous",
    "D$($eAcute)pendances",
    "Commandes de validation",
    "Commit RED",
    "Commit GREEN"
)

function Assert-PathExists {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $PathType,

        [Parameter(Mandatory = $true)]
        [string] $Message
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

function Assert-ConventionDocument {
    Assert-PathExists `
        -Path $conventionPath `
        -PathType "Leaf" `
        -Message "Convention des tâches absente: docs/tasks/README.md"

    $content = Get-Content -Raw -Encoding UTF8 -LiteralPath $conventionPath

    foreach ($marker in $requiredConventionMarkers) {
        if (-not $content.Contains($marker)) {
            throw "La convention des tâches ne mentionne pas le marqueur obligatoire: $marker"
        }
    }
}

function Assert-MilestoneDependenciesInMaster {
    param(
        [Parameter(Mandatory = $true)]
        [int] $MilestoneNumber
    )

    if ($MilestoneNumber -eq 0) {
        return
    }

    for ($requiredMilestone = 0; $requiredMilestone -lt $MilestoneNumber; $requiredMilestone++) {
        $requiredPath = "docs/tasks/milestone_{0:000}" -f $requiredMilestone
        $output = & git -C $repoRoot ls-tree -r --name-only master -- $requiredPath 2>&1

        if ($LASTEXITCODE -ne 0) {
            throw "Impossible de vérifier les dépendances amont dans master pour $requiredPath. Sortie git: $($output -join "`n")"
        }

        if (@($output | Where-Object { $_ -like "$requiredPath/*" }).Count -eq 0) {
            throw "Milestone amont absent de master pour le dossier aval: $requiredPath"
        }
    }
}

function Assert-TaskContent {
    param(
        [Parameter(Mandatory = $true)]
        [System.IO.FileInfo] $TaskFile,

        [Parameter(Mandatory = $true)]
        [int] $TaskNumber
    )

    $content = Get-Content -Raw -Encoding UTF8 -LiteralPath $TaskFile.FullName
    $taskId = "T-{0:000}" -f $TaskNumber

    Assert-Regex `
        -Content $content `
        -Pattern "(?m)^# $([regex]::Escape($taskId)) - .+\S$" `
        -Message "Titre de tâche invalide ou absent: $($TaskFile.Name)"

    foreach ($heading in $requiredHeadings) {
        Assert-Regex `
            -Content $content `
            -Pattern "(?m)^## $([regex]::Escape($heading))\s*$" `
            -Message "Section obligatoire absente dans $($TaskFile.Name): ## $heading"
    }

    Assert-Regex `
        -Content $content `
        -Pattern "(?m)^### $([regex]::Escape($taskId)) - .+\S$" `
        -Message "Sous-titre de tâche invalide ou absent: $($TaskFile.Name)"

    foreach ($field in $requiredSingleLineFields) {
        Assert-Regex `
            -Content $content `
            -Pattern "(?m)^- $([regex]::Escape($field)):\s*\S.*$" `
            -Message "Champ obligatoire absent ou vide dans $($TaskFile.Name): $field"
    }

    Assert-Regex `
        -Content $content `
        -Pattern "(?ms)^- Sc$($eAcute)nario BDD:\s*`r?`n\s+- Given\s+\S.*`r?`n\s+- When\s+\S.*`r?`n\s+- Then\s+\S.*" `
        -Message "Sc$($eAcute)nario BDD Given-When-Then absent ou incomplet: $($TaskFile.Name)"
}

function Assert-MilestoneDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [System.IO.DirectoryInfo] $MilestoneDirectory
    )

    $match = [regex]::Match($MilestoneDirectory.Name, "^milestone_(?<number>\d{3})$")
    if (-not $match.Success) {
        throw "Dossier de milestone invalide: $($MilestoneDirectory.Name)"
    }

    $milestoneNumber = [int] $match.Groups["number"].Value
    Assert-MilestoneDependenciesInMaster -MilestoneNumber $milestoneNumber

    $taskFiles = New-Object System.Collections.Generic.List[object]
    $taskNumbers = New-Object System.Collections.Generic.HashSet[int]

    foreach ($child in (Get-ChildItem -LiteralPath $MilestoneDirectory.FullName | Sort-Object Name)) {
        if ($child.PSIsContainer) {
            throw "Sous-dossier interdit dans $($MilestoneDirectory.Name): $($child.Name)"
        }

        if ($allowedMilestoneFiles -contains $child.Name) {
            continue
        }

        $fileMatch = [regex]::Match($child.Name, "^(?<number>\d{4})_(?<slug>[a-z0-9]+(?:_[a-z0-9]+)*)\.md$")
        if (-not $fileMatch.Success) {
            throw "Fichier de tâche invalide dans $($MilestoneDirectory.Name): $($child.Name)"
        }

        $taskNumber = [int] $fileMatch.Groups["number"].Value
        if (-not $taskNumbers.Add($taskNumber)) {
            throw "Numéro de tâche dupliqué dans $($MilestoneDirectory.Name): $($fileMatch.Groups["number"].Value)"
        }

        $taskFiles.Add([pscustomobject] @{
            Number = $taskNumber
            File = $child
        })
    }

    if ($taskFiles.Count -eq 0) {
        throw "Aucune tâche de milestone trouvée dans $($MilestoneDirectory.Name)."
    }

    $orderedTaskFiles = @($taskFiles | Sort-Object Number)
    if ($orderedTaskFiles[0].File.Name -ne "0001_verifier_precondition_green.md") {
        throw "La première tâche de $($MilestoneDirectory.Name) doit être 0001_verifier_precondition_green.md"
    }

    for ($index = 0; $index -lt $orderedTaskFiles.Count; $index++) {
        $expectedNumber = $index + 1
        $actualNumber = $orderedTaskFiles[$index].Number

        if ($actualNumber -ne $expectedNumber) {
            throw "Numéro de tâche non séquentiel dans $($MilestoneDirectory.Name). Attendu: {0:0000}. Obtenu: {1:0000}" -f $expectedNumber, $actualNumber
        }

        Assert-TaskContent -TaskFile $orderedTaskFiles[$index].File -TaskNumber $actualNumber
    }
}

Assert-PathExists `
    -Path $tasksDir `
    -PathType "Container" `
    -Message "Le répertoire docs/tasks est absent."

Assert-ConventionDocument

$milestoneDirectories = New-Object System.Collections.Generic.List[System.IO.DirectoryInfo]

foreach ($child in (Get-ChildItem -LiteralPath $tasksDir | Sort-Object Name)) {
    if ($child.PSIsContainer) {
        if ($child.Name -notmatch "^milestone_\d{3}$") {
            throw "Entrée invalide dans docs/tasks: $($child.Name)"
        }

        $milestoneDirectories.Add($child)
        continue
    }

    if ($allowedRootFiles -notcontains $child.Name) {
        throw "Fichier non autorisé dans docs/tasks: $($child.Name)"
    }
}

if ($milestoneDirectories.Count -eq 0) {
    throw "Aucun dossier de milestone trouvé dans docs/tasks."
}

foreach ($milestoneDirectory in $milestoneDirectories) {
    Assert-MilestoneDirectory -MilestoneDirectory $milestoneDirectory
}

$taskCount = (Get-ChildItem -LiteralPath $tasksDir -Recurse -File |
    Where-Object { $_.Name -match "^\d{4}_[a-z0-9]+(?:_[a-z0-9]+)*\.md$" }).Count

Write-Host "Système de tâches valide: $($milestoneDirectories.Count) milestone(s), $taskCount tâche(s) contrôlée(s)."
