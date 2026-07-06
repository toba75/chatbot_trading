$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$pythonCode = @'
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

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
REPORT_PATH = repo_root / "docs" / "evaluation" / "m012" / "calibration_promotion_decisions_report.md"


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_contains(text, fragment, message):
    if fragment not in text:
        raise AssertionError(message)


def assert_raises(expected_fragment, action):
    try:
        action()
    except (TypeError, ValueError) as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}") from exc
        return
    raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


# Given les benchmarks documentaires, recherche, EG, RA, CV, SD, LLM et EX sont termines.
register = build_m012_calibration_decision_register()

# When les decisions de calibration et de promotion sont publiees.
policy = CalibrationDecisionPolicy(policy_version=POLICY_VERSION)
policy.validate_register(register)

# Then chaque decision reference ses sources benchmark, versionne ses seuils ou criteres et conserve refus/reports.
expected_contexts = {"SP", "KA", "EG", "RA", "CV", "SD", "LLM", "EX"}
assert_equal(set(register.decisions_by_context), expected_contexts, "Tous les contextes M-012 doivent publier une decision.")
assert any(decision.status == REJECTED for decision in register.decisions), "Un refus doit etre conserve."
assert any(decision.status == DEFERRED for decision in register.decisions), "Un report doit etre conserve."
for decision in register.decisions:
    assert decision.benchmark_sources, f"Benchmark source absent pour {decision.decision_id}"
    assert decision.adr_refs, f"ADR absente pour {decision.decision_id}"
    for source in decision.benchmark_sources:
        assert source.artifact_path.startswith("docs/evaluation/m012/"), source.artifact_path
    for threshold in decision.thresholds:
        assert_equal(threshold.policy_version, decision.policy_version, "Un seuil doit porter la version de politique.")

# Then une promotion communautaire exige la comparaison de toutes les taches LLM obligatoires.
llm_decision = register.decisions_by_context["LLM"]
assert_equal(llm_decision.status, REJECTED, "La promotion communautaire pilote doit rester refusee.")
assert_equal(set(llm_decision.compared_llm_tasks), set(policy.required_llm_tasks), "Toutes les taches LLM doivent etre comparees.")

# Then un test scientifique RED reste visible malgre les gates logiciels GREEN.
red_verdicts = [verdict for decision in register.decisions for verdict in decision.scientific_verdicts if verdict.status == SCIENTIFIC_RED]
assert red_verdicts, "Un test scientifique RED doit rester visible."
assert any(verdict.software_gate_status == "GREEN" for verdict in red_verdicts), "Le gate logiciel GREEN ne doit pas cacher le RED scientifique."

report = REPORT_PATH.read_text(encoding="utf-8")
assert_contains(report, "Test scientifique RED", "Le rapport doit mentionner les tests scientifiques RED.")
assert_contains(report, "gate logiciel GREEN", "Le rapport doit distinguer RED scientifique et GREEN logiciel.")
assert_contains(report, "REJECTED", "Le rapport doit conserver les refus.")
assert_contains(report, "DEFERRED", "Le rapport doit conserver les reports.")
assert_contains(report, "ADR-010", "Le rapport doit referencer les ADR applicables.")

# Garde-fous explicites: aucune decision favorable sans metriques critiques, EG/RA/SD/CV/LLM obligatoires.
def source(context, metric_names):
    return BenchmarkSourceLink(
        benchmark_id=f"RUN-M012-{context}",
        context=context,
        artifact_path=f"docs/evaluation/m012/{context.lower()}_benchmark_report.md",
        policy_version="BenchmarkPolicy-M012-1.0",
        metric_names=metric_names,
    )


def threshold(metric_name):
    return CalibrationThreshold(
        threshold_id=f"THR-M012-{metric_name}",
        metric_name=metric_name,
        operator="MINIMUM",
        value="0.800000000000",
        policy_version=POLICY_VERSION,
    )


def accepted_decision(context, metric_names, criteria=(), compared_llm_tasks=()):
    first_metric = metric_names[0]
    return PromotionDecision(
        decision_id=f"DEC-M012-{context}-ACCEPTED",
        policy_version=POLICY_VERSION,
        context=context,
        status=ACCEPTED,
        benchmark_sources=(source(context, metric_names),),
        thresholds=(threshold(first_metric),),
        criteria=criteria,
        scientific_verdicts=(
            ScientificGateVerdict(
                verdict_id=f"SCI-M012-{context}",
                status="GREEN",
                metric_name=first_metric,
                benchmark_source_id=f"RUN-M012-{context}",
                software_gate_status="GREEN",
                reason="mesure pilote conforme",
            ),
        ),
        adr_refs=("ADR-010", "DDD-ADR-010"),
        v1_gap_refs=(),
        justification="Decision favorable de test.",
        compared_llm_tasks=compared_llm_tasks,
    )


assert_raises(
    "decision favorable avec metrique critique absente",
    lambda: PromotionDecision(
        decision_id="DEC-M012-NO-METRIC",
        policy_version=POLICY_VERSION,
        context="KA",
        status=ACCEPTED,
        benchmark_sources=(source("KA", ("knowledge_recall_at_10",)),),
        thresholds=(threshold("knowledge_recall_at_10"),),
        criteria=(),
        scientific_verdicts=(),
        adr_refs=("ADR-010",),
        v1_gap_refs=(),
        justification="Decision invalide.",
    ),
)
assert_raises(
    "metrique EG obligatoire absente",
    lambda: policy.publish_register(
        register_id="REG-M012-EG-INCOMPLETE",
        decisions=(accepted_decision("EG", ("evidence_claim_verified_rate",)),),
    ),
)
assert_raises(
    "metrique RA obligatoire absente",
    lambda: policy.publish_register(
        register_id="REG-M012-RA-INCOMPLETE",
        decisions=(accepted_decision("RA", ("answer_citation_precision",)),),
    ),
)
assert_raises(
    "metrique SD obligatoire absente",
    lambda: policy.publish_register(
        register_id="REG-M012-SD-INCOMPLETE",
        decisions=(accepted_decision("SD", ("strategy_compilable_rate",)),),
    ),
)
assert_raises(
    "critere CV obligatoire absent",
    lambda: policy.publish_register(
        register_id="REG-M012-CV-INCOMPLETE",
        decisions=(
            accepted_decision(
                "CV",
                ("conversation_creation_criterion",),
                criteria=(ContextDecisionCriteria("conversation_creation_criterion", POLICY_VERSION, ACCEPTED),),
            ),
        ),
    ),
)
assert_raises(
    "tache LLM obligatoire absente",
    lambda: policy.publish_register(
        register_id="REG-M012-LLM-INCOMPLETE",
        decisions=(
            accepted_decision(
                "LLM",
                ("json_valide",),
                criteria=(ContextDecisionCriteria("json_valide", POLICY_VERSION, ACCEPTED),),
                compared_llm_tasks=("json_valide",),
            ),
        ),
    ),
)

print("Test d'acceptation T-011 decisions calibration promotion M-012: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m012_calibration_decisions_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Test d'acceptation T-011 decisions calibration promotion M-012 invalide. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
