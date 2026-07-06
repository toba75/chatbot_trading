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

from app.contracts.source_references import (
    ACCEPTED_CANONICAL_VERSION_STATUS,
    CanonicalSourceRef,
    SourceLocator,
    SourceLocatorValidationPolicy,
    SUPERSEDED_CANONICAL_VERSION_STATUS,
)
from app.evaluation.domain.verified_answer_benchmark import (
    ANSWER_ACCURACY_SCORE,
    ANSWER_CITATION_PRECISION,
    ANSWER_COMPLETENESS_SCORE,
    ANSWER_CONTRADICTION_MANAGEMENT_RATE,
    ANSWER_CORRECT_ABSTENTION_RATE,
    ANSWER_FIDELITY_SCORE,
    ANSWER_INVENTED_PARAMETER_REJECTION_RATE,
    ANSWER_OBSOLETE_VERSION_REUSE_RATE,
    ANSWER_RESEARCH_OBLIGATION_COVERAGE,
    ANSWER_SOURCE_DEDUCTION_DISTINCTION_RATE,
    ANSWER_UNSUPPORTED_ASSERTION_REMOVED_TOTAL,
    CONFLICTING_EVIDENCE,
    EG_CLAIM_REJECTED_RATE,
    EG_CLAIM_REVIEW_RATE,
    EG_CLAIM_VERIFIED_RATE,
    EG_UNSUPPORTED_ASSERTION_RATIO,
    EG_SUPERSESSION_RATE,
    EG_VERIFICATION_DELAY_SECONDS,
    INSUFFICIENT_EVIDENCE,
    PARTIALLY_SUPPORTED,
    SUPPORTED,
    AnswerAssertionMeasurement,
    AnswerEvaluationCase,
    CitationMeasurement,
    EvidenceClaimMeasurement,
    EvidenceGovernanceBenchmark,
    ResearchObligationMeasurement,
    VerifiedAnswerBenchmark,
)

HASH = "e" * 64
POLICY_VERSION = "EvidenceAnswerBenchmarkPolicy-1.0"


def source_policy():
    accepted = CanonicalSourceRef.from_payload(
        {
            "schema_version": "1.0",
            "canonical_source_id": "CSRC-M012-T008-ACCEPTED",
            "document_id": "DOC-M012-T008",
            "canonical_version_id": "CVER-M012-T008-ACCEPTED",
            "source_sha256": HASH,
            "canonical_artifact_sha256": HASH,
            "page_count": 4,
            "accepted_at": "2026-07-06T00:00:00Z",
            "quality_policy_version": "DocumentQualityCalibrationPolicy-1.0",
        }
    )
    superseded = CanonicalSourceRef.from_payload(
        {
            "schema_version": "1.0",
            "canonical_source_id": "CSRC-M012-T008-OLD",
            "document_id": "DOC-M012-T008",
            "canonical_version_id": "CVER-M012-T008-OLD",
            "source_sha256": HASH,
            "canonical_artifact_sha256": HASH,
            "page_count": 4,
            "accepted_at": "2026-07-05T00:00:00Z",
            "quality_policy_version": "DocumentQualityCalibrationPolicy-1.0",
        }
    )
    return SourceLocatorValidationPolicy(
        canonical_sources_by_version_id={
            "CVER-M012-T008-ACCEPTED": accepted,
            "CVER-M012-T008-OLD": superseded,
        },
        version_statuses_by_version_id={
            "CVER-M012-T008-ACCEPTED": ACCEPTED_CANONICAL_VERSION_STATUS,
            "CVER-M012-T008-OLD": SUPERSEDED_CANONICAL_VERSION_STATUS,
        },
        resolvable_item_ids_by_version_id={
            "CVER-M012-T008-ACCEPTED": {
                "ITEM-M012-T008-1": HASH,
                "ITEM-M012-T008-2": HASH,
                "ITEM-M012-T008-3": HASH,
            },
            "CVER-M012-T008-OLD": {
                "ITEM-M012-T008-OLD": HASH,
            },
        },
    )


SOURCE_POLICY = source_policy()


def locator(item_id="ITEM-M012-T008-1", version_id="CVER-M012-T008-ACCEPTED"):
    return SourceLocator.from_payload(
        {
            "schema_version": "1.0",
            "canonical_version_id": version_id,
            "document_id": "DOC-M012-T008",
            "page_pdf": 1,
            "item_id": item_id,
            "bbox": [0.1, 0.1, 0.2, 0.2],
            "content_hash": HASH,
        },
        validation_policy=SOURCE_POLICY,
    )


def citation(index, *, resolved=True, version_id="CVER-M012-T008-ACCEPTED"):
    return CitationMeasurement(
        citation_id=f"CIT-M012-T008-{index}",
        source_locator=locator(f"ITEM-M012-T008-{index}", version_id) if resolved else None,
        resolved=resolved,
    )


def assertion(index, **overrides):
    payload = {
        "assertion_id": f"AST-M012-T008-{index}",
        "expected_supported": True,
        "observed_supported": True,
        "faithful_to_evidence": True,
        "source_deduction_distinguished": True,
        "removed_because_unsupported": False,
        "invented_parameter_detected": False,
        "invented_parameter_rejected": False,
    }
    payload.update(overrides)
    return AnswerAssertionMeasurement(**payload)


def obligation(index, covered=True):
    return ResearchObligationMeasurement(
        obligation_id=f"OBL-M012-T008-{index}",
        topic=f"obligation-{index}",
        covered=covered,
    )


def answer_case(case_id, support_status, **overrides):
    payload = {
        "case_id": case_id,
        "question": f"Question pilote {case_id}.",
        "expected_support_status": support_status,
        "support_status": support_status,
        "citations": (citation(1),),
        "assertions": (assertion(1),),
        "research_obligations": (obligation(1),),
        "expected_abstention": False,
        "abstained": False,
        "contradiction_expected": False,
        "contradiction_handled": False,
        "reused_obsolete_version": False,
        "raw_conversation_evidence_used": False,
    }
    payload.update(overrides)
    return AnswerEvaluationCase(**payload)


# Given des questions d'évaluation avec preuves, contradictions ou insuffisances attendues.
answer_cases = (
    answer_case(
        "CASE-M012-T008-SUPPORTED",
        SUPPORTED,
        citations=(citation(1), citation(2)),
        assertions=(assertion(1), assertion(2)),
        research_obligations=(obligation(1), obligation(2)),
    ),
    answer_case(
        "CASE-M012-T008-PARTIAL",
        PARTIALLY_SUPPORTED,
        citations=(citation(1), CitationMeasurement("CIT-M012-T008-BROKEN", None, False)),
        assertions=(
            assertion(3),
            assertion(
                4,
                expected_supported=False,
                observed_supported=False,
                faithful_to_evidence=False,
                removed_because_unsupported=True,
                invented_parameter_detected=True,
                invented_parameter_rejected=True,
            ),
        ),
        research_obligations=(obligation(3), obligation(4, covered=False)),
        reused_obsolete_version=True,
    ),
    answer_case(
        "CASE-M012-T008-ABSTENTION",
        INSUFFICIENT_EVIDENCE,
        citations=(),
        assertions=(),
        research_obligations=(obligation(5, covered=False),),
        expected_abstention=True,
        abstained=True,
    ),
    answer_case(
        "CASE-M012-T008-CONFLICT",
        CONFLICTING_EVIDENCE,
        citations=(citation(3),),
        assertions=(assertion(5),),
        research_obligations=(obligation(6),),
        contradiction_expected=True,
        contradiction_handled=True,
    ),
)

# When RA produit des réponses vérifiées et abstinentes sur le corpus pilote.
answer_run = VerifiedAnswerBenchmark(policy_version=POLICY_VERSION).measure(
    run_id="VARUN-M012-T008",
    evaluation_cases=answer_cases,
)

# Then chaque statut RA, citation, obligation, abstention et limite reste mesurable.
assert answer_run.case_count == 4
assert set(answer_run.support_status_rates.keys()) == {
    SUPPORTED,
    PARTIALLY_SUPPORTED,
    INSUFFICIENT_EVIDENCE,
    CONFLICTING_EVIDENCE,
}
assert answer_run.support_status_rates[SUPPORTED].value == "0.250000000000"
assert answer_run.support_status_rates[PARTIALLY_SUPPORTED].value == "0.250000000000"
assert answer_run.support_status_rates[INSUFFICIENT_EVIDENCE].value == "0.250000000000"
assert answer_run.support_status_rates[CONFLICTING_EVIDENCE].value == "0.250000000000"
assert answer_run.metrics[ANSWER_CITATION_PRECISION].value == "0.800000000000"
assert answer_run.metrics[ANSWER_CITATION_PRECISION].denominator == 5
assert answer_run.metrics[ANSWER_UNSUPPORTED_ASSERTION_REMOVED_TOTAL].numerator == 1
assert answer_run.metrics[ANSWER_RESEARCH_OBLIGATION_COVERAGE].value == "0.666666666667"
assert answer_run.metrics[ANSWER_OBSOLETE_VERSION_REUSE_RATE].value == "0.250000000000"
assert answer_run.metrics[ANSWER_CORRECT_ABSTENTION_RATE].value == "1.000000000000"
assert answer_run.metrics[ANSWER_CONTRADICTION_MANAGEMENT_RATE].value == "1.000000000000"
assert answer_run.metrics[ANSWER_INVENTED_PARAMETER_REJECTION_RATE].value == "1.000000000000"
assert answer_run.metrics[ANSWER_SOURCE_DEDUCTION_DISTINCTION_RATE].value == "1.000000000000"
assert answer_run.metrics[ANSWER_ACCURACY_SCORE].value == "0.800000000000"
assert answer_run.metrics[ANSWER_FIDELITY_SCORE].value == "0.800000000000"
assert answer_run.metrics[ANSWER_COMPLETENESS_SCORE].value == "0.666666666667"
assert answer_run.case_results[1].citation_failure_count == 1
assert answer_run.case_results[1].unsupported_assertion_removed_count == 1
assert answer_run.case_results[1].reused_obsolete_version

# Given EG publie les états de claims associés au corpus pilote.
claim_measurements = (
    EvidenceClaimMeasurement(
        claim_id="CLM-M012-T008-VERIFIED",
        claim_version=1,
        subject="liquidité",
        status="VERIFIED",
        verdict="ENTAILED",
        has_direct_evidence=True,
        dependency_group_ids=("DEP-M012-T008-A", "DEP-M012-T008-B"),
        superseded=False,
        submitted_at="2026-07-06T08:00:00Z",
        decided_at="2026-07-06T08:05:00Z",
    ),
    EvidenceClaimMeasurement(
        claim_id="CLM-M012-T008-REJECTED",
        claim_version=1,
        subject="liquidité",
        status="REJECTED",
        verdict="NOT_ENTAILED",
        has_direct_evidence=False,
        dependency_group_ids=("DEP-M012-T008-A",),
        superseded=False,
        submitted_at="2026-07-06T08:00:00Z",
        decided_at="2026-07-06T08:10:00Z",
    ),
    EvidenceClaimMeasurement(
        claim_id="CLM-M012-T008-REVIEW",
        claim_version=1,
        subject="marge",
        status="IN_REVIEW",
        verdict="PARTIALLY_ENTAILED",
        has_direct_evidence=False,
        dependency_group_ids=("DEP-M012-T008-C",),
        superseded=False,
        submitted_at="2026-07-06T08:00:00Z",
        decided_at=None,
    ),
    EvidenceClaimMeasurement(
        claim_id="CLM-M012-T008-SUPERSEDED",
        claim_version=1,
        subject="marge",
        status="VERIFIED",
        verdict="ENTAILED",
        has_direct_evidence=True,
        dependency_group_ids=("DEP-M012-T008-D",),
        superseded=True,
        submitted_at="2026-07-06T08:00:00Z",
        decided_at="2026-07-06T08:20:00Z",
    ),
)

# When EG est mesuré depuis ses contrats publiés.
eg_run = EvidenceGovernanceBenchmark(policy_version=POLICY_VERSION).measure(
    run_id="EGRUN-M012-T008",
    claim_measurements=claim_measurements,
)

# Then claims, verdicts, preuves directes, groupes, supersession et délais sont publiés.
assert eg_run.claim_count == 4
assert eg_run.metrics[EG_CLAIM_VERIFIED_RATE].value == "0.500000000000"
assert eg_run.metrics[EG_CLAIM_REJECTED_RATE].value == "0.250000000000"
assert eg_run.metrics[EG_CLAIM_REVIEW_RATE].value == "0.250000000000"
assert eg_run.metrics[EG_UNSUPPORTED_ASSERTION_RATIO].value == "0.500000000000"
assert eg_run.metrics[EG_SUPERSESSION_RATE].value == "0.250000000000"
assert eg_run.metrics[EG_VERIFICATION_DELAY_SECONDS].value == "700.000000000000"
assert eg_run.verdict_distribution == {
    "ENTAILED": 2,
    "NOT_ENTAILED": 1,
    "PARTIALLY_ENTAILED": 1,
}
assert eg_run.dependency_group_count_by_subject == {"liquidité": 2, "marge": 2}

print("Test d'acceptation T-008 benchmark réponses vérifiées M-012: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m012_verified_answer_benchmark_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Test d'acceptation T-008 benchmark réponses vérifiées M-012 invalide. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
