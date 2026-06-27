$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$eAcute = [char] 0x00E9

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.event_envelope import (
    ALLOWED_EVENT_PRODUCER_CONTEXTS,
    EventEnvelope,
    EventIdempotenceLedger,
)


def assert_raises(expected_fragment, action):
    try:
        action()
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def valid_payload():
    return {
        "event_id": "EVT-000001",
        "event_type": "CanonicalSourcePublished",
        "event_version": 1,
        "occurred_at": "2026-06-21T08:30:00Z",
        "aggregate_type": "CanonicalSource",
        "aggregate_id": "CSRC-000001",
        "aggregate_version": 4,
        "correlation_id": "CORR-000001",
        "causation_id": "CMD-ACCEPT-CANONICAL-SOURCE-000001",
        "producer_context": "SP",
        "payload": {
            "schema_version": "1.0",
            "canonical_source_id": "CSRC-000001",
            "document_id": "DOC-000001",
            "canonical_version_id": "CVER-000004",
            "source_sha256": "a" * 64,
            "canonical_artifact_sha256": "b" * 64,
            "page_count": 2,
            "accepted_at": "2026-06-21T08:30:00Z",
            "quality_policy_version": "source-qa-v3",
        },
    }


event = EventEnvelope.from_payload(valid_payload())
if EventEnvelope.from_json(event.to_json()) != event:
    raise AssertionError("Le round-trip EventEnvelope doit rester stable.")
if EventEnvelope.from_json(event.to_json()).to_json() != event.to_json():
    raise AssertionError("La serialisation EventEnvelope doit etre deterministe.")

event_json = event.to_json()
try:
    event.payload["document_id"] = "DOC-999999"
except TypeError:
    pass
else:
    raise AssertionError("EventEnvelope.payload doit etre immuable apres validation.")
if event.to_json() != event_json:
    raise AssertionError("Une mutation externe ne doit pas modifier EventEnvelope.")

expected_contexts = {"SP", "KA", "EG", "RA", "CV", "SD", "EX"}
if ALLOWED_EVENT_PRODUCER_CONTEXTS != expected_contexts:
    raise AssertionError("Les producteurs autorises doivent rester les sept bounded contexts metier.")

for context in sorted(ALLOWED_EVENT_PRODUCER_CONTEXTS):
    payload = valid_payload()
    payload["producer_context"] = context
    if context != "SP":
        payload["event_type"] = "BoundaryContractVerified"
        payload["aggregate_type"] = "BoundaryContract"
        payload["aggregate_id"] = "EVS-000001"
        payload["payload"] = {"schema_version": "1.0", "event_marker": "verified"}
    EventEnvelope.from_payload(payload)

missing_event_id = valid_payload()
del missing_event_id["event_id"]
assert_raises("event_id absent", lambda: EventEnvelope.from_payload(missing_event_id))

invalid_event_id = valid_payload()
invalid_event_id["event_id"] = "EXP-000001"
assert_raises("event_id invalide", lambda: EventEnvelope.from_payload(invalid_event_id))

empty_event_type = valid_payload()
empty_event_type["event_type"] = ""
assert_raises("event_type vide", lambda: EventEnvelope.from_payload(empty_event_type))

not_past_event_type = valid_payload()
not_past_event_type["event_type"] = "CanonicalSourcePublish"
assert_raises("fait passe", lambda: EventEnvelope.from_payload(not_past_event_type))

command_event_type = valid_payload()
command_event_type["event_type"] = "AcceptCanonicalSource"
assert_raises("fait passe", lambda: EventEnvelope.from_payload(command_event_type))

job_event_type = valid_payload()
job_event_type["event_type"] = "CONVERT_GRANITE"
assert_raises("job technique", lambda: EventEnvelope.from_payload(job_event_type))

missing_event_version = valid_payload()
del missing_event_version["event_version"]
assert_raises("event_version absent", lambda: EventEnvelope.from_payload(missing_event_version))

invalid_event_version = valid_payload()
invalid_event_version["event_version"] = 0
assert_raises("event_version invalide", lambda: EventEnvelope.from_payload(invalid_event_version))

missing_occurred_at = valid_payload()
del missing_occurred_at["occurred_at"]
assert_raises("occurred_at absent", lambda: EventEnvelope.from_payload(missing_occurred_at))

invalid_occurred_at = valid_payload()
invalid_occurred_at["occurred_at"] = "2026-06-21 08:30:00"
assert_raises("occurred_at invalide", lambda: EventEnvelope.from_payload(invalid_occurred_at))

impossible_occurred_at = valid_payload()
impossible_occurred_at["occurred_at"] = "2026-02-30T08:30:00Z"
assert_raises("occurred_at invalide", lambda: EventEnvelope.from_payload(impossible_occurred_at))

missing_aggregate_type = valid_payload()
del missing_aggregate_type["aggregate_type"]
assert_raises("aggregate_type absent", lambda: EventEnvelope.from_payload(missing_aggregate_type))

missing_aggregate_id = valid_payload()
del missing_aggregate_id["aggregate_id"]
assert_raises("aggregate_id absent", lambda: EventEnvelope.from_payload(missing_aggregate_id))

invalid_aggregate_id = valid_payload()
invalid_aggregate_id["aggregate_id"] = "qdrant:source_processing:1"
assert_raises("aggregate_id invalide", lambda: EventEnvelope.from_payload(invalid_aggregate_id))

invalid_aggregate_version = valid_payload()
invalid_aggregate_version["aggregate_version"] = 0
assert_raises("aggregate_version invalide", lambda: EventEnvelope.from_payload(invalid_aggregate_version))

missing_correlation_id = valid_payload()
del missing_correlation_id["correlation_id"]
assert_raises("correlation_id absent", lambda: EventEnvelope.from_payload(missing_correlation_id))

invalid_correlation_id = valid_payload()
invalid_correlation_id["correlation_id"] = "EVT-000001"
assert_raises("correlation_id invalide", lambda: EventEnvelope.from_payload(invalid_correlation_id))

missing_causation_id = valid_payload()
del missing_causation_id["causation_id"]
assert_raises("causation_id absent", lambda: EventEnvelope.from_payload(missing_causation_id))

invalid_causation_id = valid_payload()
invalid_causation_id["causation_id"] = "CORR-000001"
assert_raises("causation_id invalide", lambda: EventEnvelope.from_payload(invalid_causation_id))

implicit_producer = valid_payload()
implicit_producer["producer_context"] = ""
assert_raises("producer_context vide", lambda: EventEnvelope.from_payload(implicit_producer))

unknown_producer = valid_payload()
unknown_producer["producer_context"] = "PLATFORM"
assert_raises("producer_context inconnu", lambda: EventEnvelope.from_payload(unknown_producer))

missing_payload = valid_payload()
del missing_payload["payload"]
assert_raises("payload absent", lambda: EventEnvelope.from_payload(missing_payload))

invalid_payload = valid_payload()
invalid_payload["payload"] = ["not", "an", "object"]
assert_raises("payload non objet", lambda: EventEnvelope.from_payload(invalid_payload))

payload_with_empty_value = valid_payload()
payload_with_empty_value["payload"] = {"schema_version": "1.0", "empty": ""}
assert_raises("payload invalide", lambda: EventEnvelope.from_payload(payload_with_empty_value))

payload_with_secret = valid_payload()
payload_with_secret["payload"] = {
    "schema_version": "1.0",
    "canonical_source_id": "CSRC-000001",
    "document_id": "DOC-000001",
    "canonical_version_id": "CVER-000004",
    "source_sha256": "a" * 64,
    "canonical_artifact_sha256": "b" * 64,
    "page_count": 2,
    "accepted_at": "2026-06-21T08:30:00Z",
    "quality_policy_version": "source-qa-v3",
    "api_key": "secret",
}
assert_raises("cle interdite", lambda: EventEnvelope.from_payload(payload_with_secret))

payload_with_access_token = valid_payload()
payload_with_access_token["event_type"] = "BoundaryContractVerified"
payload_with_access_token["aggregate_type"] = "BoundaryContract"
payload_with_access_token["aggregate_id"] = "EVS-000001"
payload_with_access_token["payload"] = {
    "schema_version": "1.0",
    "credentials": {
        "access_token": "secret",
    },
}
assert_raises("cle interdite", lambda: EventEnvelope.from_payload(payload_with_access_token))

payload_with_nan = valid_payload()
payload_with_nan["payload"] = {"schema_version": "1.0", "score": float("nan")}
assert_raises("payload invalide", lambda: EventEnvelope.from_payload(payload_with_nan))

incomplete_canonical_payload = valid_payload()
incomplete_canonical_payload["payload"] = {"schema_version": "1.0", "canonical_source_id": "CSRC-000001"}
assert_raises(
    "payload CanonicalSourcePublished invalide",
    lambda: EventEnvelope.from_payload(incomplete_canonical_payload),
)

inconsistent_canonical_payload = valid_payload()
inconsistent_canonical_payload["payload"] = {
    "schema_version": "1.0",
    "canonical_source_id": "CSRC-999999",
    "document_id": "DOC-000001",
    "canonical_version_id": "CVER-000004",
    "source_sha256": "a" * 64,
    "canonical_artifact_sha256": "b" * 64,
    "page_count": 2,
    "accepted_at": "2026-06-21T08:30:00Z",
    "quality_policy_version": "source-qa-v3",
}
assert_raises(
    "aggregate_id incoherent",
    lambda: EventEnvelope.from_payload(inconsistent_canonical_payload),
)

def valid_superseded_payload():
    payload = valid_payload()
    payload["event_id"] = "EVT-CANONICAL-SOURCE-SUPERSEDED-CVER-000005"
    payload["event_type"] = "CanonicalSourceSuperseded"
    payload["aggregate_type"] = "CanonicalSource"
    payload["aggregate_id"] = "CSRC-000001"
    payload["aggregate_version"] = 5
    payload["payload"] = {
        "schema_version": "1.0",
        "canonical_source_id": "CSRC-000001",
        "previous_canonical_version_id": "CVER-000004",
        "new_canonical_version_id": "CVER-000005",
    }
    return payload


EventEnvelope.from_payload(valid_superseded_payload())

missing_superseded_version = valid_superseded_payload()
del missing_superseded_version["payload"]["new_canonical_version_id"]
assert_raises(
    "payload CanonicalSourceSuperseded invalide",
    lambda: EventEnvelope.from_payload(missing_superseded_version),
)

inconsistent_superseded_payload = valid_superseded_payload()
inconsistent_superseded_payload["aggregate_id"] = "CSRC-999999"
assert_raises(
    "aggregate_id incoherent avec CanonicalSourceSuperseded",
    lambda: EventEnvelope.from_payload(inconsistent_superseded_payload),
)

same_version_superseded_payload = valid_superseded_payload()
same_version_superseded_payload["payload"]["new_canonical_version_id"] = "CVER-000004"
assert_raises(
    "versions identiques",
    lambda: EventEnvelope.from_payload(same_version_superseded_payload),
)

extra_superseded_field_payload = valid_superseded_payload()
extra_superseded_field_payload["payload"]["document_id"] = "DOC-000001"
assert_raises(
    "payload CanonicalSourceSuperseded invalide",
    lambda: EventEnvelope.from_payload(extra_superseded_field_payload),
)

ledger = EventIdempotenceLedger.from_processed_event_ids(["EVT-000099"])
if not ledger.has_processed("EVT-000099"):
    raise AssertionError("Le ledger de test doit reconnaitre un event_id deja traite.")
if ledger.has_processed(event):
    raise AssertionError("Le ledger de test ne doit pas inventer un doublon.")

first_decision = ledger.record(event)
if first_decision.already_processed:
    raise AssertionError("Un nouvel event_id ne doit pas etre signale comme doublon.")
if not first_decision.ledger.has_processed(event):
    raise AssertionError("Le nouvel event_id doit etre ajoute au ledger de test.")

second_decision_from_same_ledger = ledger.record(event)
if not second_decision_from_same_ledger.already_processed:
    raise AssertionError("Deux records depuis le meme ledger initial doivent detecter le doublon.")

duplicate_decision = first_decision.ledger.record(event)
if not duplicate_decision.already_processed:
    raise AssertionError("Le meme event_id doit etre signale comme doublon.")
if duplicate_decision.ledger != first_decision.ledger:
    raise AssertionError("Un doublon ne doit pas modifier le ledger de test.")

assert_raises(
    "event_id invalide",
    lambda: EventIdempotenceLedger.from_processed_event_ids(["EXP-000099"]),
)
assert_raises("event invalide", lambda: ledger.has_processed({"event_id": "EVT-000001"}))

print("Invariants unitaires EventEnvelope M-001: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m001_event_envelope_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

if ($LASTEXITCODE -ne 0) {
    throw ($output -join "`n")
}

Write-Host "Tests unitaires de l'enveloppe d'$($eAcute)v$($eAcute)nement M-001: OK"
