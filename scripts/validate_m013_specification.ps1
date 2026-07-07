param(
    [Parameter(Mandatory = $false)]
    [string] $Path
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$defaultSpecificationPath = "docs/specs/m013_durcissement_acceptation_v1.md"

$requiredSections = @(
    "# M-013 - Durcissement et acceptation V1",
    "## Statut",
    "## Scénario BDD",
    "## Mission M-013",
    "## Contexte DDD",
    "## Langage ubiquitaire M-013",
    "## Critères V1 et écarts M-012",
    "## Statuts d'écarts V1",
    "## Objets de gouvernance M-013",
    "## Politiques d'acceptation V1",
    "## Sécurité réseau Spark",
    "## Sauvegarde et restauration",
    "## Rétention",
    "## Monitoring local",
    "## Runbooks",
    "## Documentation utilisateur",
    "## Anti-patterns interdits V1",
    "## Rapport d'acceptation V1",
    "## Comportements vérifiables M-013",
    "## Commandes de validation",
    "## Exclusions M-013"
)

$requiredMarkers = @(
    "Given le système complet a été mesuré par M-012 et les critères V1 sont publiés.",
    "When la spécification M-013 est publiée.",
    "Then chaque comportement de durcissement nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.",
    "Aucun fallback silencieux n'est autorisé dans M-013.",
    "Aucun critère V1 n'est supprimé.",
    "écart non accepté interdit le V1AcceptanceReport"
)

$requiredArtifacts = @(
    "V1AcceptanceGate",
    "RegressionSuite",
    "SecurityAuditReport",
    "BackupRestoreDrill",
    "LocalMonitoringProfile",
    "RetentionPolicy",
    "Runbook",
    "V1AcceptanceReport"
)

$requiredCommands = @(
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_m013_specification_acceptance.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_m013_specification_unit.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_specification.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1"
)

$requiredAdrIds = @(
    "ADR-007",
    "ADR-008",
    "ADR-009",
    "ADR-010",
    "ADR-013",
    "DDD-ADR-006",
    "DDD-ADR-004",
    "DDD-ADR-010",
    "DDD-ADR-011"
)

$expectedGapStatuses = @{
    SP = "différé"
    KA = "différé"
    EG = "satisfait"
    RA = "différé"
    CV = "satisfait"
    SD = "bloquant"
    LLM = "bloquant"
    EX = "satisfait"
}

$expectedPolicies = @(
    "V1AcceptanceGatePolicy",
    "RegressionSuitePolicy",
    "SecurityAuditPolicy",
    "BackupRestorePolicy",
    "RetentionPolicy",
    "MonitoringPolicy",
    "RunbookPolicy",
    "UserDocumentationPolicy",
    "ForbiddenAntiPatternPolicy",
    "V1AcceptanceReportPolicy"
)

$expectedBehaviors = @(
    @{ Name = "V1-001 - Spécification exécutable M-013"; Test = "T-002"; Adr = @("ADR-007", "ADR-008", "ADR-009", "ADR-010", "DDD-ADR-006", "DDD-ADR-010", "DDD-ADR-011"); Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_specification.ps1" },
    @{ Name = "V1-002 - Contrôle des écarts V1 M-012"; Test = "T-003"; Adr = @("ADR-010", "DDD-ADR-010", "DDD-ADR-011"); Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_v1_gap_decisions_acceptance.ps1" },
    @{ Name = "V1-003 - Suite de régression V1"; Test = "T-004"; Adr = @("ADR-010", "DDD-ADR-011"); Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_v1_regression_suite_acceptance.ps1" },
    @{ Name = "V1-004 - Audit réseau et sécurité Spark"; Test = "T-005"; Adr = @("ADR-007", "ADR-008", "ADR-009"); Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_m013_network_security_acceptance.ps1" },
    @{ Name = "V1-005 - Pannes Spark sans fallback"; Test = "T-006"; Adr = @("ADR-008", "ADR-009", "DDD-ADR-006"); Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_spark_failure_acceptance.ps1" },
    @{ Name = "V1-006 - Sauvegarde chiffrée et restauration testée"; Test = "T-007"; Adr = @("ADR-009", "ADR-013", "DDD-ADR-004", "DDD-ADR-010"); Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_backup_restore_acceptance.ps1" },
    @{ Name = "V1-007 - Rétention et purge administrative"; Test = "T-008"; Adr = @("DDD-ADR-010"); Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_retention_policy_acceptance.ps1" },
    @{ Name = "V1-008 - Monitoring local d'exploitation"; Test = "T-009"; Adr = @("ADR-008", "ADR-009", "ADR-010"); Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_local_monitoring_acceptance.ps1" },
    @{ Name = "V1-009 - Runbooks et documentation utilisateur"; Test = "T-010"; Adr = @("ADR-010"); Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_runbooks_user_docs_acceptance.ps1" },
    @{ Name = "V1-010 - Anti-patterns interdits V1"; Test = "T-011"; Adr = @("ADR-007", "ADR-008", "ADR-009", "DDD-ADR-006", "DDD-ADR-010"); Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_forbidden_antipatterns_acceptance.ps1" },
    @{ Name = "V1-011 - Rapport d'acceptation V1"; Test = "T-012"; Adr = @("ADR-010", "DDD-ADR-010", "DDD-ADR-011"); Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_v1_acceptance_report_acceptance.ps1" }
)

function Assert-M013Contains {
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

function Split-M013MarkdownRow {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Line
    )

    $trimmed = $Line.Trim()
    if (-not ($trimmed.StartsWith("|") -and $trimmed.EndsWith("|"))) {
        throw "Ligne de table Markdown invalide: $Line"
    }

    return @($trimmed.Trim("|").Split("|") | ForEach-Object { $_.Trim() })
}

function Read-M013MarkdownTable {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string[]] $Lines,

        [Parameter(Mandatory = $true)]
        [string[]] $RequiredHeaders,

        [Parameter(Mandatory = $true)]
        [string] $TableName
    )

    $headerIndex = -1
    for ($index = 0; $index -lt $Lines.Count; $index++) {
        if ($Lines[$index] -notmatch "^\|") {
            continue
        }

        $headers = Split-M013MarkdownRow -Line $Lines[$index]
        if (($headers.Count -eq $RequiredHeaders.Count) -and (@(Compare-Object -ReferenceObject $RequiredHeaders -DifferenceObject $headers -SyncWindow 0).Count -eq 0)) {
            $headerIndex = $index
            break
        }
    }

    if ($headerIndex -lt 0) {
        throw "Table $TableName absente ou en-têtes invalides: $($RequiredHeaders -join ', ')"
    }

    if (($headerIndex + 1) -ge $Lines.Count) {
        throw "Séparateur absent pour la table $TableName."
    }

    $separatorCells = Split-M013MarkdownRow -Line $Lines[$headerIndex + 1]
    if (($separatorCells.Count -ne $RequiredHeaders.Count) -or (@($separatorCells | Where-Object { $_ -notmatch "^-{3,}$" }).Count -gt 0)) {
        throw "Séparateur invalide pour la table $TableName."
    }

    $rows = New-Object System.Collections.Generic.List[hashtable]
    for ($index = $headerIndex + 2; $index -lt $Lines.Count; $index++) {
        $line = $Lines[$index]
        if ($line -notmatch "^\|") {
            break
        }

        $cells = Split-M013MarkdownRow -Line $line
        if ($cells.Count -ne $RequiredHeaders.Count) {
            throw "Ligne de table $TableName avec nombre de cellules invalide: $line"
        }

        $row = @{}
        for ($cellIndex = 0; $cellIndex -lt $RequiredHeaders.Count; $cellIndex++) {
            $row[$RequiredHeaders[$cellIndex]] = $cells[$cellIndex]
        }
        $rows.Add($row)
    }

    if ($rows.Count -eq 0) {
        throw "Table $TableName sans ligne."
    }

    return $rows.ToArray()
}

function Assert-M013AdrToken {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $AdrId
    )

    $pattern = "(?<![A-Z0-9-])" + [regex]::Escape($AdrId) + "(?![A-Z0-9-])"
    if (-not [regex]::IsMatch($Content, $pattern)) {
        throw "ADR applicable absente: $AdrId"
    }
}

function Assert-M013NamedRows {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $Rows,

        [Parameter(Mandatory = $true)]
        [string] $NameColumn,

        [Parameter(Mandatory = $true)]
        [string[]] $RequiredColumns,

        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [string[]] $ExpectedNames,

        [Parameter(Mandatory = $true)]
        [string] $Label
    )

    $rowsByName = @{}
    foreach ($row in $Rows) {
        $name = $row[$NameColumn]
        if ([string]::IsNullOrWhiteSpace($name)) {
            throw "$Label sans nom."
        }
        if ($rowsByName.ContainsKey($name)) {
            throw "$Label dupliqué: $name"
        }

        foreach ($requiredColumn in $RequiredColumns) {
            if ([string]::IsNullOrWhiteSpace($row[$requiredColumn])) {
                throw "Colonne $requiredColumn vide pour $name."
            }
        }

        $rowsByName[$name] = $row
    }

    foreach ($expectedName in $ExpectedNames) {
        if (-not $rowsByName.ContainsKey($expectedName)) {
            throw "$Label attendu absent: $expectedName"
        }
    }

    return $rowsByName
}

function Assert-M013GapStatuses {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $Rows
    )

    $rowsByContext = Assert-M013NamedRows `
        -Rows $Rows `
        -NameColumn "Contexte" `
        -RequiredColumns @("Statut M-012", "Décision M-013", "Commande de preuve", "Blocage d'acceptation") `
        -ExpectedNames @($expectedGapStatuses.Keys) `
        -Label "Écart V1 M-013"

    foreach ($context in $expectedGapStatuses.Keys) {
        $expectedStatus = $expectedGapStatuses[$context]
        $actualStatus = $rowsByContext[$context]["Statut M-012"]
        if ($actualStatus -ne $expectedStatus) {
            throw "Statut d'écart V1 invalide pour $context. Attendu: $expectedStatus. Obtenu: $actualStatus"
        }
    }
}

function Assert-M013Behaviors {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $BehaviorRows
    )

    $behaviorsByName = Assert-M013NamedRows `
        -Rows $BehaviorRows `
        -NameColumn "Comportement" `
        -RequiredColumns @("Invariant", "Scénario BDD", "Test RED", "ADR", "Commande") `
        -ExpectedNames @($expectedBehaviors | ForEach-Object { $_.Name }) `
        -Label "Comportement M-013"

    foreach ($expectedBehavior in $expectedBehaviors) {
        $row = $behaviorsByName[$expectedBehavior.Name]
        if ($row["Test RED"] -ne $expectedBehavior.Test) {
            throw "Test RED invalide pour $($expectedBehavior.Name). Attendu: $($expectedBehavior.Test). Obtenu: $($row["Test RED"])"
        }
        if ($row["Commande"] -ne $expectedBehavior.Command) {
            throw "Commande invalide pour $($expectedBehavior.Name). Attendu: $($expectedBehavior.Command). Obtenu: $($row["Commande"])"
        }
        foreach ($adrId in $expectedBehavior.Adr) {
            Assert-M013AdrToken -Content $row["ADR"] -AdrId $adrId
        }
    }
}

function Assert-M013ForbiddenPatterns {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    $forbiddenPatterns = @(
        @{ Pattern = "fallback silencieux autoris"; Message = "Fallback silencieux autorisé interdit" },
        @{ Pattern = "acceptation implicite autoris"; Message = "Acceptation implicite autorisée interdite" },
        @{ Pattern = "seuil par d[ée]faut"; Message = "Seuil par défaut interdit" },
        @{ Pattern = "rend mTLS obligatoire sans ADR"; Message = "mTLS obligatoire sans ADR interdit" }
    )

    foreach ($forbiddenPattern in $forbiddenPatterns) {
        if ($Content -match $forbiddenPattern.Pattern) {
            throw $forbiddenPattern.Message + ": " + $Matches[0]
        }
    }
}

function Resolve-M013SpecificationPath {
    param(
        [Parameter(Mandatory = $false)]
        [AllowEmptyString()]
        [string] $InputPath
    )

    if ([string]::IsNullOrWhiteSpace($InputPath)) {
        $candidatePath = Join-Path $repoRoot $defaultSpecificationPath
    }
    elseif ([System.IO.Path]::IsPathRooted($InputPath)) {
        $candidatePath = $InputPath
    }
    else {
        $candidatePath = Join-Path $repoRoot $InputPath
    }

    $resolvedRepositoryRoot = [System.IO.Path]::GetFullPath($repoRoot)
    $resolvedCandidatePath = [System.IO.Path]::GetFullPath($candidatePath)
    $repositoryPrefix = $resolvedRepositoryRoot.TrimEnd("\", "/") + [System.IO.Path]::DirectorySeparatorChar

    if (-not $resolvedCandidatePath.StartsWith($repositoryPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Chemin hors dépôt interdit (spécification M-013): $resolvedCandidatePath"
    }

    return $resolvedCandidatePath
}

function Assert-M013Spec {
    param(
        [Parameter(Mandatory = $true)]
        [string] $SpecPath
    )

    if (-not (Test-Path -LiteralPath $SpecPath -PathType Leaf)) {
        throw "Spécification M-013 absente: $SpecPath"
    }

    $content = (Get-Content -Raw -Encoding UTF8 -LiteralPath $SpecPath).TrimStart([char] 0xFEFF)
    $lines = @(Get-Content -Encoding UTF8 -LiteralPath $SpecPath)
    if ($lines.Count -gt 0) {
        $lines[0] = $lines[0].TrimStart([char] 0xFEFF)
    }

    Assert-M013ForbiddenPatterns -Content $content

    foreach ($artifact in $requiredArtifacts) {
        Assert-M013Contains -Content $content -Expected $artifact -Message "Artefact M-013 attendu absent: $artifact"
    }

    Assert-M013Contains `
        -Content $content `
        -Expected "docs/governance/m012_v1_gap_report.md" `
        -Message "Rapport M-012 obligatoire absent: docs/governance/m012_v1_gap_report.md"

    Assert-M013Contains `
        -Content $content `
        -Expected "restore_test_result" `
        -Message "Preuve de restauration absente: restore_test_result"

    foreach ($marker in $requiredMarkers) {
        Assert-M013Contains -Content $content -Expected $marker -Message "Marqueur obligatoire absent: $marker"
    }

    foreach ($section in $requiredSections) {
        if ($lines -notcontains $section) {
            throw "Section obligatoire absente: $section"
        }
    }

    foreach ($adrId in $requiredAdrIds) {
        Assert-M013AdrToken -Content $content -AdrId $adrId
    }

    foreach ($command in $requiredCommands) {
        Assert-M013Contains -Content $content -Expected $command -Message "Commande de validation absente: $command"
    }

    $artifactRows = Read-M013MarkdownTable -Lines $lines -RequiredHeaders @("Objet", "Responsabilité", "Invariant") -TableName "objets M-013"
    Assert-M013NamedRows -Rows $artifactRows -NameColumn "Objet" -RequiredColumns @("Responsabilité", "Invariant") -ExpectedNames $requiredArtifacts -Label "Objet M-013" | Out-Null

    $policyRows = Read-M013MarkdownTable -Lines $lines -RequiredHeaders @("Politique", "Décision", "Invariants", "ADR") -TableName "politiques M-013"
    Assert-M013NamedRows -Rows $policyRows -NameColumn "Politique" -RequiredColumns @("Décision", "Invariants", "ADR") -ExpectedNames $expectedPolicies -Label "Politique M-013" | Out-Null

    $gapRows = Read-M013MarkdownTable -Lines $lines -RequiredHeaders @("Contexte", "Statut M-012", "Décision M-013", "Commande de preuve", "Blocage d'acceptation") -TableName "statuts d'écarts V1 M-013"
    Assert-M013GapStatuses -Rows $gapRows

    $behaviorRows = Read-M013MarkdownTable -Lines $lines -RequiredHeaders @("Comportement", "Invariant", "Scénario BDD", "Test RED", "ADR", "Commande") -TableName "comportements M-013"
    Assert-M013Behaviors -BehaviorRows $behaviorRows
}

$resolvedPath = Resolve-M013SpecificationPath -InputPath $Path
Assert-M013Spec -SpecPath $resolvedPath

Write-Host "Spécification M-013 valide: $($expectedBehaviors.Count) comportement(s), $($requiredArtifacts.Count) objet(s), $($expectedGapStatuses.Keys.Count) écart(s) V1 contrôlé(s)."
