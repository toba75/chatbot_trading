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


def canonical_source_published_payload() -> dict:
    return {
        "event_id": "EVT-M002-OUTBOX-0001",
        "event_type": "CanonicalSourcePublished",
        "event_version": 1,
        "occurred_at": "2026-06-21T08:30:00Z",
        "aggregate_type": "CanonicalSource",
        "aggregate_id": "CSRC-000001",
        "aggregate_version": 4,
        "correlation_id": "CORR-M002-OUTBOX-0001",
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


class ProjectionConsumerDouble:
    def __init__(self):
        self.transitions = []

    def apply(self, event: EventEnvelope) -> None:
        self.transitions.append(
            {
                "event_id": event.event_id,
                "aggregate_id": event.aggregate_id,
                "aggregate_version": event.aggregate_version,
            }
        )


# Given un contexte publie un evenement intercontexte dans la meme transaction que son etat.
event = EventEnvelope.from_payload(canonical_source_published_payload())
state_mutation = ProducerStateMutation(
    mutation_id="MUT-SP-CSRC-000001-V4",
    producer_context="SP",
    aggregate_type="CanonicalSource",
    aggregate_id="CSRC-000001",
    aggregate_version=4,
)
outbox = InMemoryTransactionalOutbox.empty()
entry = outbox.append_in_transaction(state_mutation=state_mutation, event=event)

if entry.status is not OutboxMessageStatus.PENDING:
    raise AssertionError("L'evenement ecrit dans l'outbox doit demarrer en pending.")
if outbox.recorded_state_mutations() != (state_mutation,):
    raise AssertionError("La mutation productrice doit etre enregistree avec l'evenement.")
if outbox.pending_events() != (entry,):
    raise AssertionError("L'evenement outbox doit etre livrable apres la transaction locale.")

# When le meme evenement est livre deux fois au consommateur.
projection = ProjectionConsumerDouble()
registry = InMemoryProcessedEventRegistry.empty()
consumer = IdempotentEventConsumer(processed_events=registry)

first_decision = consumer.consume(event=entry.event, handler=projection.apply)
second_decision = consumer.consume(event=entry.event, handler=projection.apply)
outbox.mark_delivered(entry.event.event_id)

# Then le consommateur applique la decision une seule fois et enregistre le doublon.
if not first_decision.applied or first_decision.duplicate:
    raise AssertionError(f"Premiere livraison invalide: {first_decision}")
if second_decision.applied or not second_decision.duplicate:
    raise AssertionError(f"Livraison dupliquee invalide: {second_decision}")
if projection.transitions != [
    {
        "event_id": "EVT-M002-OUTBOX-0001",
        "aggregate_id": "CSRC-000001",
        "aggregate_version": 4,
    }
]:
    raise AssertionError(f"Le doublon ne doit pas creer de seconde transition: {projection.transitions}")
if registry.processed_event_ids() != ("EVT-M002-OUTBOX-0001",):
    raise AssertionError(f"event_id traite non enregistre: {registry.processed_event_ids()}")
if registry.duplicate_event_ids() != ("EVT-M002-OUTBOX-0001",):
    raise AssertionError(f"Doublon non enregistre explicitement: {registry.duplicate_event_ids()}")
if outbox.status_of("EVT-M002-OUTBOX-0001") is not OutboxMessageStatus.DELIVERED:
    raise AssertionError("La livraison outbox doit etre marquee delivered explicitement.")

print("Test d'acceptation outbox idempotente M-002: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m002_outbox_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation outbox idempotente M-002: OK"
