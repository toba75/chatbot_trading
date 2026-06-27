$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import hashlib
import sys

sys.path.insert(0, sys.argv[1])

from app.source_processing.domain.document_processing_run import (
    PageManifest,
    PageManifestEntry,
    PageManifestEntryState,
    PageNumber,
    PageRouteName,
)
from app.source_processing.domain.page_conversion import (
    ConversionToolName,
    PageConversionArtifact,
    PageConversionCandidate,
    PageConversionItem,
    PageConversionItemLabel,
    PageItemGeometry,
    PagewiseDoclingFusionService,
    TextAuthority,
    TextAuthorityManifest,
    TextAuthoritySelectionError,
    TextAuthoritySelectionPolicy,
)
from app.source_processing.domain.source_document import (
    BibliographicMetadata,
    DocumentId,
    OriginalStorageRef,
    SourceDocument,
    SourceFingerprint,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_raises_code(expected_code, action):
    try:
        action()
    except TextAuthoritySelectionError as exc:
        if exc.code != expected_code:
            raise AssertionError(f"Code métier inattendu: {exc.code!r}. Message: {exc}")
        if expected_code not in str(exc):
            raise AssertionError(f"Le message doit exposer le code métier {expected_code}. Message: {exc}")
    else:
        raise AssertionError(f"Erreur métier attendue absente: {expected_code}")


def registered_source():
    original_content = b"%PDF-1.7\ntext authority unit\n%%EOF\n"
    fingerprint = SourceFingerprint.from_content(original_content)
    document_id = DocumentId.from_fingerprint(fingerprint)
    storage_ref = OriginalStorageRef.from_value(
        f"artifact:source_processing.original_sources/{document_id.value}/{fingerprint.value}.pdf"
    )
    return SourceDocument.register_original(
        document_id=document_id,
        fingerprint=fingerprint,
        original_storage_ref=storage_ref,
        metadata=BibliographicMetadata.from_payload(
            {
                "title": "Autorité textuelle unitaire M-004",
                "authors": ["Perry J. Kaufman"],
                "publication_year": 2020,
                "edition": "1re édition",
            }
        ),
    )


def manifest_for(page_count):
    return PageManifest.from_entries(
        source_page_count=page_count,
        entries=tuple(
            PageManifestEntry(
                page_number=PageNumber.from_value(page_number),
                state=PageManifestEntryState.PRESENT,
            )
            for page_number in range(1, page_count + 1)
        ),
    )


def content_hash_for(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def item(text):
    return PageConversionItem(
        label=PageConversionItemLabel.TEXT,
        text=text,
        geometry=PageItemGeometry(
            left=10,
            top=10,
            right=90,
            bottom=40,
            page_width=100,
            page_height=100,
        ),
        content_hash=content_hash_for(text),
    )


def artifact(page_number, route_name, tool_name, artifact_hash, text):
    return PageConversionArtifact(
        page_number=PageNumber.from_value(page_number),
        route_name=route_name,
        tool_name=tool_name,
        tool_version=f"{tool_name.value.lower()}-v1",
        artifact_hash=artifact_hash,
        audit_artifact_ref=(
            "artifact:source_processing.page_conversion/"
            f"RUN-M004-T004-UNIT/page-{page_number:03d}-{tool_name.value.lower()}.json"
        ),
        items=(item(text),),
    )


def candidate(candidate_id, output):
    return PageConversionCandidate(candidate_id=candidate_id, page_output=output)


def native_candidate(page_number=1, candidate_id="native"):
    return candidate(
        candidate_id,
        artifact(
            page_number,
            PageRouteName.NATIVE_STANDARD,
            ConversionToolName.DOCLING_STANDARD,
            "a" * 64,
            f"Texte natif page {page_number}.",
        ),
    )


def granite_candidate(page_number=1, candidate_id="granite"):
    return candidate(
        candidate_id,
        artifact(
            page_number,
            PageRouteName.MIXED_PAGEWISE,
            ConversionToolName.GRANITE_DOCLING,
            "b" * 64,
            f"Texte Granite page {page_number}.",
        ),
    )


policy = TextAuthoritySelectionPolicy(policy_version="text-authority-v1")
native = native_candidate()
granite = granite_candidate()

decision = policy.select(
    page_number=PageNumber.from_value(1),
    candidates=(native, granite),
    selected_candidate_ids=("granite",),
    justification="Granite retenu après comparaison des chiffres, signes, unités et ordre de lecture.",
)

assert_equal(decision.page_number.value, 1, "La décision doit porter la page arbitrée.")
assert_equal(decision.authority.candidate_id, "granite", "L'autorité retenue doit être le candidat explicitement sélectionné.")
assert_equal(decision.authority.tool_name, ConversionToolName.GRANITE_DOCLING, "L'autorité doit conserver l'outil source.")
assert_equal(decision.authority.policy_version, "text-authority-v1", "La version de politique doit être conservée.")
assert_true(decision.authority.justification.startswith("Granite retenu"), "La justification doit être conservée.")
assert_equal(tuple(candidate.candidate_id for candidate in decision.candidates), ("native", "granite"), "Tous les candidats doivent être conservés.")
assert_equal(decision.selected_page_output().items[0].text, "Texte Granite page 1.", "La sortie retenue doit être accessible sans fusion.")
assert_equal(decision.to_payload()["authority"]["candidate_id"], "granite", "La sérialisation doit exposer l'autorité retenue.")
assert_equal(len(decision.to_payload()["candidates"]), 2, "La sérialisation doit conserver les candidats concurrents.")

assert_raises_code(
    "PAGE_AUTHORITY_MISSING",
    lambda: TextAuthority(
        page_number=PageNumber.from_value(1),
        candidate_id="",
        tool_name=ConversionToolName.DOCLING_STANDARD,
        tool_version="docling-standard-v1",
        artifact_hash="a" * 64,
        audit_artifact_ref="artifact:source_processing.page_conversion/RUN-M004-T004-UNIT/page-001-native.json",
        policy_version="text-authority-v1",
        justification="Autorité invalide.",
    ),
)
assert_raises_code(
    "PAGE_AUTHORITY_MISSING",
    lambda: TextAuthority(
        page_number=PageNumber.from_value(1),
        candidate_id="native",
        tool_name=ConversionToolName.DOCLING_STANDARD,
        tool_version="docling-standard-v1",
        artifact_hash="a" * 64,
        audit_artifact_ref="artifact:source_processing.page_conversion/RUN-M004-T004-UNIT/page-001-native.json",
        policy_version="",
        justification="Autorité sans version.",
    ),
)
assert_raises_code(
    "PAGE_AUTHORITY_MISSING",
    lambda: policy.select(
        page_number=PageNumber.from_value(1),
        candidates=(native,),
        selected_candidate_ids=(),
        justification="Aucune autorité sélectionnée.",
    ),
)
assert_raises_code(
    "PAGE_AUTHORITY_MISSING",
    lambda: policy.select(
        page_number=PageNumber.from_value(1),
        candidates=(native,),
        selected_candidate_ids=("absent",),
        justification="Candidat inexistant.",
    ),
)
assert_raises_code(
    "PAGE_AUTHORITY_AMBIGUOUS",
    lambda: policy.select(
        page_number=PageNumber.from_value(1),
        candidates=(native, granite),
        selected_candidate_ids=("native", "granite"),
        justification="Deux candidats sélectionnés.",
    ),
)
assert_raises_code(
    "PAGE_AUTHORITY_AMBIGUOUS",
    lambda: policy.select(
        page_number=PageNumber.from_value(1),
        candidates=(native, native_candidate(candidate_id="native")),
        selected_candidate_ids=("native",),
        justification="Identifiants de candidats dupliqués.",
    ),
)
assert_raises_code(
    "PAGE_AUTHORITY_MISSING",
    lambda: policy.select(
        page_number=PageNumber.from_value(1),
        candidates=(native, granite),
        selected_candidate_ids=("native",),
        justification="",
    ),
)
assert_raises_code(
    "PAGE_AUTHORITY_MISSING",
    lambda: TextAuthoritySelectionPolicy(policy_version=""),
)

page_manifest = manifest_for(2)
page_1_decision = decision
page_2_decision = policy.select(
    page_number=PageNumber.from_value(2),
    candidates=(granite_candidate(page_number=2, candidate_id="page-2-granite"),),
    selected_candidate_ids=("page-2-granite",),
    justification="Granite page 2 explicitement retenu.",
)
authority_manifest = TextAuthorityManifest.from_page_decisions(
    page_manifest=page_manifest,
    page_decisions=(page_1_decision, page_2_decision),
)

assert_equal(tuple(entry.page_number.value for entry in authority_manifest.entries), (1, 2), "Le manifeste doit conserver l'ordre PDF.")
assert_equal(authority_manifest.decision_for(PageNumber.from_value(2)).authority.candidate_id, "page-2-granite", "La décision d'une page doit être résolue explicitement.")
assert_equal(authority_manifest.to_payload()["entries"][0]["page_pdf"], 1, "Le payload du manifeste doit exposer la page.")

assert_raises_code(
    "PAGE_AUTHORITY_MISSING",
    lambda: TextAuthorityManifest.from_page_decisions(
        page_manifest=page_manifest,
        page_decisions=(page_1_decision,),
    ),
)
assert_raises_code(
    "PAGE_AUTHORITY_AMBIGUOUS",
    lambda: TextAuthorityManifest.from_page_decisions(
        page_manifest=page_manifest,
        page_decisions=(page_1_decision, page_1_decision, page_2_decision),
    ),
)

source_document = registered_source()
docling_document = PagewiseDoclingFusionService().merge_authorized(
    document_id=source_document.document_id,
    canonical_version_id="CVER-M004-T004",
    source_sha256=source_document.fingerprint,
    original_storage_ref=source_document.original_storage_ref,
    page_manifest=page_manifest,
    text_authority_manifest=authority_manifest,
)
assert_equal(docling_document.pages[0].items[0].text, "Texte Granite page 1.", "La fusion autorisée doit utiliser seulement l'autorité retenue.")
assert_equal(docling_document.pages[1].items[0].text, "Texte Granite page 2.", "La fusion autorisée doit couvrir chaque page du manifeste.")

assert_raises_code(
    "PAGE_AUTHORITY_MISSING",
    lambda: PagewiseDoclingFusionService().merge_authorized(
        document_id=source_document.document_id,
        canonical_version_id="CVER-M004-T004",
        source_sha256=source_document.fingerprint,
        original_storage_ref=source_document.original_storage_ref,
        page_manifest=manifest_for(3),
        text_authority_manifest=authority_manifest,
    ),
)

print("Tests unitaires T-004 autorité textuelle M-004: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m004_text_authority_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-004 autorité textuelle M-004: OK"
