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
)
from app.evaluation.domain.verified_answer_benchmark import (
    ANSWER_ACCURACY_SCORE,
    ANSWER_CITATION_PRECISION,
    ANSWER_CORRECT_ABSTENTION_RATE,
    ANSWER_INVENTED_PARAMETER_REJECTION_RATE,
    CONFLICTING_EVIDENCE,
    EG_CLAIM_VERIFIED_RATE,
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

POLICY_VERSION = "EvidenceAnswerBenchmarkPolicy-1.0"
HASH = "f" * 64


def source_policy():
    canonical_ref = CanonicalSourceRef.from_payload(
        {
            "schema_version": "1.0",
            "canonical_source_id": "CSRC-M012-T008-UNIT",
            "document_id": "DOC-M012-T008-UNIT",
            "canonical_version_id": "CVER-M012-T008-UNIT",
            "source_sha256": HASH,
            "canonical_artifact_sha256": HASH,
            "page_count": 3,
            "accepted_at": "2026-07-06T00:00:00Z",
            "quality_policy_version": "DocumentQualityCalibrationPolicy-1.0",
        }
    )
    return SourceLocatorValidationPolicy(
        canonical_sources_by_version_id={"CVER-M012-T008-UNIT": canonical_ref},
        version_statuses_by_version_id={"CVER-M012-T008-UNIT": ACCEPTED_CANONICAL_VERSION_STATUS},
        resolvable_item_ids_by_version_id={"CVER-M012-T008-UNIT": {"ITEM-M012-T008-UNIT": HASH}},
    )


SOURCE_POLICY = source_policy()


def locator():
    return SourceLocator.from_payload(
        {
            "schema_version": "1.0",
            "canonical_version_id": "CVER-M012-T008-UNIT",
            "document_id": "DOC-M012-T008-UNIT",
            "page_pdf": 1,
            "item_id": "ITEM-M012-T008-UNIT",
            "bbox": [0.1, 0.1, 0.2, 0.2],
            "content_hash": HASH,
        },
        validation_policy=SOURCE_POLICY,
    )


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


def citation(resolved=True):
    return CitationMeasurement(
        citation_id="CIT-M012-T008-UNIT",
        source_locator=locator() if resolved else None,
        resolved=resolved,
    )


def assertion(**overrides):
    payload = {
        "assertion_id": "AST-M012-T008-UNIT",
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


def obligation(covered=True):
    return ResearchObligationMeasurement(
        obligation_id="OBL-M012-T008-UNIT",
        topic="liquidité",
        covered=covered,
    )


def answer_case(**overrides):
    payload = {
        "case_id": "CASE-M012-T008-UNIT",
        "question": "Question unitaire.",
        "expected_support_status": SUPPORTED,
        "support_status": SUPPORTED,
        "citations": (citation(),),
        "assertions": (assertion(),),
        "research_obligations": (obligation(),),
        "expected_abstention": False,
        "abstained": False,
        "contradiction_expected": True,
        "contradiction_handled": True,
        "reused_obsolete_version": False,
        "raw_conversation_evidence_used": False,
    }
    payload.update(overrides)
    return AnswerEvaluationCase(**payload)


def full_answer_run(*cases):
    required_cases = (
        answer_case(case_id="CASE-M012-T008-U-SUPPORTED", support_status=SUPPORTED, expected_support_status=SUPPORTED),
        answer_case(
            case_id="CASE-M012-T008-U-PARTIAL",
            support_status=PARTIALLY_SUPPORTED,
            expected_support_status=PARTIALLY_SUPPORTED,
            assertions=(assertion(invented_parameter_detected=True, invented_parameter_rejected=True),),
        ),
        answer_case(
            case_id="CASE-M012-T008-U-INSUFFICIENT",
            support_status=INSUFFICIENT_EVIDENCE,
            expected_support_status=INSUFFICIENT_EVIDENCE,
            assertions=(),
            citations=(),
            expected_abstention=True,
            abstained=True,
            research_obligations=(obligation(False),),
        ),
        answer_case(
            case_id="CASE-M012-T008-U-CONFLICT",
            support_status=CONFLICTING_EVIDENCE,
            expected_support_status=CONFLICTING_EVIDENCE,
            contradiction_expected=True,
            contradiction_handled=True,
        ),
    )
    return VerifiedAnswerBenchmark(policy_version=POLICY_VERSION).measure(
        run_id="VARUN-M012-T008-UNIT",
        evaluation_cases=required_cases + tuple(cases),
    )


def claim(**overrides):
    payload = {
        "claim_id": "CLM-M012-T008-UNIT",
        "claim_version": 1,
        "subject": "liquidité",
        "status": "VERIFIED",
        "verdict": "ENTAILED",
        "has_direct_evidence": True,
        "dependency_group_ids": ("DEP-M012-T008-UNIT",),
        "superseded": False,
        "submitted_at": "2026-07-06T08:00:00Z",
        "decided_at": "2026-07-06T08:05:00Z",
    }
    payload.update(overrides)
    return EvidenceClaimMeasurement(**payload)


def eg_run(*claims):
    return EvidenceGovernanceBenchmark(policy_version=POLICY_VERSION).measure(
        run_id="EGRUN-M012-T008-UNIT",
        claim_measurements=claims,
    )


run = full_answer_run()
assert_equal(run.metrics[ANSWER_CITATION_PRECISION].denominator, 3, "Les citations doivent porter un dénominateur.")
assert_equal(run.metrics[ANSWER_CORRECT_ABSTENTION_RATE].value, "1.000000000000", "L'abstention correcte doit être comptée.")

unsupported_case = answer_case(
    case_id="CASE-M012-T008-U-UNSUPPORTED",
    support_status=PARTIALLY_SUPPORTED,
    expected_support_status=PARTIALLY_SUPPORTED,
    assertions=(assertion(expected_supported=False, observed_supported=False, faithful_to_evidence=False),),
)
unsupported_run = full_answer_run(unsupported_case)
assert_equal(unsupported_run.metrics[ANSWER_ACCURACY_SCORE].value, "0.750000000000", "Une assertion non supportée ne compte pas correcte.")

broken_citation_case = answer_case(
    case_id="CASE-M012-T008-U-CITATION",
    support_status=PARTIALLY_SUPPORTED,
    expected_support_status=PARTIALLY_SUPPORTED,
    citations=(citation(False),),
)
broken_citation_run = full_answer_run(broken_citation_case)
assert_equal(broken_citation_run.case_results[-1].citation_failure_count, 1, "Une citation non résoluble doit échouer.")

missing_abstention_case = answer_case(
    case_id="CASE-M012-T008-U-NO-ABSTENTION",
    support_status=INSUFFICIENT_EVIDENCE,
    expected_support_status=INSUFFICIENT_EVIDENCE,
    citations=(),
    assertions=(),
    expected_abstention=True,
    abstained=False,
)
missing_abstention_run = full_answer_run(missing_abstention_case)
assert_equal(missing_abstention_run.case_results[-1].failure_reasons, ("abstention attendue absente",), "Une abstention manquante doit rester visible.")

invented_parameter_case = answer_case(
    case_id="CASE-M012-T008-U-INVENTED",
    support_status=PARTIALLY_SUPPORTED,
    expected_support_status=PARTIALLY_SUPPORTED,
    assertions=(assertion(invented_parameter_detected=True, invented_parameter_rejected=False),),
)
invented_parameter_run = full_answer_run(invented_parameter_case)
assert_equal(invented_parameter_run.metrics[ANSWER_INVENTED_PARAMETER_REJECTION_RATE].value, "0.500000000000", "Un paramètre inventé non rejeté doit dégrader la métrique.")
assert_equal(invented_parameter_run.case_results[-1].failure_reasons, ("param\u00e8tre invent\u00e9 non rejet\u00e9",), "Le paramètre inventé doit être visible.")

assert_raises(
    "historique conversationnel brut interdit",
    lambda: answer_case(raw_conversation_evidence_used=True),
)
assert_raises(
    "statut documentaire invalide",
    lambda: answer_case(support_status="SUPPORTED_WITHOUT_DENOMINATOR"),
)
assert_raises(
    "source_locator requis pour citation r\u00e9solue",
    lambda: CitationMeasurement("CIT-M012-T008-BAD", None, True),
)
assert_raises(
    "SUPPORTED avec assertion non support\u00e9e",
    lambda: answer_case(assertions=(assertion(expected_supported=True, observed_supported=False),)),
)

eg = eg_run(
    claim(claim_id="CLM-M012-T008-UNIT-A", status="VERIFIED", has_direct_evidence=True, decided_at="2026-07-06T08:10:00Z"),
    claim(claim_id="CLM-M012-T008-UNIT-B", status="REJECTED", verdict="NOT_ENTAILED", has_direct_evidence=False, decided_at="2026-07-06T08:20:00Z"),
    claim(claim_id="CLM-M012-T008-UNIT-C", status="IN_REVIEW", verdict="PARTIALLY_ENTAILED", has_direct_evidence=False, decided_at=None),
)
assert_equal(eg.metrics[EG_CLAIM_VERIFIED_RATE].value, "0.333333333333", "Le taux VERIFIED doit être publié.")
assert_equal(eg.metrics[EG_VERIFICATION_DELAY_SECONDS].value, "900.000000000000", "Le délai moyen doit ignorer les claims encore en revue.")
assert_equal(eg.status_distribution, {"IN_REVIEW": 1, "REJECTED": 1, "VERIFIED": 1}, "La distribution de statuts doit être publiée.")

assert_raises(
    "preuve directe requise pour claim VERIFIED",
    lambda: claim(has_direct_evidence=False),
)
assert_raises(
    "d\u00e9nominateur m\u00e9trique invalide",
    lambda: EvidenceGovernanceBenchmark(policy_version=POLICY_VERSION).measure(
        run_id="EGRUN-M012-T008-EMPTY",
        claim_measurements=(),
    ),
)
assert_raises(
    "delai verification negatif",
    lambda: claim(decided_at="2026-07-06T07:59:00Z"),
)

print("Tests unitaires T-008 benchmark réponses vérifiées M-012: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m012_verified_answer_benchmark_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Tests unitaires T-008 benchmark réponses vérifiées M-012 invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
