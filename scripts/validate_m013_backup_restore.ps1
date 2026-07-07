param(
    [Parameter(Mandatory = $false)]
    [string] $DrillPath,

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

$defaultDrillPath = "docs/governance/m013_backup_restore_drill.md"
$defaultMatrixPath = "docs/traceability/matrix.md"
$defaultTestGatePath = "scripts/test.ps1"
$defaultLintGatePath = "scripts/lint.ps1"

$requiredContexts = @("SP", "KA", "EG", "RA", "CV", "SD", "EX", "EV", "platform")
$requiredDrillMarkers = @(
    "# Exercice sauvegardes chiffrées et restauration M-013",
    "M013-BackupRestoreDrill-1.0",
    "M013-BackupManifest-1.0",
    "BackupRestorePolicy",
    "Given une instance V1 contient corpus",
    "When une sauvegarde chiffrée est restaurée",
    "Then les identifiants stables",
    "restore_test_result",
    "clé hors dépôt",
    "aucun secret en Git",
    "aucune donnée métier sur Spark",
    "projections régénérables non autorité",
    "résultats négatifs et supersédés conservés",
    "hash sauvegardé",
    "hash restauré",
    "cible locale isolée",
    "restauration destructive interdite",
    "ADR-009",
    "ADR-013",
    "DDD-ADR-004",
    "DDD-ADR-010",
    "CTRL-M013-BACKUP-001",
    "CTRL-M013-BACKUP-002",
    "CTRL-M013-BACKUP-003",
    "CTRL-M013-BACKUP-004",
    "CTRL-M013-BACKUP-005",
    "CTRL-M013-BACKUP-006",
    "CTRL-M013-BACKUP-007",
    "CTRL-M013-BACKUP-008",
    "CTRL-M013-BACKUP-009",
    "CTRL-M013-BACKUP-010",
    "CTRL-M013-BACKUP-011"
)

$forbiddenDrillPatterns = @(
    "BEGIN PRIVATE KEY",
    "END PRIVATE KEY",
    "POSTGRES_PASSWORD\s*=",
    "QDRANT_API_KEY\s*=",
    "GEMMA_API_KEY\s*=",
    "VLLM_API_KEY\s*=",
    "Authorization:\s*Bearer",
    "SECRET_INTERDIT_M013"
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

function Invoke-M013BackupRestoreDomainCheck {
    . (Join-Path $repoRoot "scripts/require_python.ps1")
    $pythonExecutable = Get-RequiredPythonExecutable
    $pythonCode = @'
import sys

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.platform.backup_restore import (
    BACKUP_RESTORE_DRILL_POLICY_VERSION,
    BackupRestoreDrillPolicy,
    build_m013_backup_restore_drill,
)

drill = build_m013_backup_restore_drill()
BackupRestoreDrillPolicy(policy_version=BACKUP_RESTORE_DRILL_POLICY_VERSION).validate_drill(drill)
print(f"{len(drill.manifest.entries)} entrées restaurables validées")
'@
    $pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_backup_restore_validator_" + [System.Guid]::NewGuid().ToString("N") + ".py")
    Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $env:PYTHONIOENCODING = "utf-8"
        $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
        Remove-Item -LiteralPath $pythonScriptPath -Force
    }

    if ($exitCode -ne 0) {
        throw "Politique sauvegarde restauration M-013 invalide: $($output -join "`n")"
    }
}

function Assert-M013BackupRestoreDrillReport {
    param(
        [Parameter(Mandatory = $true)]
        [string] $DrillContent
    )

    foreach ($pattern in $forbiddenDrillPatterns) {
        if ([regex]::IsMatch($DrillContent, $pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)) {
            throw "Secret complet interdit dans le drill sauvegarde restauration M-013: $pattern"
        }
    }

    foreach ($context in $requiredContexts) {
        $expectedContextMarker = "| ``$context`` |"
        Assert-M013Contains -Content $DrillContent -Expected $expectedContextMarker -Message "Contexte V1 absent du drill sauvegarde restauration: $context"
    }

    foreach ($marker in $requiredDrillMarkers) {
        Assert-M013Contains -Content $DrillContent -Expected $marker -Message "Marqueur drill sauvegarde restauration absent: $marker"
    }
}

function Assert-M013Traceability {
    param(
        [Parameter(Mandatory = $true)]
        [string] $MatrixContent,

        [Parameter(Mandatory = $true)]
        [string] $TestGateContent,

        [Parameter(Mandatory = $true)]
        [string] $LintGateContent
    )

    foreach ($marker in @(
        "REQ-M013-007",
        "docs/tasks/milestone_013/0007_valider_sauvegardes_chiffrees_restauration.md",
        "tests/m013/validate_backup_restore_acceptance.ps1",
        "tests/m013/validate_backup_restore_unit.ps1",
        "scripts/validate_m013_backup_restore.ps1",
        "docs/governance/m013_backup_restore_drill.md",
        "app/platform/backup_restore.py",
        "ADR-009",
        "ADR-013",
        "DDD-ADR-004",
        "DDD-ADR-010"
    )) {
        Assert-M013Contains -Content $MatrixContent -Expected $marker -Message "Traçabilité T-007 absente: $marker"
    }

    foreach ($marker in @(
        "scripts/validate_m013_backup_restore.ps1",
        "tests/m013/validate_backup_restore_acceptance.ps1",
        "tests/m013/validate_backup_restore_unit.ps1"
    )) {
        Assert-M013Contains -Content $TestGateContent -Expected $marker -Message "Gate test sans sauvegarde restauration M-013: $marker"
    }

    Assert-M013Contains `
        -Content $LintGateContent `
        -Expected "scripts/validate_m013_backup_restore.ps1" `
        -Message "Gate lint sans validateur sauvegarde restauration M-013."
}

$resolvedDrillPath = Resolve-M013RequiredPath -Path $DrillPath -DefaultRelativePath $defaultDrillPath -Label "drill sauvegarde restauration"
$resolvedMatrixPath = Resolve-M013RequiredPath -Path $MatrixPath -DefaultRelativePath $defaultMatrixPath -Label "matrice"
$resolvedTestGatePath = Resolve-M013RequiredPath -Path $TestGatePath -DefaultRelativePath $defaultTestGatePath -Label "gate test"
$resolvedLintGatePath = Resolve-M013RequiredPath -Path $LintGatePath -DefaultRelativePath $defaultLintGatePath -Label "gate lint"

Invoke-M013BackupRestoreDomainCheck

$drillContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedDrillPath).TrimStart([char] 0xFEFF)
$matrixContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedMatrixPath).TrimStart([char] 0xFEFF)
$testGateContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedTestGatePath).TrimStart([char] 0xFEFF)
$lintGateContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedLintGatePath).TrimStart([char] 0xFEFF)

Assert-M013BackupRestoreDrillReport -DrillContent $drillContent
Assert-M013Traceability -MatrixContent $matrixContent -TestGateContent $testGateContent -LintGateContent $lintGateContent

Write-Host "Sauvegarde restauration M-013 valide: restore_test_result, aucun secret en Git, aucune donnée métier sur Spark, projections régénérables non autorité, résultats négatifs et supersédés conservés."
