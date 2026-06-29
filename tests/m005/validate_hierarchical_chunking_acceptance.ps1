$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import hashlib
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.source_references import (
    ACCEPTED_CANONICAL_VERSION_STATUS,
    CanonicalSourceRef,
    SourceLocatorValidationPolicy,
)
from app.knowledge_access.application.chunk_canonical_source import (
    ChunkingSourceNotFoundError,
    ProjectCanonicalChunksCommand,
    ProjectCanonicalChunksHandler,
)
from app.knowledge_access.domain.chunking import (
    CanonicalChunkDocument,
    ChunkingProfile,
    HierarchicalChunkProjector,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_false(condition, message):
    if condition:
        raise AssertionError(message)


def assert_raises(expected_fragment, action):
    try:
        action()
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def content_hash_for(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_ref():
    return CanonicalSourceRef.from_payload(
        {
            "schema_version": "1.0",
            "canonical_source_id": "CSRC-M005-T004-ACCEPTANCE",
            "document_id": "DOC-M005-T004-ACCEPTANCE",
            "canonical_version_id": "CVER-M005-T004-0001",
            "source_sha256": "1" * 64,
            "canonical_artifact_sha256": "2" * 64,
            "page_count": 2,
            "accepted_at": "2026-06-27T14:00:00Z",
            "quality_policy_version": "canonical-quality-m005-t004-v1",
        }
    )


def item_payload(ref, page_pdf, item_index, text):
    content_hash = content_hash_for(text)
    return {
        "text": text,
        "source_locator": {
            "schema_version": "1.0",
            "canonical_version_id": ref.canonical_version_id,
            "document_id": ref.document_id,
            "page_pdf": page_pdf,
            "item_id": f"{ref.document_id}-P{page_pdf:03d}-I{item_index:03d}",
            "bbox": [0.1, 0.1 * item_index, 0.9, 0.1 * item_index + 0.05],
            "content_hash": content_hash,
        },
    }


def validation_policy_for(ref, item_payloads, status=ACCEPTED_CANONICAL_VERSION_STATUS):
    return SourceLocatorValidationPolicy(
        canonical_sources_by_version_id={ref.canonical_version_id: ref},
        version_statuses_by_version_id={ref.canonical_version_id: status},
        resolvable_item_ids_by_version_id={
            ref.canonical_version_id: {
                item["source_locator"]["item_id"]: item["source_locator"]["content_hash"]
                for item in item_payloads
                if "source_locator" in item
            }
        },
    )


def canonical_document_payload(ref, items):
    return {
        "schema_version": "1.0",
        "canonical_ref": ref.to_payload(),
        "version_status": ACCEPTED_CANONICAL_VERSION_STATUS,
        "items": tuple(items),
    }


class RecordingCanonicalSourceReader:
    def __init__(self, records):
        self.records = dict(records)
        self.read_version_ids = []
        self.mutation_attempts = []

    def find_chunking_source_by_version_id(self, canonical_version_id):
        self.read_version_ids.append(canonical_version_id)
        return self.records.get(canonical_version_id)

    def mutate_source_processing(self, canonical_version_id):
        self.mutation_attempts.append(canonical_version_id)


# Given une version canonique publiée avec pages, items et hashes.
ref = canonical_ref()
items = (
    item_payload(ref, 1, 1, "Le risque par position reste borné."),
    item_payload(ref, 1, 2, "Le stop initial protège le capital."),
    item_payload(ref, 2, 1, "La convexité est recherchée par option."),
    item_payload(ref, 2, 2, "La sortie partielle réduit l'exposition."),
)
validation_policy = validation_policy_for(ref, items)
canonical_document = CanonicalChunkDocument.from_payload(
    canonical_document_payload(ref, items),
    validation_policy=validation_policy,
)
profile = ChunkingProfile(
    profile_id="chunking-profile-m005-t004",
    profile_version="hierarchical-v1",
    max_parent_items=3,
    max_child_items=2,
    max_child_characters=90,
)

# When KA applique un profil de chunking hiérarchique explicite.
reader = RecordingCanonicalSourceReader({ref.canonical_version_id: canonical_document})
handler = ProjectCanonicalChunksHandler(canonical_source_reader=reader)
projection = handler.project_from_canonical_version(
    ProjectCanonicalChunksCommand(
        canonical_version_id=ref.canonical_version_id,
        chunking_profile=profile,
    )
)

# Then chaque chunk porte pages, item ids, SourceLocator résolvable et content_hash cohérent.
assert_equal(reader.read_version_ids, [ref.canonical_version_id], "KA doit lire la version canonique demandée.")
assert_equal(reader.mutation_attempts, [], "KA ne doit pas muter SP pendant le chunking.")
assert_equal(projection.canonical_version_id, ref.canonical_version_id, "La projection doit viser la version canonique.")
assert_equal(projection.document_id, ref.document_id, "La projection doit conserver le document.")
assert_equal(projection.profile_id, profile.profile_id, "La projection doit conserver le profil.")
assert_equal(projection.profile_version, profile.profile_version, "La projection doit conserver la version de profil.")

parents = tuple(chunk for chunk in projection.chunks if chunk.chunk_level == "PARENT")
children = tuple(chunk for chunk in projection.chunks if chunk.chunk_level == "CHILD")
assert_equal(len(parents), 2, "Le découpage doit créer les parents hiérarchiques attendus.")
assert_equal(len(children), 3, "Le découpage doit créer les enfants attendus.")
assert_true(all(child.parent_chunk_id in {parent.chunk_id for parent in parents} for child in children), "Chaque enfant doit pointer vers un parent existant.")
assert_true(all(len(chunk.item_ids) > 0 for chunk in projection.chunks), "Aucun chunk ne doit être sans item source.")
assert_true(all(len(chunk.source_locators) == len(chunk.item_ids) for chunk in projection.chunks), "Chaque item doit conserver un SourceLocator.")
assert_true(all(chunk.content_hash == content_hash_for(chunk.text) for chunk in projection.chunks), "Chaque hash de chunk doit correspondre au texte projeté.")
assert_equal(children[0].pages, (1,), "Le premier enfant doit conserver la page source.")
assert_equal(children[1].pages, (2,), "Le deuxième enfant doit conserver la page source.")
assert_equal(parents[0].pages, (1, 2), "Le parent doit conserver l'ensemble des pages de ses enfants.")

for chunk in projection.chunks:
    for locator in chunk.source_locators:
        validation_policy.validate_locator(locator)
    assert_false(hasattr(chunk, "claim"), "Un chunk ne doit pas stocker de claim.")
    assert_false(hasattr(chunk, "verified_claim_id"), "Un chunk ne doit pas stocker de claim vérifié.")

public_payload = projection.to_payload()
serialized_projection = repr(public_payload)
assert_false("claim" in serialized_projection.lower(), "Le payload de chunking ne doit contenir aucun claim.")
assert_false("raw_text" in serialized_projection, "Le payload de chunking ne doit pas exposer de fallback texte brut.")

# Given un item canonique sans locator.
item_without_locator = {"text": "Texte sans provenance."}
assert_raises(
    "source_locator absent",
    lambda: CanonicalChunkDocument.from_payload(
        canonical_document_payload(ref, (item_without_locator,)),
        validation_policy=validation_policy,
    ),
)

# Given un texte dont le hash ne correspond pas au SourceLocator.
incoherent_item = dict(items[0])
incoherent_item["text"] = "Texte modifié sans nouvelle provenance."
assert_raises(
    "content_hash incoherent avec le texte",
    lambda: CanonicalChunkDocument.from_payload(
        canonical_document_payload(ref, (incoherent_item,)),
        validation_policy=validation_policy,
    ),
)

# Given un document canonique non publié.
not_published_payload = canonical_document_payload(ref, items)
not_published_payload["version_status"] = "SUPERSEDED"
assert_raises(
    "version canonique non publiee",
    lambda: CanonicalChunkDocument.from_payload(
        not_published_payload,
        validation_policy=validation_policy_for(ref, items, status="SUPERSEDED"),
    ),
)

# Given un payload contenant seulement du texte brut.
raw_text_payload = {
    "schema_version": "1.0",
    "canonical_ref": ref.to_payload(),
    "version_status": ACCEPTED_CANONICAL_VERSION_STATUS,
    "raw_text": "Fallback interdit.",
    "items": (),
}
assert_raises(
    "raw_text interdit",
    lambda: CanonicalChunkDocument.from_payload(
        raw_text_payload,
        validation_policy=validation_policy,
    ),
)

assert_raises(
    "source canonique introuvable",
    lambda: ProjectCanonicalChunksHandler(
        canonical_source_reader=RecordingCanonicalSourceReader({}),
    ).project_from_canonical_version(
        ProjectCanonicalChunksCommand(
            canonical_version_id=ref.canonical_version_id,
            chunking_profile=profile,
        )
    ),
)

print("Test d'acceptation T-004 chunking hiérarchique traçable M-005: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m005_hierarchical_chunking_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-004 chunking hiérarchique traçable M-005: OK"
