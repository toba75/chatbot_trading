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
    SourceLocator,
    SourceLocatorValidationPolicy,
)
from app.knowledge_access.domain.chunking import (
    CanonicalChunkDocument,
    ChunkingProfile,
    HierarchicalChunkProjector,
    KnowledgeChunk,
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


def ref():
    return CanonicalSourceRef.from_payload(
        {
            "schema_version": "1.0",
            "canonical_source_id": "CSRC-M005-T004-UNIT",
            "document_id": "DOC-M005-T004-UNIT",
            "canonical_version_id": "CVER-M005-T004-UNIT-0001",
            "source_sha256": "3" * 64,
            "canonical_artifact_sha256": "4" * 64,
            "page_count": 3,
            "accepted_at": "2026-06-27T15:00:00Z",
            "quality_policy_version": "canonical-quality-m005-t004-unit-v1",
        }
    )


def locator_payload(canonical_ref, page_pdf, item_index, text):
    return {
        "schema_version": "1.0",
        "canonical_version_id": canonical_ref.canonical_version_id,
        "document_id": canonical_ref.document_id,
        "page_pdf": page_pdf,
        "item_id": f"{canonical_ref.document_id}-P{page_pdf:03d}-I{item_index:03d}",
        "bbox": [0.05, 0.08 * item_index, 0.95, 0.08 * item_index + 0.04],
        "content_hash": content_hash_for(text),
    }


def item_payload(canonical_ref, page_pdf, item_index, text):
    return {"text": text, "source_locator": locator_payload(canonical_ref, page_pdf, item_index, text)}


def policy_for(canonical_ref, items, status=ACCEPTED_CANONICAL_VERSION_STATUS):
    return SourceLocatorValidationPolicy(
        canonical_sources_by_version_id={canonical_ref.canonical_version_id: canonical_ref},
        version_statuses_by_version_id={canonical_ref.canonical_version_id: status},
        resolvable_item_ids_by_version_id={
            canonical_ref.canonical_version_id: {
                item["source_locator"]["item_id"]: item["source_locator"]["content_hash"]
                for item in items
                if "source_locator" in item
            }
        },
    )


def document_for(canonical_ref, items, status=ACCEPTED_CANONICAL_VERSION_STATUS):
    return CanonicalChunkDocument.from_payload(
        {
            "schema_version": "1.0",
            "canonical_ref": canonical_ref.to_payload(),
            "version_status": status,
            "items": tuple(items),
        },
        validation_policy=policy_for(canonical_ref, items, status=status),
    )


canonical_ref = ref()
items = (
    item_payload(canonical_ref, 1, 1, "Première règle de taille explicite."),
    item_payload(canonical_ref, 1, 2, "Deuxième règle de regroupement."),
    item_payload(canonical_ref, 2, 1, "Troisième item sur une autre page."),
    item_payload(canonical_ref, 3, 1, "Quatrième item de contexte parent."),
)

# ChunkingProfile est versionné et refuse les limites implicites.
profile = ChunkingProfile(
    profile_id="chunking-profile-m005-t004-unit",
    profile_version="hierarchical-v1",
    max_parent_items=3,
    max_child_items=2,
    max_child_characters=120,
)
assert_equal(profile.profile_id, "chunking-profile-m005-t004-unit", "Le profil doit conserver son identifiant.")
assert_equal(profile.profile_version, "hierarchical-v1", "Le profil doit conserver sa version.")
assert_raises(
    "max_child_items invalide",
    lambda: ChunkingProfile(
        profile_id="chunking-profile-invalid",
        profile_version="hierarchical-v1",
        max_parent_items=3,
        max_child_items=0,
        max_child_characters=120,
    ),
)
assert_raises(
    "max_child_characters invalide",
    lambda: ChunkingProfile(
        profile_id="chunking-profile-invalid",
        profile_version="hierarchical-v1",
        max_parent_items=3,
        max_child_items=1,
        max_child_characters=None,
    ),
)
assert_raises(
    "limites de profil incoherentes",
    lambda: ChunkingProfile(
        profile_id="chunking-profile-invalid",
        profile_version="hierarchical-v1",
        max_parent_items=1,
        max_child_items=2,
        max_child_characters=120,
    ),
)

# Le document canonique de chunking refuse les états partiels.
document = document_for(canonical_ref, items)
assert_equal(tuple(item.item_id for item in document.items), tuple(item["source_locator"]["item_id"] for item in items), "Les item_ids doivent venir des locators.")
assert_raises(
    "items canoniques absents",
    lambda: CanonicalChunkDocument.from_payload(
        {
            "schema_version": "1.0",
            "canonical_ref": canonical_ref.to_payload(),
            "version_status": ACCEPTED_CANONICAL_VERSION_STATUS,
            "items": (),
        },
        validation_policy=policy_for(canonical_ref, items),
    ),
)
duplicate_items = (items[0], items[0])
assert_raises(
    "item_id canonique duplique",
    lambda: document_for(canonical_ref, duplicate_items),
)
with_claim = dict(items[0])
with_claim["claim"] = "Le claim ne doit pas être stocké dans KA."
assert_raises(
    "claim interdit",
    lambda: document_for(canonical_ref, (with_claim,)),
)

# KnowledgeChunk impose source, parent et hash cohérent.
locator = SourceLocator.from_payload(items[0]["source_locator"], validation_policy=policy_for(canonical_ref, items))
chunk_text = items[0]["text"]
parent = KnowledgeChunk.parent(
    chunk_id="KCHK-M005-T004-PARENT",
    canonical_version_id=canonical_ref.canonical_version_id,
    document_id=canonical_ref.document_id,
    profile_id=profile.profile_id,
    profile_version=profile.profile_version,
    text=chunk_text,
    source_locators=(locator,),
)
assert_equal(parent.chunk_level, "PARENT", "Le chunk parent doit déclarer son niveau.")
assert_equal(parent.parent_chunk_id, None, "Le parent ne doit pas inventer de parent.")
assert_equal(parent.pages, (1,), "Les pages doivent venir des SourceLocator.")
assert_equal(parent.item_ids, (locator.item_id,), "Les item_ids doivent venir des SourceLocator.")
assert_equal(parent.content_hash, content_hash_for(chunk_text), "Le hash du parent doit venir du texte.")
assert_raises(
    "parent_chunk_id obligatoire",
    lambda: KnowledgeChunk.child(
        chunk_id="KCHK-M005-T004-CHILD",
        parent_chunk_id=None,
        canonical_version_id=canonical_ref.canonical_version_id,
        document_id=canonical_ref.document_id,
        profile_id=profile.profile_id,
        profile_version=profile.profile_version,
        text=chunk_text,
        source_locators=(locator,),
    ),
)
assert_raises(
    "source_locators absents",
    lambda: KnowledgeChunk.parent(
        chunk_id="KCHK-M005-T004-EMPTY",
        canonical_version_id=canonical_ref.canonical_version_id,
        document_id=canonical_ref.document_id,
        profile_id=profile.profile_id,
        profile_version=profile.profile_version,
        text=chunk_text,
        source_locators=(),
    ),
)
assert_raises(
    "content_hash incoherent",
    lambda: KnowledgeChunk(
        chunk_id="KCHK-M005-T004-BADHASH",
        chunk_level="PARENT",
        parent_chunk_id=None,
        canonical_version_id=canonical_ref.canonical_version_id,
        document_id=canonical_ref.document_id,
        profile_id=profile.profile_id,
        profile_version=profile.profile_version,
        text=chunk_text,
        pages=(1,),
        item_ids=(locator.item_id,),
        source_locators=(locator,),
        content_hash="f" * 64,
    ),
)

# HierarchicalChunkProjector conserve les parents, enfants, pages et limites explicites.
projection = HierarchicalChunkProjector().project(
    canonical_document=document,
    chunking_profile=profile,
)
parents = tuple(chunk for chunk in projection.chunks if chunk.chunk_level == "PARENT")
children = tuple(chunk for chunk in projection.chunks if chunk.chunk_level == "CHILD")
assert_equal(len(parents), 2, "Deux parents sont attendus avec max_parent_items=3.")
assert_equal(len(children), 3, "Trois enfants sont attendus avec max_child_items=2.")
assert_equal(parents[0].item_ids, tuple(item["source_locator"]["item_id"] for item in items[:3]), "Le premier parent doit regrouper les trois premiers items.")
assert_equal(children[0].parent_chunk_id, parents[0].chunk_id, "Le premier enfant doit référencer le premier parent.")
assert_equal(children[0].item_ids, tuple(item["source_locator"]["item_id"] for item in items[:2]), "Le premier enfant doit respecter max_child_items.")
assert_equal(children[1].item_ids, (items[2]["source_locator"]["item_id"],), "Le deuxième enfant doit porter l'item restant du parent.")
assert_true(all(len(child.text) <= profile.max_child_characters for child in children), "Les enfants doivent respecter la taille explicite.")
assert_true(all(chunk.source_locators for chunk in projection.chunks), "Aucun chunk ne doit être sans SourceLocator.")
assert_false(any("claim" in repr(chunk.to_payload()).lower() for chunk in projection.chunks), "Aucun chunk ne doit sérialiser de claim.")

too_long_item = (
    item_payload(canonical_ref, 1, 1, "X" * 130),
)
assert_raises(
    "item canonique depasse max_child_characters",
    lambda: HierarchicalChunkProjector().project(
        canonical_document=document_for(canonical_ref, too_long_item),
        chunking_profile=profile,
    ),
)

print("Tests unitaires T-004 chunking hiérarchique traçable M-005: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m005_hierarchical_chunking_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-004 chunking hiérarchique traçable M-005: OK"
