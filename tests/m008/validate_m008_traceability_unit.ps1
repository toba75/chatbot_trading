$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import math
import sys

sys.path.insert(0, sys.argv[1])

from app.conversation.application.traceability_metrics import (
    ConversationAuditSignal,
    ConversationMetricObservation,
    ConversationMetricsPublisher,
    assert_no_sensitive_payload_in_audit_payload,
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


forbidden_user_message = "Compare cette réponse avec Kelly et cite le passage complet."
forbidden_prompt = "Prompt interne CV avec instruction de routage cachée."
forbidden_document_text = "Passage documentaire complet sur le volatility targeting."

observations = (
    ConversationMetricObservation(
        trace_id="TRACE-M008-T011-CREATED",
        conversation_id="CONV-M008-T011-A",
        turn_id=None,
        event_type="ConversationCreated",
        mode=None,
        support_status=None,
        public_error_code=None,
        payload_hash="1" * 64,
        occurred_at="2026-07-01T18:00:00Z",
    ),
    ConversationMetricObservation(
        trace_id="TRACE-M008-T011-TURN",
        conversation_id="CONV-M008-T011-A",
        turn_id="TURN-M008-T011-A",
        event_type="UserTurnAppended",
        mode=None,
        support_status=None,
        public_error_code=None,
        payload_hash="2" * 64,
        occurred_at="2026-07-01T18:01:00Z",
    ),
    ConversationMetricObservation(
        trace_id="TRACE-M008-T011-RESOLVED",
        conversation_id="CONV-M008-T011-A",
        turn_id="TURN-M008-T011-A",
        event_type="FollowUpQuestionResolved",
        mode=None,
        support_status=None,
        public_error_code=None,
        payload_hash="3" * 64,
        occurred_at="2026-07-01T18:01:02Z",
    ),
    ConversationMetricObservation(
        trace_id="TRACE-M008-T011-CLARIFICATION",
        conversation_id="CONV-M008-T011-A",
        turn_id="TURN-M008-T011-B",
        event_type="FollowUpQuestionClarificationRequired",
        mode=None,
        support_status=None,
        public_error_code="FOLLOW_UP_AMBIGUOUS",
        payload_hash="4" * 64,
        occurred_at="2026-07-01T18:01:03Z",
    ),
    ConversationMetricObservation(
        trace_id="TRACE-M008-T011-MODE",
        conversation_id="CONV-M008-T011-A",
        turn_id="TURN-M008-T011-A",
        event_type="ConversationModeSelected",
        mode="CHAT_DOCUMENTAIRE",
        support_status=None,
        public_error_code=None,
        payload_hash="5" * 64,
        occurred_at="2026-07-01T18:01:04Z",
    ),
    ConversationMetricObservation(
        trace_id="TRACE-M008-T011-REVALIDATED",
        conversation_id="CONV-M008-T011-A",
        turn_id="TURN-M008-T011-A",
        event_type="HistoricalAssertionRevalidationRequested",
        mode=None,
        support_status=None,
        public_error_code=None,
        payload_hash="6" * 64,
        occurred_at="2026-07-01T18:01:05Z",
    ),
    ConversationMetricObservation(
        trace_id="TRACE-M008-T011-ATTACHED",
        conversation_id="CONV-M008-T011-A",
        turn_id="TURN-M008-T011-A",
        event_type="VerifiedAnswerAttachedToTurn",
        mode=None,
        support_status="SUPPORTED",
        public_error_code=None,
        payload_hash="7" * 64,
        occurred_at="2026-07-01T18:01:06Z",
    ),
    ConversationMetricObservation(
        trace_id="TRACE-M008-T011-PRESENTED",
        conversation_id="CONV-M008-T011-A",
        turn_id="TURN-M008-T011-A",
        event_type="ConversationPublicResponsePresented",
        mode=None,
        support_status="SUPPORTED",
        public_error_code=None,
        payload_hash="8" * 64,
        occurred_at="2026-07-01T18:01:07Z",
    ),
    ConversationMetricObservation(
        trace_id="TRACE-M008-T011-ARCHIVED",
        conversation_id="CONV-M008-T011-A",
        turn_id=None,
        event_type="ConversationArchived",
        mode=None,
        support_status=None,
        public_error_code=None,
        payload_hash="9" * 64,
        occurred_at="2026-07-01T18:02:00Z",
    ),
    ConversationMetricObservation(
        trace_id="TRACE-M008-T011-ERROR",
        conversation_id="CONV-M008-T011-A",
        turn_id=None,
        event_type="ConversationPublicError",
        mode=None,
        support_status=None,
        public_error_code="CONVERSATION_ARCHIVED",
        payload_hash="a" * 64,
        occurred_at="2026-07-01T18:02:01Z",
    ),
    ConversationMetricObservation(
        trace_id="TRACE-M008-T011-REJECTED",
        conversation_id="CONV-M008-T011-A",
        turn_id=None,
        event_type="ConversationPromptPayloadRejected",
        mode=None,
        support_status=None,
        public_error_code="HTTP_REQUEST_INVALID",
        payload_hash="b" * 64,
        occurred_at="2026-07-01T18:02:02Z",
    ),
)

# Given des observations CV agrégées sans messages complets.
# When les métriques de clôture M-008 sont calculées.
# Then les signaux de conversation, résolution, routage, rattachement et archive sont publiés sans contenu sensible.
snapshot = ConversationMetricsPublisher().publish(
    fixture_id="m008_conversation_metrics_fixture_v1",
    fixture_path="tests/m008/fixtures/m008_conversation_metrics_fixture.json",
    observations=observations,
    measured_at="2026-07-01T18:30:00Z",
)
payload = snapshot.to_payload()
assert_equal(payload["metric_scope"], "M008_PRODUCT_CONVERSATION", "La portée métrique doit nommer M-008.")
assert_equal(payload["observation_count"], 11, "Le nombre d'observations doit être publié.")
assert_equal(
    payload["normative_signals"],
    {
        "conversation_created_total": 1,
        "conversation_turn_appended_total": 1,
        "follow_up_question_resolved_total": 1,
        "conversation_mode_selected_total": 1,
        "historical_assertion_revalidated_total": 1,
        "verified_answer_attached_total": 1,
        "conversation_archived_total": 1,
        "conversation_public_error_total": 2,
        "conversation_prompt_payload_rejected_total": 1,
    },
    "Les signaux normatifs M-008 doivent être publiés explicitement.",
)
assert_equal(payload["mode_counts"], {"CHAT_DOCUMENTAIRE": 1}, "Les modes doivent être comptés.")
assert_equal(payload["support_status_counts"]["SUPPORTED"], 2, "Les statuts documentaires doivent être comptés.")
assert_equal(payload["clarification_required_total"], 1, "Les ambiguïtés doivent être mesurées explicitement.")
assert_equal(payload["public_error_code_counts"], {"CONVERSATION_ARCHIVED": 1, "FOLLOW_UP_AMBIGUOUS": 1, "HTTP_REQUEST_INVALID": 1}, "Les erreurs publiques doivent être comptées.")
assert_close(payload["archive_rate"], 1.0, "Le taux d'archive doit être calculé sur les conversations créées.")
assert_false(forbidden_user_message in repr(payload), "Les métriques ne doivent pas exposer le message utilisateur.")
assert_false(forbidden_prompt in repr(payload), "Les métriques ne doivent pas exposer le prompt.")
assert_false(forbidden_document_text in repr(payload), "Les métriques ne doivent pas exposer le texte documentaire.")
assert_false("answer_text" in repr(payload), "Les métriques ne doivent pas exposer la réponse complète.")

assert_raises(
    "mode requis",
    lambda: ConversationMetricObservation(
        trace_id="TRACE-M008-T011-BAD-MODE",
        conversation_id="CONV-M008-T011-A",
        turn_id="TURN-M008-T011-C",
        event_type="ConversationModeSelected",
        mode=None,
        support_status=None,
        public_error_code=None,
        payload_hash="c" * 64,
        occurred_at="2026-07-01T18:03:00Z",
    ),
)
assert_raises(
    "support_status requis",
    lambda: ConversationMetricObservation(
        trace_id="TRACE-M008-T011-BAD-ATTACH",
        conversation_id="CONV-M008-T011-A",
        turn_id="TURN-M008-T011-C",
        event_type="VerifiedAnswerAttachedToTurn",
        mode=None,
        support_status=None,
        public_error_code=None,
        payload_hash="d" * 64,
        occurred_at="2026-07-01T18:03:01Z",
    ),
)
assert_raises(
    "public_error_code requis",
    lambda: ConversationMetricObservation(
        trace_id="TRACE-M008-T011-BAD-ERROR",
        conversation_id="CONV-M008-T011-A",
        turn_id=None,
        event_type="ConversationPublicError",
        mode=None,
        support_status=None,
        public_error_code=None,
        payload_hash="e" * 64,
        occurred_at="2026-07-01T18:03:02Z",
    ),
)

signal = ConversationAuditSignal.from_metric_snapshot(
    audit_signal_id="CV-AUDIT-M008-T011-0001",
    trace_id="TRACE-M008-T011-AUDIT",
    metric_snapshot=snapshot,
    conversation_refs=(
        {
            "conversation_id": "CONV-M008-T011-A",
            "conversation_status": "ARCHIVED",
            "turn_count": 2,
            "last_turn_id": "TURN-M008-T011-B",
            "last_question_hash": "f" * 64,
        },
    ),
    forbidden_sensitive_payloads=(forbidden_user_message, forbidden_prompt, forbidden_document_text),
)
signal_payload = signal.to_payload()
assert_equal(signal_payload["signal_name"], "conversation_metrics_published", "Le signal CV doit être nommé.")
assert_equal(signal_payload["metric_scope"], "M008_PRODUCT_CONVERSATION", "La portée du signal doit nommer M-008.")
assert_false(forbidden_user_message in repr(signal_payload), "Le signal ne doit pas exposer le message utilisateur.")
assert_false(forbidden_prompt in repr(signal_payload), "Le signal ne doit pas exposer le prompt.")
assert_false(forbidden_document_text in repr(signal_payload), "Le signal ne doit pas exposer le document complet.")
assert_false("'message':" in repr(signal_payload), "Le signal ne doit pas contenir de message brut.")

assert_raises(
    "payload sensible interdit dans conversation_refs",
    lambda: ConversationAuditSignal.from_metric_snapshot(
        audit_signal_id="CV-AUDIT-M008-T011-LEAK",
        trace_id="TRACE-M008-T011-LEAK",
        metric_snapshot=snapshot,
        conversation_refs=(
            {
                "conversation_id": "CONV-M008-T011-A",
                "conversation_status": "ARCHIVED",
                "turn_count": 2,
                "last_turn_id": "TURN-M008-T011-B",
                "last_question_hash": "f" * 64,
                "message": forbidden_user_message,
            },
        ),
        forbidden_sensitive_payloads=(forbidden_user_message, forbidden_prompt, forbidden_document_text),
    ),
)
assert_raises(
    "payload sensible interdit dans signal d'audit",
    lambda: assert_no_sensitive_payload_in_audit_payload(
        {"prompt": forbidden_prompt},
        forbidden_sensitive_payloads=(forbidden_user_message, forbidden_prompt, forbidden_document_text),
    ),
)

print("Tests unitaires T-011 traçabilité et métriques M-008: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m008_traceability_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-011 traçabilité et métriques M-008: OK"
