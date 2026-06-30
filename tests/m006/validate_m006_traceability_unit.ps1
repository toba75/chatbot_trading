$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import math
import sys

sys.path.insert(0, sys.argv[1])

from app.evidence_governance.application.traceability_metrics import (
    ClaimMetricObservation,
    EvidenceGovernanceAuditSignal,
    EvidenceGovernanceMetricsPublisher,
    assert_no_documentary_payload_in_audit_payload,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_close(actual, expected, message):
    if not math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9):
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_false(condition, message):
    if condition:
        raise AssertionError(message)


def assert_raises(expected_fragment, action):
    try:
        action()
    except (TypeError, ValueError) as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


forbidden_claim_text = "Les couvertures de queue réduisent le drawdown quotidien pendant les crises de volatilité."
forbidden_evidence_text = (
    "Dans les crises de volatilité, les couvertures de queue réduisent le drawdown quotidien "
    "sur le portefeuille étudié."
)

observations = (
    ClaimMetricObservation(
        claim_id="CLM-M006-T010-VERIFIED",
        claim_version=1,
        status="VERIFIED",
        direct_evidence_count=2,
        verification_verdict="ENTAILED",
        reason_codes=(),
        dependency_group_ids=("DEP-M006-T010-PRIMARY", "DEP-M006-T010-REPLICATION"),
        submitted_at="2026-06-30T10:00:00Z",
        decided_at="2026-06-30T10:03:00Z",
        superseded_by_claim_version=None,
    ),
    ClaimMetricObservation(
        claim_id="CLM-M006-T010-REJECTED",
        claim_version=1,
        status="REJECTED",
        direct_evidence_count=0,
        verification_verdict="NOT_ENTAILED",
        reason_codes=(
            "INSUFFICIENT_DIRECT_EVIDENCE",
            "CLAIM_SCOPE_EXCEEDS_EVIDENCE",
            "CLAIM_EVIDENCE_SOURCE_UNRESOLVABLE",
        ),
        dependency_group_ids=(),
        submitted_at="2026-06-30T10:01:00Z",
        decided_at="2026-06-30T10:02:00Z",
        superseded_by_claim_version=None,
    ),
    ClaimMetricObservation(
        claim_id="CLM-M006-T010-IN-REVIEW",
        claim_version=1,
        status="UNDER_VERIFICATION",
        direct_evidence_count=1,
        verification_verdict=None,
        reason_codes=(),
        dependency_group_ids=("DEP-M006-T010-PRIMARY",),
        submitted_at="2026-06-30T10:05:00Z",
        decided_at=None,
        superseded_by_claim_version=None,
    ),
    ClaimMetricObservation(
        claim_id="CLM-M006-T010-SUPERSEDED",
        claim_version=1,
        status="SUPERSEDED",
        direct_evidence_count=1,
        verification_verdict="ENTAILED",
        reason_codes=(),
        dependency_group_ids=("DEP-M006-T010-SUPERSEDED",),
        submitted_at="2026-06-30T09:55:00Z",
        decided_at="2026-06-30T10:00:00Z",
        superseded_by_claim_version=2,
    ),
)

# Given des observations EG agrégées par identifiants de claims et preuves.
# When les métriques de clôture M-006 sont calculées.
# Then les taux, distributions, groupes de dépendance, supersession et latence sont déterministes.
snapshot = EvidenceGovernanceMetricsPublisher().publish(
    fixture_id="m006_claim_metrics_fixture_v1",
    fixture_path="tests/m006/fixtures/m006_claim_metrics_fixture.json",
    observations=observations,
    measured_at="2026-06-30T10:30:00Z",
)
payload = snapshot.to_payload()
assert_equal(payload["metric_scope"], "M006_CLAIMS_VERIFIABLES", "La portée métrique doit nommer M-006.")
assert_equal(payload["claim_count"], 4, "Le nombre de claims doit être publié.")
assert_equal(payload["status_counts"]["VERIFIED"], 1, "Les claims vérifiés doivent être comptés.")
assert_equal(payload["status_counts"]["REJECTED"], 1, "Les claims rejetés doivent être comptés.")
assert_equal(payload["status_counts"]["UNDER_VERIFICATION"], 1, "Les claims en revue doivent être comptés.")
assert_equal(payload["status_counts"]["SUPERSEDED"], 1, "Les claims supersédés doivent être comptés.")
assert_equal(
    payload["normative_signals"],
    {
        "claims_drafted_total": 4,
        "claims_verified_total": 1,
        "claims_rejected_total": 1,
        "claim_verification_latency_seconds": 180.0,
        "claim_scope_refusal_total": 1,
        "claim_independent_support_groups": 4,
        "claim_superseded_total": 1,
        "claim_model_proposal_total": 4,
        "claim_public_evidence_resolution_failed_total": 1,
    },
    "Les signaux normatifs M-006 doivent être publiés explicitement.",
)
assert_close(payload["rates"]["verified_rate"], 0.25, "Le taux vérifié est incorrect.")
assert_close(payload["rates"]["rejected_rate"], 0.25, "Le taux rejeté est incorrect.")
assert_close(payload["rates"]["in_review_rate"], 0.25, "Le taux en revue est incorrect.")
assert_close(payload["rates"]["without_direct_evidence_ratio"], 0.25, "La proportion sans preuve directe est incorrecte.")
assert_close(payload["rates"]["supersession_rate"], 0.25, "Le taux de supersession est incorrect.")
assert_equal(payload["verdict_distribution"], {"ENTAILED": 2, "NOT_ENTAILED": 1}, "La distribution des verdicts est incorrecte.")
assert_equal(
    payload["dependency_group_count_distribution"],
    {"0": 1, "1": 2, "2": 1},
    "La distribution des groupes de dépendance est incorrecte.",
)
assert_close(payload["average_verification_latency_seconds"], 180.0, "Le délai moyen de vérification est incorrect.")
assert_false(forbidden_claim_text in repr(payload), "Le texte complet du claim ne doit pas sortir dans les métriques.")
assert_false(forbidden_evidence_text in repr(payload), "Le texte documentaire ne doit pas sortir dans les métriques.")
assert_false("documentary_mention_count" in repr(payload), "Les mentions documentaires ne doivent pas devenir confirmation indépendante.")

# Les métriques ne doivent pas accepter un compteur de mentions documentaires en substitution des groupes indépendants.
assert_raises(
    "unexpected keyword argument",
    lambda: ClaimMetricObservation(
        claim_id="CLM-M006-T010-MENTION",
        claim_version=1,
        status="VERIFIED",
        direct_evidence_count=1,
        verification_verdict="ENTAILED",
        reason_codes=(),
        dependency_group_ids=("DEP-M006-T010-MENTION",),
        submitted_at="2026-06-30T10:00:00Z",
        decided_at="2026-06-30T10:01:00Z",
        superseded_by_claim_version=None,
        documentary_mention_count=4,
    ),
)

# Les décisions vérifiées ou rejetées doivent porter un délai de vérification calculable.
assert_raises(
    "decided_at requis",
    lambda: ClaimMetricObservation(
        claim_id="CLM-M006-T010-LATENCY-MISSING",
        claim_version=1,
        status="VERIFIED",
        direct_evidence_count=1,
        verification_verdict="ENTAILED",
        reason_codes=(),
        dependency_group_ids=("DEP-M006-T010-LATENCY",),
        submitted_at="2026-06-30T10:00:00Z",
        decided_at=None,
        superseded_by_claim_version=None,
    ),
)

# Les signaux d'audit publient seulement des références, hashes et compteurs, jamais le payload documentaire.
signal = EvidenceGovernanceAuditSignal.from_metric_snapshot(
    audit_signal_id="EG-AUDIT-M006-T010-0001",
    trace_id="TRACE-M006-T010-0001",
    metric_snapshot=snapshot,
    claim_refs=(
        {
            "claim_id": "CLM-M006-T010-VERIFIED",
            "claim_version": 1,
            "status": "VERIFIED",
            "proposition_hash": "a" * 64,
            "evidence_ref_ids": ("EVS-M006-T010-A", "EVS-M006-T010-B"),
            "dependency_group_ids": ("DEP-M006-T010-PRIMARY", "DEP-M006-T010-REPLICATION"),
        },
    ),
    forbidden_documentary_payloads=(forbidden_claim_text, forbidden_evidence_text),
)
signal_payload = signal.to_payload()
assert_equal(signal_payload["signal_name"], "evidence_governance_claim_metrics_published", "Le signal EG doit être nommé.")
assert_equal(signal_payload["metrics"]["claim_count"], 4, "Le signal doit reprendre les métriques EG.")
assert_false(forbidden_claim_text in repr(signal_payload), "Le signal ne doit pas contenir le claim complet.")
assert_false(forbidden_evidence_text in repr(signal_payload), "Le signal ne doit pas contenir la preuve complète.")
assert_false("canonical_proposition" in repr(signal_payload), "Le signal ne doit pas contenir la proposition canonique.")
assert_false("source_locator" in repr(signal_payload), "Le signal ne doit pas exposer le payload documentaire.")

assert_raises(
    "contenu documentaire interdit dans claim_refs",
    lambda: EvidenceGovernanceAuditSignal.from_metric_snapshot(
        audit_signal_id="EG-AUDIT-M006-T010-0002",
        trace_id="TRACE-M006-T010-0002",
        metric_snapshot=snapshot,
        claim_refs=(
            {
                "claim_id": "CLM-M006-T010-VERIFIED",
                "claim_version": 1,
                "status": "VERIFIED",
                "proposition_hash": "a" * 64,
                "evidence_ref_ids": ("EVS-M006-T010-A",),
                "dependency_group_ids": ("DEP-M006-T010-PRIMARY",),
                "canonical_proposition": forbidden_claim_text,
            },
        ),
        forbidden_documentary_payloads=(forbidden_claim_text, forbidden_evidence_text),
    ),
)

assert_raises(
    "payload documentaire interdit dans signal d'audit",
    lambda: assert_no_documentary_payload_in_audit_payload(
        {"message": forbidden_evidence_text},
        forbidden_documentary_payloads=(forbidden_claim_text, forbidden_evidence_text),
    ),
)

print("Tests unitaires T-010 traçabilité et métriques M-006: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m006_traceability_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $env:PYTHONIOENCODING = "utf-8"
    $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

if ($LASTEXITCODE -ne 0) {
    throw ($output -join "`n")
}

Write-Host "Tests unitaires T-010 traçabilité et métriques M-006: OK"
