$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$pythonCode = @'
import sys

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.evaluation.domain.calibration_decisions import (
    ACCEPTED,
    DEFERRED,
    REJECTED,
    SCIENTIFIC_RED,
    BenchmarkSourceLink,
    CalibrationDecisionPolicy,
    CalibrationThreshold,
    ContextDecisionCriteria,
    PromotionDecision,
    ScientificGateVerdict,
    build_m012_calibration_decision_register,
)


POLICY_VERSION = "CalibrationDecisionPolicy-M012-1.0"
ADR_REFS = ("ADR-010", "DDD-ADR-010")


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_raises(expected_fragment, action):
    try:
        action()
    except (TypeError, ValueError) as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}") from exc
        return
    raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def source(context="KA", metric_names=("knowledge_recall_at_10",), benchmark_id="RUN-M012-KA", **overrides):
    payload = {
        "benchmark_id": benchmark_id,
        "context": context,
        "artifact_path": f"docs/evaluation/m012/{context.lower()}_benchmark_report.md",
        "policy_version": "BenchmarkPolicy-M012-1.0",
        "metric_names": metric_names,
    }
    payload.update(overrides)
    return BenchmarkSourceLink(**payload)


def threshold(metric_name="knowledge_recall_at_10"):
    return CalibrationThreshold(
        threshold_id=f"THR-M012-{metric_name}",
        metric_name=metric_name,
        operator="MINIMUM",
        value="0.850000000000",
        policy_version=POLICY_VERSION,
    )


def verdict(status=SCIENTIFIC_RED, metric_name="knowledge_recall_at_10", benchmark_source_id="RUN-M012-KA"):
    return ScientificGateVerdict(
        verdict_id=f"SCI-M012-{metric_name}",
        status=status,
        metric_name=metric_name,
        benchmark_source_id=benchmark_source_id,
        software_gate_status="GREEN",
        reason="mesure scientifique sous seuil conservee",
    )


def decision(**overrides):
    context = overrides.get("context", "KA")
    benchmark_id = f"RUN-M012-{context}"
    metric_name = "knowledge_recall_at_10"
    payload = {
        "decision_id": "DEC-M012-KA-RECALL",
        "policy_version": POLICY_VERSION,
        "context": context,
        "status": REJECTED,
        "benchmark_sources": (source(context=context, benchmark_id=benchmark_id, metric_names=(metric_name,)),),
        "thresholds": (threshold(metric_name),),
        "criteria": (),
        "scientific_verdicts": (verdict(metric_name=metric_name, benchmark_source_id=benchmark_id),),
        "adr_refs": ADR_REFS,
        "v1_gap_refs": ("V1-GAP-M012-KA-RECALL",),
        "justification": "Recall@10 pilote sous le seuil de promotion.",
    }
    payload.update(overrides)
    return PromotionDecision(**payload)


policy = CalibrationDecisionPolicy(policy_version=POLICY_VERSION)

assert_raises(
    "benchmark source requis",
    lambda: decision(benchmark_sources=()),
)
assert_raises(
    "version de politique requise",
    lambda: CalibrationThreshold(
        threshold_id="THR-M012-NOVERSION",
        metric_name="knowledge_recall_at_10",
        operator="MINIMUM",
        value="0.850000000000",
        policy_version="",
    ),
)
assert_raises(
    "decision favorable avec metrique critique absente",
    lambda: decision(status=ACCEPTED, scientific_verdicts=()),
)
assert_raises(
    "decision structurante sans ADR",
    lambda: decision(adr_refs=()),
)
assert_raises(
    "benchmark obsolete interdit",
    lambda: source(policy_version="BenchmarkPolicy-M012-current"),
)
assert_raises(
    "conflit de decisions",
    lambda: policy.publish_register(
        register_id="REG-M012-CONFLICT",
        decisions=(
            decision(status=REJECTED),
            decision(status=DEFERRED),
        ),
    ),
)

register = build_m012_calibration_decision_register()
assert_equal(register.statuses_by_decision_id["DEC-M012-KA-REJECTED"], REJECTED, "Un refus doit rester dans le registre.")
assert_equal(register.statuses_by_decision_id["DEC-M012-SP-DEFERRED"], DEFERRED, "Un report doit rester dans le registre.")

accepted_eg = decision(
    decision_id="DEC-M012-EG-ACCEPTED",
    context="EG",
    status=ACCEPTED,
    benchmark_sources=(source("EG", ("evidence_claim_verified_rate",)),),
    thresholds=(threshold("evidence_claim_verified_rate"),),
    scientific_verdicts=(verdict("GREEN", "evidence_claim_verified_rate"),),
)
assert_raises(
    "metrique EG obligatoire absente",
    lambda: policy.publish_register(register_id="REG-M012-MISSING-EG", decisions=(accepted_eg,)),
)

accepted_ra = decision(
    decision_id="DEC-M012-RA-ACCEPTED",
    context="RA",
    status=ACCEPTED,
    benchmark_sources=(source("RA", ("answer_citation_precision",)),),
    thresholds=(threshold("answer_citation_precision"),),
    scientific_verdicts=(verdict("GREEN", "answer_citation_precision"),),
)
assert_raises(
    "metrique RA obligatoire absente",
    lambda: policy.publish_register(register_id="REG-M012-MISSING-RA", decisions=(accepted_ra,)),
)

accepted_sd = decision(
    decision_id="DEC-M012-SD-ACCEPTED",
    context="SD",
    status=ACCEPTED,
    benchmark_sources=(source("SD", ("strategy_compilable_rate",)),),
    thresholds=(threshold("strategy_compilable_rate"),),
    scientific_verdicts=(verdict("GREEN", "strategy_compilable_rate"),),
)
assert_raises(
    "metrique SD obligatoire absente",
    lambda: policy.publish_register(register_id="REG-M012-MISSING-SD", decisions=(accepted_sd,)),
)

accepted_cv = decision(
    decision_id="DEC-M012-CV-ACCEPTED",
    context="CV",
    status=ACCEPTED,
    benchmark_sources=(source("CV", ("conversation_creation_criterion",)),),
    thresholds=(),
    criteria=(ContextDecisionCriteria("conversation_creation_criterion", POLICY_VERSION, ACCEPTED),),
    scientific_verdicts=(verdict("GREEN", "conversation_creation_criterion"),),
)
assert_raises(
    "critere CV obligatoire absent",
    lambda: policy.publish_register(register_id="REG-M012-MISSING-CV", decisions=(accepted_cv,)),
)

accepted_llm = decision(
    decision_id="DEC-M012-LLM-ACCEPTED",
    context="LLM",
    status=ACCEPTED,
    benchmark_sources=(source("LLM", ("json_valide",)),),
    thresholds=(),
    criteria=(ContextDecisionCriteria("json_valide", POLICY_VERSION, ACCEPTED),),
    scientific_verdicts=(verdict("GREEN", "json_valide"),),
    compared_llm_tasks=("json_valide",),
)
assert_raises(
    "tache LLM obligatoire absente",
    lambda: policy.publish_register(register_id="REG-M012-MISSING-LLM", decisions=(accepted_llm,)),
)

report = policy.render_markdown_report(register)
assert "Test scientifique RED" in report
assert "gate logiciel GREEN" in report

print("Tests unitaires T-011 decisions calibration promotion M-012: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m012_calibration_decisions_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Tests unitaires T-011 decisions calibration promotion M-012 invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
