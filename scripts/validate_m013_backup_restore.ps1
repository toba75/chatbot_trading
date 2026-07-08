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

function New-M013BackupManifestFixtureJson {
    $entries = @(
        [ordered] @{ entry_id = "BACKUP-SP-CORPUS-001"; context = "SP"; artifact_kind = "corpus_original"; stable_identifier = "SRC-M013-BACKUP-001"; storage_host = "docker-local"; authority = $true; immutable = $true; regenerable_projection = $false; retained_negative_or_superseded = $false; backup_sha256 = "41afbc972e3965ef7af89ccc1cb76033d684c363224e408b001d4ad6fe53d762"; restored_sha256 = "41afbc972e3965ef7af89ccc1cb76033d684c363224e408b001d4ad6fe53d762"; contains_plain_secret = $false; git_tracked_key_material = $false; spark_business_storage = $false; destructive_restore = $false }
        [ordered] @{ entry_id = "BACKUP-SP-CANONICAL-001"; context = "SP"; artifact_kind = "canonical_versions"; stable_identifier = "CANON-M013-BACKUP-001"; storage_host = "docker-local"; authority = $true; immutable = $true; regenerable_projection = $false; retained_negative_or_superseded = $false; backup_sha256 = "07aa716c5e229e8502dcbefdc41c1dad332376a9204286b50ce59ba8573121ab"; restored_sha256 = "07aa716c5e229e8502dcbefdc41c1dad332376a9204286b50ce59ba8573121ab"; contains_plain_secret = $false; git_tracked_key_material = $false; spark_business_storage = $false; destructive_restore = $false }
        [ordered] @{ entry_id = "BACKUP-KA-QDRANT-001"; context = "KA"; artifact_kind = "qdrant_projection"; stable_identifier = "PROJ-M013-BACKUP-001"; storage_host = "docker-local"; authority = $false; immutable = $false; regenerable_projection = $true; retained_negative_or_superseded = $false; backup_sha256 = "24c11cc03fa691edfee932d7d7fe8e2322b59df3f5e2f78f43de2d22ece1586a"; restored_sha256 = "24c11cc03fa691edfee932d7d7fe8e2322b59df3f5e2f78f43de2d22ece1586a"; contains_plain_secret = $false; git_tracked_key_material = $false; spark_business_storage = $false; destructive_restore = $false }
        [ordered] @{ entry_id = "BACKUP-EG-CLAIMS-001"; context = "EG"; artifact_kind = "claim_registry"; stable_identifier = "CLAIM-M013-BACKUP-001"; storage_host = "docker-local"; authority = $true; immutable = $true; regenerable_projection = $false; retained_negative_or_superseded = $true; backup_sha256 = "5e6f1f718dd111612c9a39f99e6106962cb672581760346ee7f438f0daacee0a"; restored_sha256 = "5e6f1f718dd111612c9a39f99e6106962cb672581760346ee7f438f0daacee0a"; contains_plain_secret = $false; git_tracked_key_material = $false; spark_business_storage = $false; destructive_restore = $false }
        [ordered] @{ entry_id = "BACKUP-RA-ANSWERS-001"; context = "RA"; artifact_kind = "verified_answers"; stable_identifier = "ANSWER-M013-BACKUP-001"; storage_host = "docker-local"; authority = $true; immutable = $true; regenerable_projection = $false; retained_negative_or_superseded = $true; backup_sha256 = "6ac74cb4c5842dc58c4a36595f8505dd11cc601ee7435d0c12b5ca300c9a9d12"; restored_sha256 = "6ac74cb4c5842dc58c4a36595f8505dd11cc601ee7435d0c12b5ca300c9a9d12"; contains_plain_secret = $false; git_tracked_key_material = $false; spark_business_storage = $false; destructive_restore = $false }
        [ordered] @{ entry_id = "BACKUP-CV-TURNS-001"; context = "CV"; artifact_kind = "conversation_turns"; stable_identifier = "CONV-M013-BACKUP-001"; storage_host = "docker-local"; authority = $true; immutable = $true; regenerable_projection = $false; retained_negative_or_superseded = $false; backup_sha256 = "ad2171f2d64fb2e0b97dead7a371940a39cee49ffd82ab431875700dfdbeab5a"; restored_sha256 = "ad2171f2d64fb2e0b97dead7a371940a39cee49ffd82ab431875700dfdbeab5a"; contains_plain_secret = $false; git_tracked_key_material = $false; spark_business_storage = $false; destructive_restore = $false }
        [ordered] @{ entry_id = "BACKUP-SD-STRATEGY-001"; context = "SD"; artifact_kind = "strategy_snapshots"; stable_identifier = "STRAT-M013-BACKUP-001"; storage_host = "docker-local"; authority = $true; immutable = $true; regenerable_projection = $false; retained_negative_or_superseded = $true; backup_sha256 = "2522c33fb81d48560c3350a3b2ff244fa22639c64aa071afc0a340225bced7ca"; restored_sha256 = "2522c33fb81d48560c3350a3b2ff244fa22639c64aa071afc0a340225bced7ca"; contains_plain_secret = $false; git_tracked_key_material = $false; spark_business_storage = $false; destructive_restore = $false }
        [ordered] @{ entry_id = "BACKUP-EX-RESULTS-001"; context = "EX"; artifact_kind = "experiment_results"; stable_identifier = "EXP-M013-BACKUP-001"; storage_host = "docker-local"; authority = $true; immutable = $true; regenerable_projection = $false; retained_negative_or_superseded = $true; backup_sha256 = "cb56bed550ec21f510dba2aacc349910069dcf4b9d3055528fbad6f73e912c3c"; restored_sha256 = "cb56bed550ec21f510dba2aacc349910069dcf4b9d3055528fbad6f73e912c3c"; contains_plain_secret = $false; git_tracked_key_material = $false; spark_business_storage = $false; destructive_restore = $false }
        [ordered] @{ entry_id = "BACKUP-EV-REPORTS-001"; context = "EV"; artifact_kind = "evaluation_reports"; stable_identifier = "EVAL-M013-BACKUP-001"; storage_host = "docker-local"; authority = $true; immutable = $true; regenerable_projection = $false; retained_negative_or_superseded = $true; backup_sha256 = "cd5fa46828c77876760ff84260c850b7769e191a18008a97cbd8381a90501717"; restored_sha256 = "cd5fa46828c77876760ff84260c850b7769e191a18008a97cbd8381a90501717"; contains_plain_secret = $false; git_tracked_key_material = $false; spark_business_storage = $false; destructive_restore = $false }
        [ordered] @{ entry_id = "BACKUP-PLATFORM-GOV-001"; context = "platform"; artifact_kind = "governance_artifacts"; stable_identifier = "GOV-M013-BACKUP-001"; storage_host = "docker-local"; authority = $true; immutable = $true; regenerable_projection = $false; retained_negative_or_superseded = $false; backup_sha256 = "217a94c41d0a66989fde831fd643d76daf7cae412593f3d634fb02ba6aecc32d"; restored_sha256 = "217a94c41d0a66989fde831fd643d76daf7cae412593f3d634fb02ba6aecc32d"; contains_plain_secret = $false; git_tracked_key_material = $false; spark_business_storage = $false; destructive_restore = $false }
    )
    return ([pscustomobject] ([ordered] @{
        manifest_id = "M013-BACKUP-MANIFEST-0001"
        contract_version = "M013-BackupManifest-1.0"
        backup_command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\backup_v1.ps1 -Manifest .\restore\manifest.json"
        restore_command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\restore_v1.ps1 -Manifest .\restore\manifest.json -Target C:\restore\m013-isolated"
        restore_target = "local_isolated"
        archive_encrypted = $true
        encryption_proof = "ciphertext_sha256=305531dcc50ebca31cf1d5b31e9fc76ed51f66b3b6dd5a030c6539ae6532f979"
        key_reference = "hors_depot://cle-restauration/m013"
        key_git_tracked = $false
        complete = $true
        entries = $entries
    }) | ConvertTo-Json -Depth 8)
}

function Assert-M013BackupRestoreScripts {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ScriptDirectory
    )

    $backupScriptPath = Join-Path $ScriptDirectory "backup_v1.ps1"
    $restoreScriptPath = Join-Path $ScriptDirectory "restore_v1.ps1"
    $manifestHelperPath = Join-Path $ScriptDirectory "lib/m013_backup_manifest.ps1"

    Assert-M013Condition -Condition (Test-Path -LiteralPath $backupScriptPath -PathType Leaf) -Message "Script sauvegarde V1 absent: scripts/backup_v1.ps1"
    Assert-M013Condition -Condition (Test-Path -LiteralPath $restoreScriptPath -PathType Leaf) -Message "Script restauration V1 absent: scripts/restore_v1.ps1"
    Assert-M013Condition -Condition (Test-Path -LiteralPath $manifestHelperPath -PathType Leaf) -Message "Helper manifeste sauvegarde V1 absent: scripts/lib/m013_backup_manifest.ps1"

    $temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_backup_restore_scripts_" + [System.Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $temporaryRoot | Out-Null
    try {
        $manifestPath = Join-Path $temporaryRoot "manifest.json"
        $restoreTarget = Join-Path $temporaryRoot "restore-target"
        Set-Content -Encoding UTF8 -LiteralPath $manifestPath -Value (New-M013BackupManifestFixtureJson)

        $previousErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            $backupOutput = & powershell -NoProfile -ExecutionPolicy Bypass -File $backupScriptPath -Manifest $manifestPath 2>&1
            $backupExitCode = $LASTEXITCODE
            $restoreOutput = & powershell -NoProfile -ExecutionPolicy Bypass -File $restoreScriptPath -Manifest $manifestPath -Target $restoreTarget 2>&1
            $restoreExitCode = $LASTEXITCODE

            $invalidManifestPath = Join-Path $temporaryRoot "manifest-invalide.json"
            Set-Content -Encoding UTF8 -LiteralPath $invalidManifestPath -Value '{ "contract_version": "M013-BackupManifest-1.0", "restore_test_result": "GREEN" }'
            $invalidBackupOutput = & powershell -NoProfile -ExecutionPolicy Bypass -File $backupScriptPath -Manifest $invalidManifestPath 2>&1
            $invalidBackupExitCode = $LASTEXITCODE
            $invalidRestoreOutput = & powershell -NoProfile -ExecutionPolicy Bypass -File $restoreScriptPath -Manifest $invalidManifestPath -Target (Join-Path $temporaryRoot "restore-invalid") 2>&1
            $invalidRestoreExitCode = $LASTEXITCODE

            $placeholderManifestPath = Join-Path $temporaryRoot "manifest-placeholder.json"
            (New-M013BackupManifestFixtureJson).Replace(
                "41afbc972e3965ef7af89ccc1cb76033d684c363224e408b001d4ad6fe53d762",
                "1111111111111111111111111111111111111111111111111111111111111111"
            ) | Set-Content -Encoding UTF8 -LiteralPath $placeholderManifestPath
            $placeholderBackupOutput = & powershell -NoProfile -ExecutionPolicy Bypass -File $backupScriptPath -Manifest $placeholderManifestPath 2>&1
            $placeholderBackupExitCode = $LASTEXITCODE
            $placeholderRestoreOutput = & powershell -NoProfile -ExecutionPolicy Bypass -File $restoreScriptPath -Manifest $placeholderManifestPath -Target (Join-Path $temporaryRoot "restore-placeholder") 2>&1
            $placeholderRestoreExitCode = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }

        if ($backupExitCode -ne 0) {
            throw "Script sauvegarde V1 invalide: $($backupOutput -join "`n")"
        }
        if ($restoreExitCode -ne 0) {
            throw "Script restauration V1 invalide: $($restoreOutput -join "`n")"
        }
        if ($invalidBackupExitCode -eq 0) {
            throw "Script sauvegarde V1 accepte un manifeste invalide: $($invalidBackupOutput -join "`n")"
        }
        if ($invalidRestoreExitCode -eq 0) {
            throw "Script restauration V1 accepte un manifeste invalide: $($invalidRestoreOutput -join "`n")"
        }
        if ($placeholderBackupExitCode -eq 0) {
            throw "Script sauvegarde V1 accepte un hash placeholder: $($placeholderBackupOutput -join "`n")"
        }
        if ($placeholderRestoreExitCode -eq 0) {
            throw "Script restauration V1 accepte un hash placeholder: $($placeholderRestoreOutput -join "`n")"
        }
    }
    finally {
        if (Test-Path -LiteralPath $temporaryRoot) {
            Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
        }
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
        "scripts/backup_v1.ps1",
        "scripts/restore_v1.ps1",
        "scripts/lib/m013_backup_manifest.ps1",
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
Assert-M013BackupRestoreScripts -ScriptDirectory (Split-Path -Parent $resolvedTestGatePath)

$drillContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedDrillPath).TrimStart([char] 0xFEFF)
$matrixContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedMatrixPath).TrimStart([char] 0xFEFF)
$testGateContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedTestGatePath).TrimStart([char] 0xFEFF)
$lintGateContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedLintGatePath).TrimStart([char] 0xFEFF)

Assert-M013BackupRestoreDrillReport -DrillContent $drillContent
Assert-M013Traceability -MatrixContent $matrixContent -TestGateContent $testGateContent -LintGateContent $lintGateContent

Write-Host "Sauvegarde restauration M-013 valide: restore_test_result, aucun secret en Git, aucune donnée métier sur Spark, projections régénérables non autorité, résultats négatifs et supersédés conservés."
