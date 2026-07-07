$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$validatorPath = Join-Path $repoRoot "scripts/validate_m013_backup_restore.ps1"
$temporaryRoot = Join-Path $repoRoot (".tmp_m013_backup_restore_unit_" + [System.Guid]::NewGuid().ToString("N"))

$pythonCode = @'
import sys

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.platform.backup_restore import (
    BACKUP_MANIFEST_CONTRACT_VERSION,
    BACKUP_RESTORE_DRILL_POLICY_VERSION,
    CONTEXT_CV,
    CONTEXT_EG,
    CONTEXT_EV,
    CONTEXT_EX,
    CONTEXT_KA,
    CONTEXT_RA,
    CONTEXT_SD,
    CONTEXT_SP,
    CONTEXT_PLATFORM,
    STORAGE_DOCKER_LOCAL,
    STORAGE_SPARK,
    BackupManifest,
    BackupManifestEntry,
    BackupRestoreDrillPolicy,
    RestoreTestResult,
    build_m013_backup_restore_drill,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_contains(collection, expected, message):
    if expected not in collection:
        raise AssertionError(f"{message} Valeur absente: {expected!r}")


def assert_raises(expected_fragment, action):
    try:
        action()
    except (TypeError, ValueError) as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}") from exc
        return
    raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def entry(**overrides):
    payload = {
        "entry_id": "BACKUP-ENTRY-UNIT-001",
        "context": CONTEXT_SP,
        "artifact_kind": "corpus_original",
        "stable_identifier": "SRC-M013-UNIT-001",
        "storage_host": STORAGE_DOCKER_LOCAL,
        "authority": True,
        "immutable": True,
        "regenerable_projection": False,
        "retained_negative_or_superseded": False,
        "backup_sha256": "a" * 64,
        "restored_sha256": "a" * 64,
        "contains_plain_secret": False,
        "git_tracked_key_material": False,
        "spark_business_storage": False,
        "destructive_restore": False,
    }
    payload.update(overrides)
    return BackupManifestEntry(**payload)


def manifest(**overrides):
    payload = {
        "manifest_id": "M013-BACKUP-MANIFEST-UNIT",
        "contract_version": BACKUP_MANIFEST_CONTRACT_VERSION,
        "backup_command": "powershell -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\backup_v1.ps1 -Manifest .\\restore\\manifest.json",
        "restore_command": "powershell -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\restore_v1.ps1 -Manifest .\\restore\\manifest.json -Target C:\\restore\\m013-isolated",
        "restore_target": "local_isolated",
        "archive_encrypted": True,
        "encryption_proof": "ciphertext_sha256=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "key_reference": "hors_depot://cle-restauration/m013",
        "key_git_tracked": False,
        "complete": True,
        "entries": (
            entry(entry_id="BACKUP-ENTRY-UNIT-SP", context=CONTEXT_SP, artifact_kind="corpus_original", stable_identifier="SRC-M013-UNIT-001"),
            entry(entry_id="BACKUP-ENTRY-UNIT-KA", context=CONTEXT_KA, artifact_kind="qdrant_projection", stable_identifier="PROJ-M013-UNIT-001", authority=False, immutable=False, regenerable_projection=True),
            entry(entry_id="BACKUP-ENTRY-UNIT-EG", context=CONTEXT_EG, artifact_kind="claim_registry", stable_identifier="CLAIM-M013-UNIT-001", retained_negative_or_superseded=True),
            entry(entry_id="BACKUP-ENTRY-UNIT-RA", context=CONTEXT_RA, artifact_kind="verified_answers", stable_identifier="ANSWER-M013-UNIT-001", retained_negative_or_superseded=True),
            entry(entry_id="BACKUP-ENTRY-UNIT-CV", context=CONTEXT_CV, artifact_kind="conversation_turns", stable_identifier="CONV-M013-UNIT-001"),
            entry(entry_id="BACKUP-ENTRY-UNIT-SD", context=CONTEXT_SD, artifact_kind="strategy_snapshots", stable_identifier="STRAT-M013-UNIT-001", retained_negative_or_superseded=True),
            entry(entry_id="BACKUP-ENTRY-UNIT-EX", context=CONTEXT_EX, artifact_kind="experiment_results", stable_identifier="EXP-M013-UNIT-001", retained_negative_or_superseded=True),
            entry(entry_id="BACKUP-ENTRY-UNIT-EV", context=CONTEXT_EV, artifact_kind="evaluation_reports", stable_identifier="EVAL-M013-UNIT-001", retained_negative_or_superseded=True),
            entry(entry_id="BACKUP-ENTRY-UNIT-PLATFORM", context=CONTEXT_PLATFORM, artifact_kind="governance_artifacts", stable_identifier="GOV-M013-UNIT-001"),
        ),
    }
    payload.update(overrides)
    return BackupManifest(**payload)


def restore_result(**overrides):
    payload = {
        "result_id": "restore_test_result",
        "status": "GREEN",
        "command": "powershell -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\restore_v1.ps1 -Manifest .\\restore\\manifest.json -Target C:\\restore\\m013-isolated",
        "verified_hashes": True,
        "stable_identifiers_preserved": True,
        "immutable_artifacts_preserved": True,
        "negative_and_superseded_available": True,
        "projections_rebuilt_from_authority": True,
        "spark_required_for_business_data": False,
        "destructive_restore_performed": False,
        "traceability_verified": True,
    }
    payload.update(overrides)
    return RestoreTestResult(**payload)


# Given un manifeste de sauvegarde V1 complet.
# When la politique BackupRestorePolicy valide le drill.
# Then chaque contexte propriétaire, hash restauré, résultat défavorable et projection régénérable reste contrôlé.
policy = BackupRestoreDrillPolicy(policy_version=BACKUP_RESTORE_DRILL_POLICY_VERSION)
drill = build_m013_backup_restore_drill()
policy.validate_drill(drill)

for context in (CONTEXT_SP, CONTEXT_KA, CONTEXT_EG, CONTEXT_RA, CONTEXT_CV, CONTEXT_SD, CONTEXT_EX, CONTEXT_EV, CONTEXT_PLATFORM):
    assert_contains(drill.manifest.contexts, context, "Chaque contexte V1 doit être couvert par le manifeste.")
assert_equal(drill.restore_test_result.status, "GREEN", "Le résultat de restauration doit être GREEN.")
assert_equal(drill.acceptance_allowed, True, "Le drill conforme doit être accepté.")

assert_raises("manifest incomplet", lambda: manifest(complete=False))
assert_raises("archive chiffrée requise", lambda: manifest(archive_encrypted=False))
assert_raises("clé hors dépôt requise", lambda: manifest(key_reference="repo://secrets/m013.key"))
assert_raises("clé versionnée interdite", lambda: manifest(key_git_tracked=True))
assert_raises("secret en clair interdit", lambda: entry(contains_plain_secret=True))
assert_raises("contexte V1 absent", lambda: policy.validate_manifest(manifest(entries=tuple(item for item in manifest().entries if item.context != CONTEXT_RA))))
assert_raises("hash restauré absent", lambda: entry(restored_sha256=""))
assert_raises("hash restauré divergent", lambda: entry(restored_sha256="b" * 64))
assert_raises("projection régénérable non autorité", lambda: entry(context=CONTEXT_KA, artifact_kind="qdrant_projection", authority=True, regenerable_projection=True))
assert_raises("restauration destructive interdite", lambda: entry(destructive_restore=True))
assert_raises("stockage métier Spark interdit", lambda: entry(storage_host=STORAGE_SPARK))
assert_raises("stockage métier Spark interdit", lambda: entry(spark_business_storage=True))
assert_raises("commande de restauration requise", lambda: restore_result(command=""))
assert_raises("résultats négatifs et supersédés conservés", lambda: restore_result(negative_and_superseded_available=False))
assert_raises("projections régénérables non autorité", lambda: restore_result(projections_rebuilt_from_authority=False))
assert_raises("Spark interdit pour les données métier", lambda: restore_result(spark_required_for_business_data=True))

print("Tests unitaires BackupRestorePolicy M-013: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_backup_restore_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $env:PYTHONIOENCODING = "utf-8"
        $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0) {
        throw "Tests unitaires BackupRestorePolicy M-013 invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

function Invoke-Validator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot
    )

    $drillPath = Join-Path $ProjectRoot "docs/governance/m013_backup_restore_drill.md"
    $matrixPath = Join-Path $ProjectRoot "docs/traceability/matrix.md"
    $testGatePath = Join-Path $ProjectRoot "scripts/test.ps1"
    $lintGatePath = Join-Path $ProjectRoot "scripts/lint.ps1"

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File $validatorPath `
            -DrillPath $drillPath `
            -MatrixPath $matrixPath `
            -TestGatePath $testGatePath `
            -LintGatePath $lintGatePath 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    return [pscustomobject] @{
        ExitCode = $exitCode
        Output = ($output -join "`n")
    }
}

function Assert-OutputContains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Output,

        [Parameter(Mandatory = $true)]
        [string] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if (-not $Output.Contains($Expected)) {
        throw "$Message Sortie obtenue: $Output"
    }
}

function New-FixtureProject {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    $projectRoot = Join-Path $temporaryRoot $Name
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/governance") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/traceability") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "scripts") -Force | Out-Null

    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/governance/m013_backup_restore_drill.md") -Destination (Join-Path $projectRoot "docs/governance/m013_backup_restore_drill.md")
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/traceability/matrix.md") -Destination (Join-Path $projectRoot "docs/traceability/matrix.md")
    Copy-Item -LiteralPath (Join-Path $repoRoot "scripts/test.ps1") -Destination (Join-Path $projectRoot "scripts/test.ps1")
    Copy-Item -LiteralPath (Join-Path $repoRoot "scripts/lint.ps1") -Destination (Join-Path $projectRoot "scripts/lint.ps1")

    return $projectRoot
}

function Assert-ValidatorFails {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $true)]
        [scriptblock] $Mutate,

        [Parameter(Mandatory = $true)]
        [string] $ExpectedMessage
    )

    $projectRoot = New-FixtureProject -Name $Name
    & $Mutate $projectRoot
    $result = Invoke-Validator -ProjectRoot $projectRoot

    if ($result.ExitCode -eq 0) {
        throw "Le cas RED $Name doit échouer."
    }

    Assert-OutputContains `
        -Output $result.Output `
        -Expected $ExpectedMessage `
        -Message "Le cas RED $Name doit nommer la règle violée."
}

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur sauvegarde restauration M-013 absent: scripts/validate_m013_backup_restore.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null
try {
    $validProjectRoot = New-FixtureProject -Name "valid"
    $validResult = Invoke-Validator -ProjectRoot $validProjectRoot
    if ($validResult.ExitCode -ne 0) {
        throw "La fixture valide T-007 doit réussir. Sortie: $($validResult.Output)"
    }
    Assert-OutputContains `
        -Output $validResult.Output `
        -Expected "Sauvegarde restauration M-013 valide" `
        -Message "La fixture valide doit annoncer le GREEN T-007."

    Assert-ValidatorFails `
        -Name "restore-result-absent" `
        -ExpectedMessage "Marqueur drill sauvegarde restauration absent: restore_test_result" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_backup_restore_drill.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("restore_test_result", "restore_result_masque") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "secret-documente" `
        -ExpectedMessage "Secret complet interdit dans le drill sauvegarde restauration M-013" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_backup_restore_drill.md"
            Add-Content -Encoding UTF8 -LiteralPath $path -Value "`nGEMMA_API_KEY=SECRET_INTERDIT_M013"
        }

    Assert-ValidatorFails `
        -Name "traceabilite-absente" `
        -ExpectedMessage "Traçabilité T-007 absente: REQ-M013-007" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/traceability/matrix.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("REQ-M013-007", "REQ-M013-XXX") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }
}
finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

Write-Host "Tests unitaires du validateur sauvegarde restauration M-013: OK"
