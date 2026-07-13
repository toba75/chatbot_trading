param(
    [Parameter(Mandatory = $false)]
    [string] $MatrixPath,

    [Parameter(Mandatory = $false)]
    [string] $AuditPath,

    [Parameter(Mandatory = $false)]
    [string] $TestGatePath,

    [Parameter(Mandatory = $false)]
    [string] $LintGatePath,

    [Parameter(Mandatory = $false)]
    [string] $EnvironmentValidatorPath,

    [Parameter(Mandatory = $false)]
    [string] $RunbookPath,

    [Parameter(Mandatory = $false)]
    [string] $JournalPath
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$aCircumflex = [char] 0x00E2
$oCircumflex = [char] 0x00F4
$eAcute = [char] 0x00E9
$cCedilla = [char] 0x00E7
$traceabilityLabel = "Tra$($cCedilla)abilit$($eAcute)"
$m013NotClosedMarker = "M-013 entier non cl$($oCircumflex)tur$($eAcute)"
$v1NotAcceptedMarker = "V1 non accept$($eAcute)e"
$realConfigMarker = "``config/application.yaml`` r$($eAcute)el requis"

$expectedRequirements = @(
    [ordered] @{
        Id = "REQ-M013-CONFIG-001"
        Source = "docs/tasks/milestone_013-config/0001_verifier_precondition_green.md"
        Test = "tests/governance/validate_task_system_acceptance.ps1"
        Command = "scripts/validate_task_system.ps1"
        Code = "docs/tasks/milestone_013-config/journal.md"
        Adr = "ADR-016"
    },
    [ordered] @{
        Id = "REQ-M013-CONFIG-002"
        Source = "docs/tasks/milestone_013-config/0002_publier_specification_configuration_applicative.md"
        Test = "tests/m013_config/validate_application_config_specification_acceptance.ps1"
        Command = "tests/m013_config/validate_application_config_specification_acceptance.ps1"
        Code = "docs/specs/m013_config_configuration_applicative.md; config/application.schema.json; config/application.example.yaml"
        Adr = "ADR-016"
    },
    [ordered] @{
        Id = "REQ-M013-CONFIG-003"
        Source = "docs/tasks/milestone_013-config/0003_charger_configuration_fichier_unique.md"
        Test = "tests/m013_config/validate_application_config_loader_acceptance.ps1"
        Command = "tests/m013_config/validate_application_config_loader_acceptance.ps1"
        Code = "app/platform/configuration/__init__.py; config/application.schema.json"
        Adr = "ADR-016"
    },
    [ordered] @{
        Id = "REQ-M013-CONFIG-004"
        Source = "docs/tasks/milestone_013-config/0004_migrer_gateway_llm_configuration.md"
        Test = "tests/m013_config/validate_llm_gateway_config_file_acceptance.ps1"
        Command = "tests/m013_config/validate_llm_gateway_config_file_acceptance.ps1"
        Code = "app/platform/local_runtime.py; app/platform/llm_gateway/__init__.py; app/platform/observability/__init__.py"
        Adr = "ADR-016"
    },
    [ordered] @{
        Id = "REQ-M013-CONFIG-005"
        Source = "docs/tasks/milestone_013-config/0005_migrer_compose_deploiement_configuration.md"
        Test = "tests/m013_config/validate_compose_config_file_acceptance.ps1; tests/m013_fastapi/validate_review3_deployment_acceptance.ps1"
        Command = "scripts/validate_local_compose.ps1"
        Code = "deploy/local-compose/application.compose.yaml; deploy/local-compose/compose.yaml; app/platform/local_compose.py; app/platform/security/network_boundary.py"
        Adr = "ADR-016; ADR-026"
    },
    [ordered] @{
        Id = "REQ-M013-CONFIG-006"
        Source = "docs/tasks/milestone_013-config/0006_bloquer_entrees_environnement_applicatives.md"
        Test = "tests/m013_config/validate_environment_input_rejection_acceptance.ps1"
        Command = "scripts/validate_m013_config_environment.ps1"
        Code = "scripts/validate_m013_config_environment.ps1; scripts/validate_m013_config_environment.py"
        Adr = "ADR-016"
    },
    [ordered] @{
        Id = "REQ-M013-CONFIG-007"
        Source = "docs/tasks/milestone_013-config/0007_publier_runbooks_migration_configuration.md"
        Test = "tests/m013_config/validate_config_runbooks_acceptance.ps1"
        Command = "tests/m013_config/validate_config_runbooks_acceptance.ps1"
        Code = "docs/runbooks/configuration_applicative.md; docs/runbooks/exploitation_locale.md; docs/runbooks/spark_reseau_incidents.md; docs/runbooks/certificats_spark.md; deploy/local-compose/README.md"
        Adr = "ADR-016"
    },
    [ordered] @{
        Id = "REQ-M013-CONFIG-008"
        Source = "docs/tasks/milestone_013-config/0008_relier_m13_config_tracabilite_gates.md"
        Test = "tests/m013_config/validate_m013_config_traceability_acceptance.ps1"
        Command = "scripts/validate_m013_config_traceability.ps1"
        Code = "scripts/validate_m013_config_traceability.ps1; docs/governance/m013_config_audit.md; docs/tasks/milestone_013-config/journal.md"
        Adr = "ADR-016"
    }
)

$expectedM013ConfigTestPaths = @(
    "tests/m013_config/validate_application_config_specification_acceptance.ps1",
    "tests/m013_config/validate_application_config_specification_unit.ps1",
    "tests/m013_config/validate_application_config_loader_acceptance.ps1",
    "tests/m013_config/validate_application_config_loader_unit.ps1",
    "tests/m013_config/validate_application_config_loader_dependencies_unit.ps1",
    "tests/m013_config/validate_llm_gateway_config_file_acceptance.ps1",
    "tests/m013_config/validate_llm_gateway_config_file_unit.ps1",
    "tests/m013_config/validate_compose_config_file_acceptance.ps1",
    "tests/m013_config/validate_compose_config_file_unit.ps1",
    "tests/m013_config/validate_environment_input_rejection_acceptance.ps1",
    "tests/m013_config/validate_environment_input_rejection_unit.ps1",
    "tests/m013_config/validate_config_runbooks_acceptance.ps1",
    "tests/m013_config/validate_config_runbooks_unit.ps1",
    "tests/m013_config/validate_m013_config_traceability_acceptance.ps1",
    "tests/m013_config/validate_m013_config_traceability_unit.ps1"
)

$expectedAuditMarkers = @(
    "ADR-016",
    "Configuration applicative par fichier unique",
    "config/application.yaml",
    "configuration_hash",
    "CONFIG_ENV_INPUT_REJECTED",
    "scripts/validate_m013_config_environment.ps1",
    "scripts/validate_m013_config_traceability.ps1",
    $m013NotClosedMarker,
    $v1NotAcceptedMarker,
    $realConfigMarker,
    "Spark live requis"
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

function Resolve-RequiredPath {
    param(
        [string] $Path,
        [Parameter(Mandatory = $true)]
    [string] $DefaultRelativePath,
    [Parameter(Mandatory = $true)]
    [string] $Label,
    [Parameter(Mandatory = $false)]
    [switch] $AllowMissing
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

    Assert-Condition `
        -Condition ($resolvedPath.StartsWith($repositoryPrefix, [System.StringComparison]::OrdinalIgnoreCase)) `
        -Message "Chemin hors dépôt interdit ($Label): $resolvedPath"

    if (-not $AllowMissing) {
        Assert-Condition `
            -Condition (Test-Path -LiteralPath $resolvedPath -PathType Leaf) `
            -Message "Fichier requis absent ($Label): $resolvedPath"
    }

    return $resolvedPath
}

function Split-MarkdownRow {
    param([string] $Line)
    return @($Line.Trim().Trim("|").Split("|") | ForEach-Object { $_.Trim() })
}

function Normalize-MatrixPathCell {
    param([string] $Value)

    return @($Value.Split(";") | ForEach-Object {
        $path = $_.Trim().Replace("\", "/")
        if ($path.StartsWith("./")) {
            $path = $path.Substring(2)
        }
        $path
    } | Where-Object { $_ -ne "" }) -join "; "
}

function Get-CommandScript {
    param([string] $Command)

    $pattern = "^powershell\s+-NoProfile\s+-ExecutionPolicy\s+Bypass\s+-File\s+(?<script>\.?[\\/][^\s;|&]+)(?:\s+-Path\s+\.?[\\/][^\s;|&]+)?\s*$"
    Assert-Condition -Condition ($Command -match $pattern) -Message "Commande M13-config invalide: $Command"
    $scriptPath = $Matches["script"].Replace("\", "/")
    if ($scriptPath.StartsWith("./")) {
        return $scriptPath.Substring(2)
    }
    return $scriptPath
}

function Test-ContainsToken {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $Token
    )

    $escapedToken = [regex]::Escape($Token)
    return [regex]::IsMatch($Content, "(?<![A-Z0-9-])$escapedToken(?![A-Z0-9-])")
}

function ConvertTo-M013ConfigRequirementMap {
    param([string] $MatrixContent)

    $requirementsById = @{}
    foreach ($line in ($MatrixContent -split "`r?`n")) {
        if (-not $line.StartsWith("| REQ-M013-CONFIG-")) {
            continue
        }

        $cells = Split-MarkdownRow -Line $line
        Assert-Condition -Condition ($cells.Count -eq 8) -Message "Ligne M13-config incomplète: $line"
        $requirementsById[$cells[0]] = [ordered] @{
            Source = Normalize-MatrixPathCell -Value $cells[1]
            Status = $cells[2]
            Test = Normalize-MatrixPathCell -Value $cells[3]
            Command = Get-CommandScript -Command $cells[4]
            Code = Normalize-MatrixPathCell -Value $cells[5]
            Adr = $cells[6]
            Justification = $cells[7]
        }
    }
    return $requirementsById
}

function Assert-M013ConfigRequirementRows {
    param([hashtable] $RequirementsById)

    foreach ($expected in $expectedRequirements) {
        $requirementId = $expected["Id"]
        Assert-Condition -Condition ($RequirementsById.ContainsKey($requirementId)) -Message "Exigence M13-config absente: $requirementId"

        $requirement = $RequirementsById[$requirementId]
        Assert-Condition -Condition ($requirement["Status"] -eq "Couvert") -Message "Exigence M13-config non couverte: $requirementId"

        foreach ($cellName in @("Source", "Test", "Command", "Code", "Adr")) {
            $expectedValue = $expected[$cellName]
            $actualValue = $requirement[$cellName]
            Assert-Condition `
                -Condition ($actualValue -eq $expectedValue) `
                -Message "$cellName M13-config invalide pour ${requirementId}. Attendu: $expectedValue. Obtenu: $actualValue"
        }

        Assert-Condition `
            -Condition ($requirement["Justification"].Contains("structurante document")) `
            -Message "Justification ADR M13-config invalide pour ${requirementId}: $($requirement["Justification"])"
    }
}

function Assert-GateEnrollment {
    param(
        [Parameter(Mandatory = $true)]
        [string] $TestGateContent,

        [Parameter(Mandatory = $true)]
        [string] $LintGateContent
    )

    foreach ($validationPath in @("scripts/validate_m013_config_environment.ps1", "scripts/validate_m013_config_traceability.ps1")) {
        Assert-Condition `
            -Condition ($TestGateContent.Contains($validationPath)) `
            -Message "Gate test sans validation M13-config: $validationPath"
        Assert-Condition `
            -Condition ($LintGateContent.Contains($validationPath)) `
            -Message "Gate lint sans validation M13-config: $validationPath"
    }

    foreach ($testPath in $expectedM013ConfigTestPaths) {
        Assert-Condition `
            -Condition ($TestGateContent.Contains($testPath)) `
            -Message "Gate test sans test M13-config: $testPath"
    }

    Assert-Condition `
        -Condition ($LintGateContent.Contains("-ExpectedValidationCount 38")) `
        -Message "Compteur lint M13-config invalide: 38 validations attendues"
}

function Assert-AuditReport {
    param(
        [Parameter(Mandatory = $true)]
        [string] $AuditContent,

        [Parameter(Mandatory = $true)]
        [string] $JournalContent,

        [Parameter(Mandatory = $true)]
        [string] $RunbookContent
    )

    foreach ($expected in $expectedRequirements) {
        $requirementId = $expected["Id"]
        Assert-Condition `
            -Condition (Test-ContainsToken -Content $AuditContent -Token $requirementId) `
            -Message "Audit M13-config sans preuve: $requirementId"
    }

    foreach ($marker in $expectedAuditMarkers) {
        Assert-Condition `
            -Condition ($AuditContent.Contains($marker)) `
            -Message "Marqueur d'audit M13-config absent: $marker"
    }

    foreach ($taskId in @("T-001", "T-002", "T-003", "T-004", "T-005", "T-006", "T-007", "T-008")) {
        Assert-Condition -Condition ($AuditContent.Contains($taskId)) -Message "Audit M13-config sans tâche: $taskId"
        Assert-Condition -Condition ($JournalContent.Contains($taskId)) -Message "Journal M13-config sans tâche: $taskId"
    }

    foreach ($marker in @("config/application.yaml", "--config", "CONFIG_ENV_INPUT_REJECTED", "configuration_hash")) {
        Assert-Condition -Condition ($RunbookContent.Contains($marker)) -Message "Runbook M13-config incomplet: $marker"
    }

    Assert-Condition `
        -Condition (-not $AuditContent.Contains("M-013 globalement clôturé")) `
        -Message "Audit M13-config ne doit pas déclarer M-013 globalement clôturé"
    Assert-Condition `
        -Condition (-not $AuditContent.Contains("M-013 entier clôturé")) `
        -Message "Audit M13-config ne doit pas déclarer M-013 globalement clôturé"
    Assert-Condition `
        -Condition (-not $AuditContent.Contains("V1 acceptée")) `
        -Message "Audit M13-config ne doit pas déclarer la V1 acceptée"
}

$resolvedMatrixPath = Resolve-RequiredPath -Path $MatrixPath -DefaultRelativePath "docs/traceability/matrix.md" -Label "matrix"
$resolvedAuditPath = Resolve-RequiredPath -Path $AuditPath -DefaultRelativePath "docs/governance/m013_config_audit.md" -Label "audit"
$resolvedTestGatePath = Resolve-RequiredPath -Path $TestGatePath -DefaultRelativePath "scripts/test.ps1" -Label "test gate"
$resolvedLintGatePath = Resolve-RequiredPath -Path $LintGatePath -DefaultRelativePath "scripts/lint.ps1" -Label "lint gate"
$resolvedEnvironmentValidatorPath = Resolve-RequiredPath -Path $EnvironmentValidatorPath -DefaultRelativePath "scripts/validate_m013_config_environment.ps1" -Label "environment validator" -AllowMissing
$resolvedRunbookPath = Resolve-RequiredPath -Path $RunbookPath -DefaultRelativePath "docs/runbooks/configuration_applicative.md" -Label "runbook"
$resolvedJournalPath = Resolve-RequiredPath -Path $JournalPath -DefaultRelativePath "docs/tasks/milestone_013-config/journal.md" -Label "journal"

Assert-Condition `
    -Condition (Test-Path -LiteralPath $resolvedEnvironmentValidatorPath -PathType Leaf) `
    -Message "Gate environnement M13-config absente"

$matrixContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedMatrixPath
$auditContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedAuditPath
$testGateContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedTestGatePath
$lintGateContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedLintGatePath
$runbookContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedRunbookPath
$journalContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedJournalPath

Assert-M013ConfigRequirementRows -RequirementsById (ConvertTo-M013ConfigRequirementMap -MatrixContent $matrixContent)
Assert-GateEnrollment -TestGateContent $testGateContent -LintGateContent $lintGateContent
Assert-AuditReport -AuditContent $auditContent -JournalContent $journalContent -RunbookContent $runbookContent

Write-Host "$traceabilityLabel M13-config valide: $($expectedRequirements.Count) exigence(s), 8 t$($aCircumflex)che(s), $v1NotAcceptedMarker."
