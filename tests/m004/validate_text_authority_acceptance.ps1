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
    original_content = b"%PDF-1.7\ntext authority acceptance\n%%EOF\n"
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
                "title": "Autorité textuelle M-004",
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


def conversion_item(text, content_hash):
    return PageConversionItem(
        label=PageConversionItemLabel.TEXT,
        text=text,
        geometry=PageItemGeometry(
            left=100,
            top=100,
            right=900,
            bottom=180,
            page_width=1000,
            page_height=1000,
        ),
        content_hash=content_hash_for(text),
    )


def artifact(page_number, route_name, tool_name, text, artifact_hash, content_hash, suffix):
    return PageConversionArtifact(
        page_number=PageNumber.from_value(page_number),
        route_name=route_name,
        tool_name=tool_name,
        tool_version=f"{tool_name.value.lower()}-v1",
        artifact_hash=artifact_hash,
        audit_artifact_ref=(
            "artifact:source_processing.page_conversion/"
            f"RUN-M004-T004/page-{page_number:03d}-{suffix}.json"
        ),
        items=(conversion_item(text, content_hash),),
    )


def candidate(candidate_id, output):
    return PageConversionCandidate(candidate_id=candidate_id, page_output=output)


source_document = registered_source()
page_manifest = manifest_for(2)
policy = TextAuthoritySelectionPolicy(policy_version="text-authority-v1")

native_page_1 = candidate(
    "page-001-native",
    artifact(
        1,
        PageRouteName.NATIVE_STANDARD,
        ConversionToolName.DOCLING_STANDARD,
        "Rendement annualisé: 12.5%.",
        "a" * 64,
        "1" * 64,
        "native",
    ),
)
granite_page_1 = candidate(
    "page-001-granite",
    artifact(
        1,
        PageRouteName.MIXED_PAGEWISE,
        ConversionToolName.GRANITE_DOCLING,
        "Rendement annualisé: 125%.",
        "b" * 64,
        "2" * 64,
        "granite",
    ),
)
native_page_2 = candidate(
    "page-002-native",
    artifact(
        2,
        PageRouteName.NATIVE_STANDARD,
        ConversionToolName.DOCLING_STANDARD,
        "Table illisible sans colonnes.",
        "c" * 64,
        "3" * 64,
        "native",
    ),
)
granite_page_2 = candidate(
    "page-002-granite",
    artifact(
        2,
        PageRouteName.TARGETED_ENRICHMENT,
        ConversionToolName.GRANITE_DOCLING,
        "Colonne A: 10; Colonne B: 11.",
        "d" * 64,
        "4" * 64,
        "granite",
    ),
)

# Given une page avec une sortie native et une sortie Granite qui divergent.
# When l'adjudication d'autorité textuelle est exécutée avec une décision explicite et justifiée.
native_authority_decision = policy.select(
    page_number=PageNumber.from_value(1),
    candidates=(native_page_1, granite_page_1),
    selected_candidate_ids=("page-001-native",),
    justification="Texte natif vérifié: chiffres, signes et ordre de lecture concordants.",
)
granite_authority_decision = policy.select(
    page_number=PageNumber.from_value(2),
    candidates=(native_page_2, granite_page_2),
    selected_candidate_ids=("page-002-granite",),
    justification="Granite retenu: structure tabulaire native incomplète après comparaison visuelle.",
)
authority_manifest = TextAuthorityManifest.from_page_decisions(
    page_manifest=page_manifest,
    page_decisions=(native_authority_decision, granite_authority_decision),
)

# Then une seule autorité est retenue par page et les sorties concurrentes restent auditables.
assert_equal(native_authority_decision.authority.candidate_id, "page-001-native", "La page 1 doit retenir l'autorité native explicitement choisie.")
assert_equal(granite_authority_decision.authority.candidate_id, "page-002-granite", "La page 2 doit retenir l'autorité Granite explicitement choisie.")
assert_true(all(decision.authority.policy_version == "text-authority-v1" for decision in authority_manifest.page_decisions), "Chaque autorité doit conserver la version de politique.")
assert_true(all(decision.authority.justification for decision in authority_manifest.page_decisions), "Chaque autorité doit conserver une justification.")
assert_equal(tuple(candidate.candidate_id for candidate in native_authority_decision.candidates), ("page-001-native", "page-001-granite"), "Les candidats concurrents de la page 1 doivent être conservés.")
assert_equal(tuple(candidate.candidate_id for candidate in granite_authority_decision.candidates), ("page-002-native", "page-002-granite"), "Les candidats concurrents de la page 2 doivent être conservés.")

docling_document = PagewiseDoclingFusionService().merge_authorized(
    document_id=source_document.document_id,
    canonical_version_id="CVER-M004-T004",
    source_sha256=source_document.fingerprint,
    original_storage_ref=source_document.original_storage_ref,
    page_manifest=page_manifest,
    text_authority_manifest=authority_manifest,
)

assert_equal(tuple(page.page_number.value for page in docling_document.pages), (1, 2), "La fusion autorisée doit conserver l'ordre PDF.")
assert_equal(docling_document.pages[0].items[0].text, "Rendement annualisé: 12.5%.", "La page 1 ne doit pas fusionner le texte Granite divergent.")
assert_equal(docling_document.pages[1].items[0].text, "Colonne A: 10; Colonne B: 11.", "La page 2 doit utiliser le candidat Granite retenu.")
assert_true(
    "125%" not in tuple(item.text for page in docling_document.pages for item in page.items),
    "La sortie concurrente non retenue ne doit pas alimenter silencieusement le canonique.",
)

assert_raises_code(
    "PAGE_AUTHORITY_AMBIGUOUS",
    lambda: policy.select(
        page_number=PageNumber.from_value(1),
        candidates=(native_page_1, granite_page_1),
        selected_candidate_ids=("page-001-native", "page-001-granite"),
        justification="Deux autorités concurrentes ne peuvent pas être retenues.",
    ),
)

assert_raises_code(
    "PAGE_AUTHORITY_MISSING",
    lambda: TextAuthorityManifest.from_page_decisions(
        page_manifest=page_manifest,
        page_decisions=(native_authority_decision,),
    ),
)

print("Test d'acceptation T-004 autorité textuelle M-004: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m004_text_authority_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-004 autorité textuelle M-004: OK"
