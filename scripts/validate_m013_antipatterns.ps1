param(
    [Parameter(Mandatory = $false)]
    [string] $ReviewPath,

    [Parameter(Mandatory = $false)]
    [string] $SpecificationPath,

    [Parameter(Mandatory = $false)]
    [string] $MatrixPath,

    [Parameter(Mandatory = $false)]
    [string] $TestGatePath,

    [Parameter(Mandatory = $false)]
    [string] $LintGatePath
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

$defaultReviewPath = "docs/governance/m013_antipattern_review.md"
$defaultSpecificationPath = "docs/specs/m013_durcissement_acceptation_v1.md"
$defaultMatrixPath = "docs/traceability/matrix.md"
$defaultTestGatePath = "scripts/test.ps1"
$defaultLintGatePath = "scripts/lint.ps1"

$requiredLinkedControls = @(
    "scripts/validate_architecture_boundaries.ps1",
    "scripts/validate_network_boundary.ps1",
    "scripts/validate_traceability.ps1",
    "scripts/validate_adr_system.ps1",
    "scripts/validate_m013_security.ps1",
    "scripts/validate_m013_backup_restore.ps1",
    "scripts/validate_m013_retention.ps1",
    "scripts/validate_m013_monitoring.ps1",
    "scripts/validate_m013_runbooks.ps1"
)

$requiredProofs = @(
    "docs/governance/m013_security_audit.md",
    "docs/governance/m013_spark_failure_drill.md",
    "docs/governance/m013_backup_restore_drill.md",
    "docs/governance/m013_retention_policy.md",
    "docs/governance/m013_local_monitoring.md",
    "docs/governance/m013_resource_profile.md",
    "docs/governance/m013_documentation_index.md",
    "docs/runbooks/conversation_v1.md",
    "docs/evaluation/m012/llm_real_path_benchmark_report.md",
    "docs/evaluation/m012/strategy_backtest_benchmark_report.md",
    "docs/adr/index.md",
    "docs/traceability/matrix.md"
)

$requiredControls = @(
    "CTRL-M013-DOMAIN-001",
    "CTRL-M013-DOMAIN-002",
    "CTRL-M013-DOMAIN-003",
    "CTRL-M013-DOMAIN-004",
    "CTRL-M013-ARCH-001",
    "CTRL-M013-NET-001",
    "CTRL-M013-NET-002",
    "CTRL-M013-NET-003",
    "CTRL-M013-LLM-001",
    "CTRL-M013-LLM-002",
    "CTRL-M013-BACKUP-001",
    "CTRL-M013-RETENTION-001",
    "CTRL-M013-MONITORING-001",
    "CTRL-M013-MONITORING-002"
)

$requiredAntiPatterns = @(
    @{ Label = "Conversation utilisée comme source factuelle"; ErrorLabel = "conversation utilisée comme source factuelle" },
    @{ Label = "Score de similarité traité comme preuve"; ErrorLabel = "score de similarité traité comme preuve" },
    @{ Label = "Affirmation vérifiée sans span direct"; ErrorLabel = "affirmation vérifiée sans span direct" },
    @{ Label = "Règle de stratégie sans origine"; ErrorLabel = "règle de stratégie sans origine" },
    @{ Label = "Paramètre inventé silencieusement"; ErrorLabel = "paramètre inventé silencieusement" },
    @{ Label = "Résultat négatif supprimé"; ErrorLabel = "résultat négatif supprimé" },
    @{ Label = "Version publiée modifiée en place"; ErrorLabel = "version publiée modifiée en place" },
    @{ Label = "Accès direct d'un contexte métier au protocole vLLM"; ErrorLabel = "accès direct d'un contexte métier au protocole vLLM" },
    @{ Label = "Bounded contexts ou bases déployés sur le Spark"; ErrorLabel = "bounded contexts ou bases déployés sur le Spark" },
    @{ Label = "Navigateur ou interface appelant directement le Spark"; ErrorLabel = "navigateur ou interface appelant directement le Spark" },
    @{ Label = "Service Gemma caché dans le Compose local comme fallback non déclaré"; ErrorLabel = "fallback LLM silencieux" },
    @{ Label = "Retry illimité d'une génération distante"; ErrorLabel = "retry illimité d'une génération distante" },
    @{ Label = "Prompt complet persistant"; ErrorLabel = "prompt complet persistant" },
    @{ Label = "Qdrant source de vérité"; ErrorLabel = "Qdrant source de vérité" },
    @{ Label = "Checkpoint quantifié sans benchmark"; ErrorLabel = "checkpoint quantifié sans benchmark" },
    @{ Label = "Contexte 256K par défaut"; ErrorLabel = "contexte 256K par défaut" },
    @{ Label = "Microservice par contexte imposé"; ErrorLabel = "microservice par contexte imposé" }
)

$requiredOpenQuestions = @(
    "Frontière exacte de KA",
    "Langage d'expression des règles",
    "Granularité maximale d'un claim",
    "Politique de vérification",
    "Revue humaine",
    "Moteur de backtest",
    "Conservation",
    "Données de marché",
    "Versioning des réponses",
    "Graphe de claims",
    "Hôte Docker local",
    "Sécurité inter-hôtes",
    "Résolution réseau",
    "Disponibilité du Spark"
)

function Assert-M013Condition {
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

function Assert-M013Contains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    Assert-M013Condition -Condition ($Content.Contains($Expected)) -Message $Message
}

function Resolve-M013RequiredPath {
    param(
        [Parameter(Mandatory = $false)]
        [AllowEmptyString()]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $DefaultRelativePath,

        [Parameter(Mandatory = $true)]
        [string] $Label
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        $candidatePath = Join-Path $repoRoot $DefaultRelativePath
    }
    elseif ([System.IO.Path]::IsPathRooted($Path)) {
        $candidatePath = $Path
    }
    else {
        $candidatePath = Join-Path $repoRoot $Path
    }

    $resolvedRepositoryRoot = [System.IO.Path]::GetFullPath($repoRoot)
    $resolvedPath = [System.IO.Path]::GetFullPath($candidatePath)
    $repositoryPrefix = $resolvedRepositoryRoot.TrimEnd("\", "/") + [System.IO.Path]::DirectorySeparatorChar

    Assert-M013Condition `
        -Condition ($resolvedPath.StartsWith($repositoryPrefix, [System.StringComparison]::OrdinalIgnoreCase)) `
        -Message "Chemin hors dépôt interdit ($Label): $resolvedPath"
    Assert-M013Condition `
        -Condition (Test-Path -LiteralPath $resolvedPath -PathType Leaf) `
        -Message "Fichier requis absent ($Label): $resolvedPath"

    return $resolvedPath
}

function Get-M013DocumentContent {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    return (Get-Content -Raw -Encoding UTF8 -LiteralPath $Path).TrimStart([char] 0xFEFF)
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

    return $rows.ToArray()
}

function Assert-M013OpenQuestions {
    param(
        [AllowEmptyString()]
        [string[]] $Lines
    )

    $rows = Read-M013MarkdownTable `
        -Lines $Lines `
        -RequiredHeaders @("Sujet", "Statut", "Décision", "ADR", "Preuve") `
        -TableName "questions ouvertes contrôlées"

    $rowsBySubject = @{}
    foreach ($row in $rows) {
        $subject = $row["Sujet"]
        $rowsBySubject[$subject] = $row
        if ($row["Statut"] -match "résolue|tranchée|décidée") {
            if ($row["ADR"] -notmatch "(ADR|DDD-ADR)-[0-9]{3}") {
                throw "Question ouverte résolue sans ADR: $subject"
            }
        }
    }

    foreach ($question in $requiredOpenQuestions) {
        Assert-M013Condition -Condition $rowsBySubject.ContainsKey($question) -Message "Question ouverte absente: $question"
    }

    return $rows.Count
}

function Assert-M013NoActiveViolation {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    $matches = [regex]::Matches($Content, "(?im)^Violation active:\s*(?<violation>.+)$")
    foreach ($match in $matches) {
        $violation = $match.Groups["violation"].Value.Trim()
        if ($violation.Length -gt 0) {
            throw "Violation active interdite: $violation"
        }
    }

    Assert-M013Contains -Content $Content -Expected "Verdict T-011: aucune violation active" -Message "Verdict sans preuve d'absence de violation active."
}

$resolvedReviewPath = Resolve-M013RequiredPath -Path $ReviewPath -DefaultRelativePath $defaultReviewPath -Label "revue anti-patterns"
$resolvedSpecificationPath = Resolve-M013RequiredPath -Path $SpecificationPath -DefaultRelativePath $defaultSpecificationPath -Label "spécification M-013"
$resolvedMatrixPath = Resolve-M013RequiredPath -Path $MatrixPath -DefaultRelativePath $defaultMatrixPath -Label "matrice"
$resolvedTestGatePath = Resolve-M013RequiredPath -Path $TestGatePath -DefaultRelativePath $defaultTestGatePath -Label "gate test"
$resolvedLintGatePath = Resolve-M013RequiredPath -Path $LintGatePath -DefaultRelativePath $defaultLintGatePath -Label "gate lint"

$reviewContent = Get-M013DocumentContent -Path $resolvedReviewPath
$reviewLines = @(Get-Content -Encoding UTF8 -LiteralPath $resolvedReviewPath)
if ($reviewLines.Count -gt 0) {
    $reviewLines[0] = $reviewLines[0].TrimStart([char] 0xFEFF)
}
$specificationContent = Get-M013DocumentContent -Path $resolvedSpecificationPath
$matrixContent = Get-M013DocumentContent -Path $resolvedMatrixPath
$testGateContent = Get-M013DocumentContent -Path $resolvedTestGatePath
$lintGateContent = Get-M013DocumentContent -Path $resolvedLintGatePath

foreach ($marker in @(
    "# Revue anti-patterns interdits V1 M-013",
    "M013-ForbiddenAntiPatternReview-1.0",
    "ForbiddenAntiPatternPolicy",
    "Given la spécification V1 liste les anti-patterns interdits",
    "When la validation M-013 des anti-patterns s'exécute",
    "Then chaque interdiction possède un contrôle automatisé ou une revue documentée"
)) {
    Assert-M013Contains -Content $reviewContent -Expected $marker -Message "Marqueur de revue anti-patterns absent: $marker"
}

Assert-M013Condition -Condition ([regex]::IsMatch($reviewContent, "Date de revue:\s*2026-07-08")) -Message "Date de revue obligatoire"
Assert-M013Condition -Condition ([regex]::IsMatch($reviewContent, "Périmètre revu:\s*section 23")) -Message "Périmètre de revue obligatoire"
Assert-M013NoActiveViolation -Content $reviewContent

foreach ($linkedControl in $requiredLinkedControls) {
    Assert-M013Contains -Content $reviewContent -Expected $linkedControl -Message "Contrôle transverse relié absent: $linkedControl"
}

foreach ($proof in $requiredProofs) {
    Assert-M013Contains -Content $reviewContent -Expected $proof -Message "Preuve de revue obligatoire absente: $proof"
}

foreach ($control in $requiredControls) {
    Assert-M013Contains -Content $reviewContent -Expected $control -Message "Contrôle obligatoire absent: $control"
}

foreach ($antiPattern in $requiredAntiPatterns) {
    Assert-M013Contains `
        -Content $reviewContent `
        -Expected $antiPattern.Label `
        -Message "Anti-pattern obligatoire absent: $($antiPattern.ErrorLabel)"
}

$openQuestionCount = Assert-M013OpenQuestions -Lines $reviewLines

foreach ($marker in @(
    "T-011",
    "V1-010 - Anti-patterns interdits V1",
    "tests/m013/validate_v1_antipatterns_acceptance.ps1",
    "scripts/validate_m013_antipatterns.ps1",
    "docs/governance/m013_antipattern_review.md"
)) {
    Assert-M013Contains -Content $specificationContent -Expected $marker -Message "Spécification M-013 sans marqueur T-011: $marker"
}

foreach ($marker in @(
    "REQ-M013-011",
    "docs/tasks/milestone_013/0011_verifier_antipatterns_v1.md",
    "tests/m013/validate_v1_antipatterns_acceptance.ps1",
    "tests/m013/validate_v1_antipatterns_unit.ps1",
    "scripts/validate_m013_antipatterns.ps1",
    "docs/governance/m013_antipattern_review.md",
    "ADR-007",
    "ADR-008",
    "ADR-009",
    "DDD-ADR-006",
    "DDD-ADR-010"
)) {
    Assert-M013Contains -Content $matrixContent -Expected $marker -Message "Traçabilité T-011 absente: $marker"
}

foreach ($marker in @(
    "scripts/validate_m013_antipatterns.ps1",
    "tests/m013/validate_v1_antipatterns_acceptance.ps1",
    "tests/m013/validate_v1_antipatterns_unit.ps1"
)) {
    Assert-M013Contains -Content $testGateContent -Expected $marker -Message "Gate test sans anti-patterns M-013: $marker"
}

Assert-M013Contains `
    -Content $lintGateContent `
    -Expected "scripts/validate_m013_antipatterns.ps1" `
    -Message "Gate lint sans validateur anti-patterns M-013."

Write-Host "Anti-patterns V1 M-013 valides: $($requiredAntiPatterns.Count) anti-pattern(s), $openQuestionCount question(s) ouverte(s) contrôlée(s), $($requiredLinkedControls.Count) contrôle(s) relié(s), aucune violation active."

