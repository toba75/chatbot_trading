$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$eventFixturePath = Join-Path $repoRoot "tests/fixtures/m001/contracts/sp_to_ka_canonical_source_published_event_v1.json"

if (-not (Test-Path -LiteralPath $eventFixturePath -PathType Leaf)) {
    throw "Fixture d'enveloppe d'événement absente: $eventFixturePath"
}

$pythonCode = @'
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])

from app.contracts.event_envelope import EventEnvelope, EventIdempotenceLedger


def load_payload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def assert_raises(expected_fragment, action):
    try:
        action()
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def assert_no_operational_messaging(payload):
    forbidden_keys = {
        "broker",
        "delivery_topic",
        "event_store",
        "job_id",
        "job_name",
        "outbox_id",
        "queue",
        "retry_policy",
    }

    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in forbidden_keys:
                raise AssertionError(f"Mecanisme operationnel hors perimetre expose: {key}")
            assert_no_operational_messaging(value)
    elif isinstance(payload, list):
        for item in payload:
            assert_no_operational_messaging(item)


event_payload = load_payload(sys.argv[2])

# Given SP publie un fait metier passe vers KA.
# When l'enveloppe d'événement est validée.
# Then le producteur, l'agregat, la causalite et l'idempotence sont explicites.
event = EventEnvelope.from_payload(event_payload)

if event.event_type != "CanonicalSourcePublished":
    raise AssertionError("Le type d'evenement publie doit etre conserve.")
if event.event_version != 1:
    raise AssertionError("La version d'evenement doit etre explicite.")
if event.producer_context != "SP":
    raise AssertionError("Le producteur SP doit etre explicite.")
if event.aggregate_type != "CanonicalSource" or event.aggregate_id != "CSRC-000001":
    raise AssertionError("L'agregat producteur doit etre conserve.")
if event.correlation_id != "CORR-000001" or event.causation_id != "CMD-ACCEPT-CANONICAL-SOURCE-000001":
    raise AssertionError("Correlation et causalite doivent etre conservees.")
if event.payload["canonical_version_id"] != "CVER-000004":
    raise AssertionError("Le payload publie doit rester accessible au consommateur.")

assert_no_operational_messaging(event_payload)

roundtrip_event = EventEnvelope.from_json(event.to_json())
if roundtrip_event != event:
    raise AssertionError("Le round-trip de l'enveloppe d'événement doit rester stable.")
if roundtrip_event.to_json() != event.to_json():
    raise AssertionError("La sérialisation de l'enveloppe d'événement doit être déterministe.")

ledger = EventIdempotenceLedger.from_processed_event_ids([])
first_decision = ledger.record(event)
if first_decision.already_processed:
    raise AssertionError("La premiere occurrence ne doit pas etre marquee comme doublon.")
if not first_decision.ledger.has_processed(event):
    raise AssertionError("event_id doit etre enregistre apres la premiere occurrence.")

second_decision = first_decision.ledger.record(event)
if not second_decision.already_processed:
    raise AssertionError("La seconde occurrence du même event_id doit être détectée.")
if second_decision.ledger != first_decision.ledger:
    raise AssertionError("La detection du doublon ne doit pas modifier l'etat de test.")

command_name = dict(event_payload)
command_name["event_type"] = "AcceptCanonicalSource"
assert_raises("fait passe", lambda: EventEnvelope.from_payload(command_name))

job_name = dict(event_payload)
job_name["event_type"] = "CONVERT_GRANITE"
assert_raises("job technique", lambda: EventEnvelope.from_payload(job_name))

without_producer = dict(event_payload)
del without_producer["producer_context"]
assert_raises("producer_context absent", lambda: EventEnvelope.from_payload(without_producer))

without_version = dict(event_payload)
del without_version["event_version"]
assert_raises("event_version absent", lambda: EventEnvelope.from_payload(without_version))

without_causality = dict(event_payload)
del without_causality["causation_id"]
assert_raises("causation_id absent", lambda: EventEnvelope.from_payload(without_causality))

print("Contrat d'enveloppe d'événement M-001 accepté.")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m001_event_envelope_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $output = & $pythonExecutable -B $pythonScriptPath $repoRoot $eventFixturePath 2>&1
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

if ($LASTEXITCODE -ne 0) {
    throw ($output -join "`n")
}

Write-Host "Test d'acceptation de l'enveloppe d'événement M-001: OK"
