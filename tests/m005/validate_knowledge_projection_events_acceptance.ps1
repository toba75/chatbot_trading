$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import json
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.event_envelope import EventEnvelope
from app.knowledge_access.application.projection_events import (
    KnowledgeProjectionEventFactory,
    append_projection_events_to_outbox,
)
from app.knowledge_access.domain.knowledge_projection import (
    BuildFingerprint,
    KnowledgeProjection,
    ProjectionProfile,
    ProjectionStatus,
)
from app.platform.event_bus import InMemoryTransactionalOutbox


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_false(condition, message):
    if condition:
        raise AssertionError(message)


def assert_raises(expected_exception, expected_fragment, action):
    try:
        action()
    except expected_exception as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
        return exc
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_exception.__name__}")


def projection(status=ProjectionStatus.BUILDING):
    return KnowledgeProjection(
        projection_id="PROJ-M005-T007-EVENTS",
        document_id="DOC-M005-T007-EVENTS",
        canonical_version_id="CVER-M005-T007-EVENTS-0001",
        projection_profile=ProjectionProfile(
            projection_profile_id="projection-profile-m005-t007-events",
            chunking_profile="chunking-profile-m005-t007-events",
            embedding_model="embedding-profile-m005-t007-events",
            sparse_profile="sparse-profile-m005-t007-events",
            index_schema="qdrant-index-schema-m005-t007-v1",
        ),
        build_fingerprint=BuildFingerprint("c" * 64),
        status=status,
    )


def assert_public_payload(event, expected_keys):
    payload = dict(event.payload)
    assert_equal(tuple(payload.keys()), tuple(expected_keys), f"Payload public inattendu pour {event.event_type}.")
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()
    for forbidden in ("claim", "verified_claim", "qdrant_id", "collection", "dense_vector", "sparse_weights", "text"):
        assert_false(forbidden in serialized, f"Payload privé interdit dans {event.event_type}: {forbidden}.")


factory = KnowledgeProjectionEventFactory(
    occurred_at="2026-06-28T11:00:00Z",
    correlation_id="CORR-M005-T007-EVENTS",
    causation_id="CMD-M005-T007-EVENTS",
)
base_projection = projection()
searchable_projection = base_projection.mark_built().start_indexing().mark_searchable()
failed_projection = base_projection.mark_failed()
stale_projection = searchable_projection.mark_stale()
retired_projection = stale_projection.retire()

# Les cinq événements KA doivent être des EventEnvelope valides et publiables.
built_event = factory.built(
    projection=base_projection.mark_built(),
    chunk_count=2,
)
searchable_event = factory.became_searchable(
    projection=searchable_projection,
    index_generation="IDX-M005-T007-EVENTS-0001",
    published_at="2026-06-28T11:01:00Z",
)
failed_event = factory.failed(
    projection=failed_projection,
    failed_step="INDEXING",
    public_error_code="INDEX_PARTIAL",
    retry_allowed=True,
)
stale_event = factory.became_stale(
    projection=stale_projection,
    stale_reason="CANONICAL_VERSION_SUPERSEDED",
    superseding_input_ref="CVER-M005-T007-EVENTS-0002",
)
retired_event = factory.retired(
    projection=retired_projection,
    retired_reason="PROJECTION_REPLACED",
)

events = (built_event, searchable_event, failed_event, stale_event, retired_event)
for event in events:
    assert_true(isinstance(event, EventEnvelope), f"{event.event_type} doit utiliser EventEnvelope.")
    assert_equal(event.producer_context, "KA", "Les événements de projection doivent être produits par KA.")
    assert_equal(event.aggregate_type, "KnowledgeProjection", "L'agrégat publié doit être KnowledgeProjection.")
    assert_equal(event.aggregate_id, base_projection.projection_id, "L'aggregate_id doit être la projection.")

assert_equal(
    tuple(event.event_type for event in events),
    (
        "KnowledgeProjectionBuilt",
        "KnowledgeProjectionBecameSearchable",
        "KnowledgeProjectionFailed",
        "KnowledgeProjectionBecameStale",
        "KnowledgeProjectionRetired",
    ),
    "Les types d'événements KA doivent être stables.",
)
assert_public_payload(
    built_event,
    ("projection_id", "canonical_version_id", "build_fingerprint", "chunk_count"),
)
assert_public_payload(
    searchable_event,
    ("projection_id", "canonical_version_id", "projection_profile_id", "index_generation", "published_at"),
)
assert_public_payload(
    failed_event,
    ("projection_id", "failed_step", "public_error_code", "retry_allowed"),
)
assert_public_payload(
    stale_event,
    ("projection_id", "stale_reason", "superseding_input_ref"),
)
assert_public_payload(
    retired_event,
    ("projection_id", "retired_reason"),
)

# L'outbox M-002 reçoit les événements avec mutation productrice et reste idempotente par event_id.
outbox = InMemoryTransactionalOutbox.empty()
first_entries = append_projection_events_to_outbox(outbox=outbox, events=events)
second_entries = append_projection_events_to_outbox(outbox=outbox, events=events)
assert_equal(len(first_entries), 5, "Les cinq événements doivent être écrits dans l'outbox.")
assert_equal(len(second_entries), 0, "Une réécriture identique ne doit pas dupliquer l'outbox.")
assert_equal(
    tuple(entry.event.event_type for entry in outbox.pending_events()),
    tuple(event.event_type for event in events),
    "L'outbox doit conserver l'ordre métier des événements.",
)
for entry in outbox.pending_events():
    assert_equal(entry.state_mutation.producer_context, "KA", "La mutation productrice doit appartenir à KA.")
    assert_equal(entry.state_mutation.aggregate_type, "KnowledgeProjection", "La mutation doit cibler la projection.")
    assert_equal(entry.state_mutation.aggregate_id, base_projection.projection_id, "La mutation doit cibler l'agrégat.")

# Les événements incomplets sont refusés plutôt que complétés par défaut.
assert_raises(
    ValueError,
    "chunk_count",
    lambda: factory.built(projection=base_projection.mark_built(), chunk_count=0),
)
assert_raises(
    ValueError,
    "public_error_code",
    lambda: factory.failed(
        projection=failed_projection,
        failed_step="INDEXING",
        public_error_code="",
        retry_allowed=True,
    ),
)

print("Test d'acceptation T-007 événements KnowledgeProjection M-005: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m005_knowledge_projection_events_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-007 événements KnowledgeProjection M-005: OK"
