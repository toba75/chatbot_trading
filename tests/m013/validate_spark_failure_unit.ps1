$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$validatorPath = Join-Path $repoRoot "scripts/validate_m013_spark_failures.ps1"
$temporaryRoot = Join-Path $repoRoot (".tmp_m013_spark_failure_unit_" + [System.Guid]::NewGuid().ToString("N"))

$pythonCode = @'
import sys

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.platform.llm_gateway.spark_failure_drill import (
    FAILURE_API_KEY_REJECTED,
    FAILURE_CIRCUIT_BREAKER_CLOSED,
    FAILURE_CIRCUIT_BREAKER_OPEN,
    FAILURE_FIRST_TOKEN_TIMEOUT,
    FAILURE_SPARK_UNAVAILABLE,
    FAILURE_STREAM_CUT_AFTER_FIRST_TOKEN,
    FAILURE_STREAM_CUT_BEFORE_FIRST_TOKEN,
    FAILURE_TLS_REJECTED,
    LOCAL_CAPABILITY_AUDIT,
    LOCAL_CAPABILITY_INGESTION,
    LOCAL_CAPABILITY_RESTORE,
    LOCAL_CAPABILITY_SEARCH,
    SPARK_FAILURE_DRILL_POLICY_VERSION,
    SparkFailureCase,
    SparkFailureDrillPolicy,
    build_m013_spark_failure_drill,
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


def case(**overrides):
    payload = {
        "case_id": "SPARK-FAIL-UNIT-001",
        "failure_mode": FAILURE_SPARK_UNAVAILABLE,
        "consumer_context": "RA",
        "public_status": "LLM_UNAVAILABLE",
        "diagnostic_code": "LLM_UNAVAILABLE",
        "complete_generation": False,
        "factual_response_published": False,
        "strategy_snapshot_created": False,
        "llm_benchmark_promoted": False,
        "alternative_provider_calls": (),
        "retry_before_first_token_count": 1,
        "retry_after_first_token_count": 0,
        "retry_limit": 1,
        "first_token_emitted": False,
        "idempotency_key": "idem-unit-t006",
        "circuit_breaker_open_visible": True,
        "circuit_breaker_close_visible": False,
        "local_capabilities_available": (
            LOCAL_CAPABILITY_INGESTION,
            LOCAL_CAPABILITY_RESTORE,
            LOCAL_CAPABILITY_SEARCH,
            LOCAL_CAPABILITY_AUDIT,
        ),
        "metric_public_labels": ("status=LLM_UNAVAILABLE", "component=llm-gateway"),
        "outbox_event_ids": ("OUTBOX-SPARK-FAIL-UNIT-001",),
    }
    payload.update(overrides)
    return SparkFailureCase(**payload)


policy = SparkFailureDrillPolicy(policy_version=SPARK_FAILURE_DRILL_POLICY_VERSION)
drill = build_m013_spark_failure_drill()
policy.validate_drill(drill)

expected_modes = {
    FAILURE_SPARK_UNAVAILABLE,
    FAILURE_FIRST_TOKEN_TIMEOUT,
    FAILURE_TLS_REJECTED,
    FAILURE_API_KEY_REJECTED,
    FAILURE_STREAM_CUT_BEFORE_FIRST_TOKEN,
    FAILURE_STREAM_CUT_AFTER_FIRST_TOKEN,
    FAILURE_CIRCUIT_BREAKER_OPEN,
    FAILURE_CIRCUIT_BREAKER_CLOSED,
}
assert_equal(set(drill.cases_by_failure_mode), expected_modes, "Tous les modes de panne Spark T-006 doivent être couverts.")
for context in ("RA", "CV", "SD", "EV"):
    assert_contains(drill.consumer_contexts, context, "Chaque consommateur V1 sensible doit être couvert.")
for capability in (
    LOCAL_CAPABILITY_INGESTION,
    LOCAL_CAPABILITY_RESTORE,
    LOCAL_CAPABILITY_SEARCH,
    LOCAL_CAPABILITY_AUDIT,
):
    assert_contains(drill.local_capabilities_available, capability, "Les fonctions locales hors Gemma doivent rester disponibles.")
assert_contains(drill.public_statuses, "LLM_UNAVAILABLE", "LLM_UNAVAILABLE doit être publié pour l'indisponibilité Spark.")
assert_contains(drill.public_statuses, "LLM_PARTIAL_OUTPUT", "La coupure après premier token doit être explicite.")
assert_equal(drill.acceptance_allowed, True, "Le drill conforme doit être acceptabile par la gate T-006.")

assert_raises("factuelle", lambda: case(factual_response_published=True))
assert_raises("interdite sur panne", lambda: case(complete_generation=True))
assert_raises("snapshot", lambda: case(strategy_snapshot_created=True))
assert_raises("benchmark LLM promu interdit", lambda: case(llm_benchmark_promoted=True))
assert_raises("provider alternatif interdit", lambda: case(alternative_provider_calls=("openai-remote",)))
assert_raises("premier token interdit", lambda: case(first_token_emitted=True, retry_after_first_token_count=1))
assert_raises(
    "premier token requis",
    lambda: case(
        failure_mode=FAILURE_STREAM_CUT_AFTER_FIRST_TOKEN,
        public_status="LLM_PARTIAL_OUTPUT",
        diagnostic_code="LLM_PARTIAL_OUTPUT",
        retry_before_first_token_count=0,
        first_token_emitted=False,
    ),
)
assert_raises(
    "premier token interdit",
    lambda: case(
        failure_mode=FAILURE_STREAM_CUT_BEFORE_FIRST_TOKEN,
        public_status="LLM_UNAVAILABLE",
        diagnostic_code="LLM_UNAVAILABLE",
        retry_before_first_token_count=1,
        first_token_emitted=True,
    ),
)
assert_raises("retry", lambda: case(retry_before_first_token_count=2, retry_limit=1))
assert_raises("idempotence retry requise", lambda: case(idempotency_key=""))
assert_raises("prompt complet interdit", lambda: case(metric_public_labels=("prompt complet: secret",)))
assert_raises("double outbox interdit", lambda: case(outbox_event_ids=("EVT-1", "EVT-1")))
assert_raises(
    "circuit breaker ouvert",
    lambda: policy.validate_drill(
        drill.with_replaced_case(
            case(
                case_id="SPARK-FAIL-CIRCUIT-OPEN",
                failure_mode=FAILURE_CIRCUIT_BREAKER_OPEN,
                public_status="LLM_CIRCUIT_OPEN",
                diagnostic_code="LLM_CIRCUIT_OPEN",
                retry_before_first_token_count=0,
                retry_limit=1,
                circuit_breaker_open_visible=False,
            )
        )
    ),
)
assert_raises(
    "circuit breaker",
    lambda: policy.validate_drill(
        drill.with_replaced_case(
            case(
                case_id="SPARK-FAIL-CIRCUIT-CLOSED",
                failure_mode=FAILURE_CIRCUIT_BREAKER_CLOSED,
                public_status="LLM_RECOVERED",
                diagnostic_code="LLM_RECOVERED",
                retry_before_first_token_count=0,
                retry_limit=1,
                circuit_breaker_open_visible=False,
                circuit_breaker_close_visible=False,
            )
        )
    ),
)

print("Tests unitaires SparkFailureDrillPolicy M-013: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_spark_failure_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Tests unitaires SparkFailureDrillPolicy M-013 invalides. Sortie: $($output -join "`n")"
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

    $drillPath = Join-Path $ProjectRoot "docs/governance/m013_spark_failure_drill.md"
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

    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/governance/m013_spark_failure_drill.md") -Destination (Join-Path $projectRoot "docs/governance/m013_spark_failure_drill.md")
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

function Remove-TemporaryRoot {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    for ($attempt = 1; $attempt -le 5; $attempt++) {
        try {
            Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
            return
        }
        catch {
            if ($attempt -eq 5) {
                throw
            }
            Start-Sleep -Milliseconds (200 * $attempt)
        }
    }
}

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur pannes Spark M-013 absent: scripts/validate_m013_spark_failures.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null
try {
    $validProjectRoot = New-FixtureProject -Name "valid"
    $validResult = Invoke-Validator -ProjectRoot $validProjectRoot
    if ($validResult.ExitCode -ne 0) {
        throw "La fixture valide T-006 doit réussir. Sortie: $($validResult.Output)"
    }
    Assert-OutputContains `
        -Output $validResult.Output `
        -Expected "Pannes Spark M-013 valides" `
        -Message "La fixture valide doit annoncer le GREEN T-006."

    Assert-ValidatorFails `
        -Name "statut-absent" `
        -ExpectedMessage "statut public panne Spark absent: LLM_UNAVAILABLE" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_spark_failure_drill.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("LLM_UNAVAILABLE", "LLM_MASQUE") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "fallback-documente" `
        -ExpectedMessage "Contenu interdit dans le drill pannes Spark" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_spark_failure_drill.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("aucun provider alternatif", "fallback distant de secours") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "traceabilite-absente" `
        -ExpectedMessage "Traçabilité T-006 absente: REQ-M013-006" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/traceability/matrix.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("REQ-M013-006", "REQ-M013-XXX") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }
}
finally {
    Remove-TemporaryRoot -Path $temporaryRoot
}

Write-Host "Tests unitaires du validateur pannes Spark M-013: OK"
