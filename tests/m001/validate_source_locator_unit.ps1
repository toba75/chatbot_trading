$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.source_references import (
    CanonicalSourceRef,
    SourceLocator,
    SourceLocatorValidationPolicy,
)


def assert_raises(expected_fragment, action):
    try:
        action()
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


canonical_payload = {
    "schema_version": "1.0",
    "canonical_source_id": "CSRC-000001",
    "document_id": "DOC-000001",
    "canonical_version_id": "CVER-000004",
    "source_sha256": "a" * 64,
    "canonical_artifact_sha256": "b" * 64,
    "page_count": 2,
    "accepted_at": "2026-06-21T08:30:00Z",
    "quality_policy_version": "source-qa-v3",
}
locator_payload = {
    "schema_version": "1.0",
    "canonical_version_id": "CVER-000004",
    "document_id": "DOC-000001",
    "page_pdf": 2,
    "item_id": "DOC-000001-P002-I001",
    "bbox": [0.1, 0.2, 0.8, 0.4],
    "content_hash": "c" * 64,
}

canonical_ref = CanonicalSourceRef.from_payload(canonical_payload)
validation_policy = SourceLocatorValidationPolicy(
    canonical_sources_by_version_id={canonical_ref.canonical_version_id: canonical_ref},
    version_statuses_by_version_id={canonical_ref.canonical_version_id: "ACCEPTED"},
    resolvable_item_ids_by_version_id={
        canonical_ref.canonical_version_id: frozenset({"DOC-000001-P002-I001"}),
    },
)

valid_locator = SourceLocator.from_payload(locator_payload, validation_policy=validation_policy)
if SourceLocator.from_json(valid_locator.to_json(), validation_policy=validation_policy) != valid_locator:
    raise AssertionError("Le round-trip unitaire SourceLocator doit rester stable.")

class OneShotItemIds:
    def __init__(self, values):
        self._values = list(values)
        self._used = False

    def __iter__(self):
        if self._used:
            return iter(())
        self._used = True
        return iter(self._values)


one_shot_policy = SourceLocatorValidationPolicy(
    canonical_sources_by_version_id={canonical_ref.canonical_version_id: canonical_ref},
    version_statuses_by_version_id={canonical_ref.canonical_version_id: "ACCEPTED"},
    resolvable_item_ids_by_version_id={
        canonical_ref.canonical_version_id: OneShotItemIds(["DOC-000001-P002-I001"]),
    },
)
SourceLocator.from_payload(locator_payload, validation_policy=one_shot_policy)

assert_raises(
    "validation_policy invalide",
    lambda: SourceLocator.from_payload(locator_payload, validation_policy=None),
)

impossible_accepted_at = dict(canonical_payload)
impossible_accepted_at["accepted_at"] = "2026-02-30T08:30:00Z"
assert_raises(
    "accepted_at invalide",
    lambda: CanonicalSourceRef.from_payload(impossible_accepted_at),
)

internal_source_key = dict(locator_payload)
internal_source_key["sp_table"] = "source_processing.canonical_sources"
assert_raises(
    "cle interdite",
    lambda: SourceLocator.from_payload(internal_source_key, validation_policy=validation_policy),
)

nan_bbox = dict(locator_payload)
nan_bbox["bbox"] = [0.1, float("nan"), 0.8, 0.4]
assert_raises(
    "bbox invalide",
    lambda: SourceLocator.from_payload(nan_bbox, validation_policy=validation_policy),
)

unsupported_schema = dict(locator_payload)
unsupported_schema["schema_version"] = "2.0"
assert_raises(
    "schema_version non supportee",
    lambda: SourceLocator.from_payload(unsupported_schema, validation_policy=validation_policy),
)

missing_canonical_version = dict(locator_payload)
del missing_canonical_version["canonical_version_id"]
assert_raises(
    "canonical_version_id absent",
    lambda: SourceLocator.from_payload(missing_canonical_version, validation_policy=validation_policy),
)

document_only_payload = dict(locator_payload)
del document_only_payload["canonical_version_id"]
assert_raises(
    "canonical_version_id absent",
    lambda: SourceLocator.from_payload(document_only_payload, validation_policy=validation_policy),
)

empty_required_fields = {
    "canonical_version_id": "canonical_version_id vide",
    "document_id": "document_id vide",
    "item_id": "item_id vide",
    "content_hash": "content_hash vide",
}
for field_name, expected_error in empty_required_fields.items():
    invalid_payload = dict(locator_payload)
    invalid_payload[field_name] = ""
    assert_raises(
        expected_error,
        lambda invalid_payload=invalid_payload: SourceLocator.from_payload(
            invalid_payload,
            validation_policy=validation_policy,
        ),
    )

invalid_page_zero = dict(locator_payload)
invalid_page_zero["page_pdf"] = 0
assert_raises(
    "page_pdf invalide",
    lambda: SourceLocator.from_payload(invalid_page_zero, validation_policy=validation_policy),
)

invalid_page_outside_version = dict(locator_payload)
invalid_page_outside_version["page_pdf"] = 3
assert_raises(
    "page_pdf hors version canonique",
    lambda: SourceLocator.from_payload(invalid_page_outside_version, validation_policy=validation_policy),
)

invalid_item = dict(locator_payload)
invalid_item["item_id"] = "DOC-000001-P002-I999"
assert_raises(
    "item_id non resolvable",
    lambda: SourceLocator.from_payload(invalid_item, validation_policy=validation_policy),
)

invalid_hash = dict(locator_payload)
invalid_hash["content_hash"] = ""
assert_raises(
    "content_hash vide",
    lambda: SourceLocator.from_payload(invalid_hash, validation_policy=validation_policy),
)

wrong_document = dict(locator_payload)
wrong_document["document_id"] = "DOC-999999"
assert_raises(
    "document_id incoherent avec CanonicalSourceRef",
    lambda: SourceLocator.from_payload(wrong_document, validation_policy=validation_policy),
)

quarantined_policy = SourceLocatorValidationPolicy(
    canonical_sources_by_version_id={canonical_ref.canonical_version_id: canonical_ref},
    version_statuses_by_version_id={canonical_ref.canonical_version_id: "QUARANTINED"},
    resolvable_item_ids_by_version_id={
        canonical_ref.canonical_version_id: frozenset({"DOC-000001-P002-I001"}),
    },
)
assert_raises(
    "Version canonique indisponible: QUARANTINED",
    lambda: SourceLocator.from_payload(locator_payload, validation_policy=quarantined_policy),
)

retired_policy = SourceLocatorValidationPolicy(
    canonical_sources_by_version_id={canonical_ref.canonical_version_id: canonical_ref},
    version_statuses_by_version_id={canonical_ref.canonical_version_id: "RETIRED"},
    resolvable_item_ids_by_version_id={
        canonical_ref.canonical_version_id: frozenset({"DOC-000001-P002-I001"}),
    },
)
assert_raises(
    "Version canonique indisponible: RETIRED",
    lambda: SourceLocator.from_payload(locator_payload, validation_policy=retired_policy),
)

print("Invariants unitaires SourceLocator M-001: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m001_source_locator_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires SourceLocator M-001: OK"
