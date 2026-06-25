$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
from __future__ import annotations

import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.event_envelope import EventEnvelope
from app.platform.event_bus import (
    IdempotentEventConsumer,
    InMemoryProcessedEventRegistry,
    InMemoryTransactionalOutbox,
    OutboxMessageStatus,
    ProducerStateMutation,
)


def payload_for(event_id: str, aggregate_version: int) -> dict:
    return {
        "event_id": event_id,
        "event_type": "BoundaryContractVerified",
        "event_version": 1,
        "occurred_at": "2026-06-22T09:00:00Z",
        "aggregate_type": "BoundaryContract",
        "aggregate_id": "EVS-000001",
        "aggregate_version": aggregate_version,
        "correlation_id": "CORR-M002-OUTBOX-UNIT",
        "causation_id": "CMD-VERIFY-BOUNDARY-CONTRACT-000001",
        "producer_context": "KA",
        "payload": {
            "schema_version": "1.0",
            "contract_id": "BCON-000001",
            "verification_marker": f"version-{aggregate_version}",
        },
    }


def event_for(event_id: str, aggregate_version: int) -> EventEnvelope:
    return EventEnvelope.from_payload(payload_for(event_id, aggregate_version))


def mutation_for(event: EventEnvelope) -> ProducerStateMutation:
    return ProducerStateMutation(
        mutation_id=f"MUT-{event.aggregate_id}-V{event.aggregate_version}",
        producer_context=event.producer_context,
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        aggregate_version=event.aggregate_version,
    )


def assert_raises(expected_fragment: str, callback) -> None:
    try:
        callback()
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


event_v2 = event_for("EVT-M002-OUTBOX-0002", 2)
event_v1 = event_for("EVT-M002-OUTBOX-0001", 1)
event_v3 = event_for("EVT-M002-OUTBOX-0003", 3)

outbox = InMemoryTransactionalOutbox.empty()
entry_v2 = outbox.append_in_transaction(state_mutation=mutation_for(event_v2), event=event_v2)
entry_v1 = outbox.append_in_transaction(state_mutation=mutation_for(event_v1), event=event_v1)
entry_v3 = outbox.append_in_transaction(state_mutation=mutation_for(event_v3), event=event_v3)

if entry_v1.status is not OutboxMessageStatus.PENDING:
    raise AssertionError("Une entree outbox nouvelle doit etre pending.")
if outbox.status_of(event_v1.event_id) is not OutboxMessageStatus.PENDING:
    raise AssertionError("Le statut pending doit etre lisible par event_id.")
if tuple(entry.event.event_id for entry in outbox.pending_events()) != (
    "EVT-M002-OUTBOX-0001",
    "EVT-M002-OUTBOX-0002",
    "EVT-M002-OUTBOX-0003",
):
    raise AssertionError("Les evenements pending d'un agregat doivent suivre aggregate_version.")

outbox.mark_delivered(event_v1.event_id)
if outbox.status_of(event_v1.event_id) is not OutboxMessageStatus.DELIVERED:
    raise AssertionError("mark_delivered doit rendre le statut delivered observable.")
if tuple(entry.event.event_id for entry in outbox.pending_events()) != (
    "EVT-M002-OUTBOX-0002",
    "EVT-M002-OUTBOX-0003",
):
    raise AssertionError("Un evenement delivered ne doit plus etre pending.")

outbox.mark_failed(event_v2.event_id, "consumer unavailable")
failed_entry = outbox.entry_for(event_v2.event_id)
if failed_entry.status is not OutboxMessageStatus.FAILED:
    raise AssertionError("mark_failed doit rendre le statut failed observable.")
if failed_entry.failure_reason != "consumer unavailable":
    raise AssertionError(f"La raison d'echec doit etre explicite: {failed_entry.failure_reason}")

assert_raises("event_id outbox duplique", lambda: outbox.append_in_transaction(mutation_for(event_v3), event_v3))
assert_raises("event outbox inconnu", lambda: outbox.mark_delivered("EVT-M002-OUTBOX-9999"))
assert_raises("raison d'echec vide", lambda: outbox.mark_failed(event_v3.event_id, ""))

mismatched_mutation = ProducerStateMutation(
    mutation_id="MUT-KA-MISMATCH",
    producer_context="KA",
    aggregate_type="BoundaryContract",
    aggregate_id="EVS-000001",
    aggregate_version=99,
)
assert_raises(
    "aggregate_version incoherente",
    lambda: InMemoryTransactionalOutbox.empty().append_in_transaction(
        state_mutation=mismatched_mutation,
        event=event_v1,
    ),
)
assert_raises(
    "event invalide",
    lambda: InMemoryTransactionalOutbox.empty().append_in_transaction(
        state_mutation=mutation_for(event_v1),
        event={"event_id": event_v1.event_id},
    ),
)

assert_raises(
    "producer_context vide",
    lambda: ProducerStateMutation(
        mutation_id="MUT-INVALID",
        producer_context="",
        aggregate_type="BoundaryContract",
        aggregate_id="EVS-000001",
        aggregate_version=1,
    ),
)
assert_raises(
    "aggregate_version invalide",
    lambda: ProducerStateMutation(
        mutation_id="MUT-INVALID",
        producer_context="KA",
        aggregate_type="BoundaryContract",
        aggregate_id="EVS-000001",
        aggregate_version=0,
    ),
)

registry = InMemoryProcessedEventRegistry.empty()
consumer = IdempotentEventConsumer(processed_events=registry)
handled_events = []

first_decision = consumer.consume(event=event_v1, handler=lambda event: handled_events.append(event.event_id))
second_decision = consumer.consume(event=event_v1, handler=lambda event: handled_events.append(event.event_id))

if not first_decision.applied or first_decision.duplicate:
    raise AssertionError(f"Premiere consommation invalide: {first_decision}")
if second_decision.applied or not second_decision.duplicate:
    raise AssertionError(f"Doublon non detecte: {second_decision}")
if handled_events != [event_v1.event_id]:
    raise AssertionError(f"Le handler ne doit etre appele qu'une seule fois: {handled_events}")
if registry.processed_event_ids() != (event_v1.event_id,):
    raise AssertionError(f"event_id traite absent: {registry.processed_event_ids()}")
if registry.duplicate_event_ids() != (event_v1.event_id,):
    raise AssertionError(f"event_id duplique absent: {registry.duplicate_event_ids()}")
assert_raises("event_id invalide", lambda: InMemoryProcessedEventRegistry.from_processed_event_ids(("EXP-000001",)))
assert_raises("event invalide", lambda: consumer.consume(event={"event_id": event_v1.event_id}, handler=lambda event: None))

print("Tests unitaires outbox idempotente M-002: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m002_outbox_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires outbox idempotente M-002: OK"
