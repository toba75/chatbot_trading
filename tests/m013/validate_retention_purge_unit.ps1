$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$validatorPath = Join-Path $repoRoot "scripts/validate_m013_retention.ps1"
$temporaryRoot = Join-Path $repoRoot (".tmp_m013_retention_unit_" + [System.Guid]::NewGuid().ToString("N"))
$eAcute = [char] 0x00E9

$pythonCode = @'
import sys

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.platform.retention import (
    ADMINISTRATIVE_PURGE,
    LOGICAL_ARCHIVE,
    ORDINARY_PURGE,
    PURGE_CONVERSATION_CONTENT,
    PURGE_REGENERABLE_PROJECTION,
    RETENTION_POLICY_VERSION,
    RetentionOperationRequest,
    RetentionPolicy,
    build_m013_retention_policy,
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


def request(**overrides):
    payload = {
        "request_id": "RETENTION-REQ-UNIT-001",
        "category_id": "EG_CLAIMS",
        "operation": LOGICAL_ARCHIVE,
        "justification": "Archivage logique demandé après revue administrative documentée.",
        "audit_event_id": "AUDIT-M013-RETENTION-UNIT-001",
        "requested_by": "operateur-v1",
        "requested_at": "2026-07-08T10:00:00Z",
        "target_stable_identifiers": ("CLAIM-M013-UNIT-001",),
        "cascade_to_knowledge": False,
        "cascade_to_experiments": False,
        "reconstruction_command": "Non applicable: artefact d'autorité conservé.",
        "read_compatibility_proof": "Identifiant stable résoluble pendant 120 mois.",
        "retains_negative_or_superseded": True,
    }
    payload.update(overrides)
    return RetentionOperationRequest(**payload)


# Given les catégories durables V1 sont publiées par DDD-ADR-012.
# When la politique de rétention est construite.
# Then chaque durée, opération, justification, audit et règle de lecture est explicite.
policy = build_m013_retention_policy()
assert_equal(policy.policy_version, RETENTION_POLICY_VERSION, "La version de politique doit être explicite.")
assert_equal(len(policy.categories), 9, "Chaque catégorie durable V1 doit être couverte.")
for category in (
    "SP_ORIGINALS",
    "SP_CANONICAL_VERSIONS",
    "KA_REGENERABLE_PROJECTIONS",
    "EG_CLAIMS",
    "RA_VERIFIED_ANSWERS",
    "CV_CONVERSATIONS",
    "SD_STRATEGY_SNAPSHOTS",
    "EX_EXPERIMENT_RESULTS",
    "EV_GOVERNANCE_DECISIONS",
):
    assert_contains(policy.categories_by_id, category, "Catégorie durable manquante.")

assert_equal(policy.categories_by_id["EG_CLAIMS"].retention_months, 120, "EG doit conserver les claims dix ans.")
assert_equal(policy.categories_by_id["CV_CONVERSATIONS"].retention_months, 18, "CV doit avoir une durée conversationnelle explicite.")
assert_equal(policy.categories_by_id["KA_REGENERABLE_PROJECTIONS"].retention_months, 3, "KA doit avoir une durée de projection explicite.")
assert_equal(policy.categories_by_id["KA_REGENERABLE_PROJECTIONS"].regenerable_projection, True, "KA doit rester projection régénérable.")
assert_equal(policy.categories_by_id["EG_CLAIMS"].preserve_negative_or_superseded, True, "Les claims défavorables doivent rester conservés.")

policy.validate_operation(request())
policy.validate_operation(
    request(
        category_id="CV_CONVERSATIONS",
        operation=PURGE_CONVERSATION_CONTENT,
        target_stable_identifiers=("CONV-M013-UNIT-001",),
        retains_negative_or_superseded=False,
        read_compatibility_proof="La suppression CV garde les références publiques déjà publiées hors conversation.",
    )
)
policy.validate_operation(
    request(
        category_id="KA_REGENERABLE_PROJECTIONS",
        operation=PURGE_REGENERABLE_PROJECTION,
        target_stable_identifiers=("PROJ-M013-UNIT-001",),
        reconstruction_command="powershell -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\rebuild_knowledge_projection.ps1 -Source SP",
        read_compatibility_proof="Projection reconstruite depuis corpus et versions canoniques.",
        retains_negative_or_superseded=False,
    )
)

assert_raises("durable inconnue", lambda: request(category_id="UNKNOWN"))
assert_raises("absente", lambda: policy.categories_by_id["EG_CLAIMS"].with_retention_months(0))
assert_raises("justification administrative requise", lambda: request(justification=""))
assert_raises("audit administratif requis", lambda: request(audit_event_id=""))
assert_raises("suppression ordinaire interdite", lambda: request(operation=ORDINARY_PURGE))
assert_raises("administrative non", lambda: request(operation=ADMINISTRATIVE_PURGE))
assert_raises(
    "doit rester",
    lambda: request(category_id="EX_EXPERIMENT_RESULTS", retains_negative_or_superseded=False),
)
assert_raises(
    "conversation sans cascade",
    lambda: request(category_id="CV_CONVERSATIONS", operation=PURGE_CONVERSATION_CONTENT, cascade_to_knowledge=True),
)
assert_raises(
    "conversation sans cascade",
    lambda: request(category_id="CV_CONVERSATIONS", operation=PURGE_CONVERSATION_CONTENT, cascade_to_experiments=True),
)
assert_raises(
    "reconstruction requise",
    lambda: request(category_id="KA_REGENERABLE_PROJECTIONS", operation=PURGE_REGENERABLE_PROJECTION, reconstruction_command=""),
)
assert_raises(
    "lecture requise",
    lambda: request(read_compatibility_proof=""),
)

print("Tests unitaires RetentionPolicy M-013: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_retention_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Tests unitaires RetentionPolicy M-013 invalides. Sortie: $($output -join "`n")"
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

    $policyPath = Join-Path $ProjectRoot "docs/governance/m013_retention_policy.md"
    $matrixPath = Join-Path $ProjectRoot "docs/traceability/matrix.md"
    $adrPath = Join-Path $ProjectRoot "docs/adr/DDD-ADR-012-politique-retention-purge-administrative-v1.md"
    $adrIndexPath = Join-Path $ProjectRoot "docs/adr/index.md"
    $testGatePath = Join-Path $ProjectRoot "scripts/test.ps1"
    $lintGatePath = Join-Path $ProjectRoot "scripts/lint.ps1"

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File $validatorPath `
            -PolicyPath $policyPath `
            -MatrixPath $matrixPath `
            -AdrPath $adrPath `
            -AdrIndexPath $adrIndexPath `
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
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/adr") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "scripts") -Force | Out-Null

    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/governance/m013_retention_policy.md") -Destination (Join-Path $projectRoot "docs/governance/m013_retention_policy.md")
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/traceability/matrix.md") -Destination (Join-Path $projectRoot "docs/traceability/matrix.md")
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/adr/DDD-ADR-012-politique-retention-purge-administrative-v1.md") -Destination (Join-Path $projectRoot "docs/adr/DDD-ADR-012-politique-retention-purge-administrative-v1.md")
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/adr/index.md") -Destination (Join-Path $projectRoot "docs/adr/index.md")
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
    throw "Validateur rétention purge M-013 absent: scripts/validate_m013_retention.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null
try {
    $validProjectRoot = New-FixtureProject -Name "valid"
    $validResult = Invoke-Validator -ProjectRoot $validProjectRoot
    if ($validResult.ExitCode -ne 0) {
        throw "La fixture valide T-008 doit réussir. Sortie: $($validResult.Output)"
    }
    Assert-OutputContains `
        -Output $validResult.Output `
        -Expected "purge M-013 valide" `
        -Message "La fixture valide doit annoncer le GREEN T-008."

    Assert-ValidatorFails `
        -Name "duree-absente" `
        -ExpectedMessage "Durée de rétention absente" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_retention_policy.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("| EG_CLAIMS | 120 |", "| EG_CLAIMS |  |") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "purge-ordinaire" `
        -ExpectedMessage "Purge ordinaire interdite" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_retention_policy.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("Aucune purge ordinaire", "Purge ordinaire autorisée") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "conversation-cascade" `
        -ExpectedMessage "Conversation sans cascade vers connaissances ou expériences" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_retention_policy.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("cascade interdite vers KA, EG, RA, SD et EX", "cascade autorisée vers KA et EX") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "projection-sans-reconstruction" `
        -ExpectedMessage "Projection régénérable sans reconstruction" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_retention_policy.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\rebuild_knowledge_projection.ps1 -Source SP", "Non documenté") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "adr-index-absente" `
        -ExpectedMessage "ADR index absente: DDD-ADR-012" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/adr/index.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("DDD-ADR-012", "DDD-ADR-999") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }
}
finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

Write-Host "Tests unitaires du validateur r$($eAcute)tention purge M-013: OK"
