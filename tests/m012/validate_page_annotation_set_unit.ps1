$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.contracts.source_references import CanonicalSourceRef, SourceLocatorValidationPolicy
from app.evaluation.domain.page_annotation import AnnotationCompletenessPolicy, freeze_page_annotation_set
from app.evaluation.domain.pilot_corpus import PilotCorpus, PilotDocument


CONTENT_HASH = "1" * 64
ARTIFACT_HASH = "2" * 64
SOURCE_HASH = "3" * 64


def canonical_ref():
    return CanonicalSourceRef.from_payload(
        {
            "schema_version": "1.0",
            "canonical_source_id": "CSRC-M012-UNIT-0001",
            "document_id": "DOC-M012-UNIT-0001",
            "canonical_version_id": "CVER-M012-UNIT-0001",
            "source_sha256": SOURCE_HASH,
            "canonical_artifact_sha256": ARTIFACT_HASH,
            "page_count": 3,
            "accepted_at": "2026-07-06T00:00:00Z",
            "quality_policy_version": "CanonicalQualityPolicy-1.0",
        }
    )


def locator_policy():
    ref = canonical_ref()
    return SourceLocatorValidationPolicy(
        canonical_sources_by_version_id={ref.canonical_version_id: ref},
        version_statuses_by_version_id={ref.canonical_version_id: "ACCEPTED"},
        resolvable_item_ids_by_version_id={
            ref.canonical_version_id: {
                "item-page-001": CONTENT_HASH,
                "item-page-002": "4" * 64,
            }
        },
    )


def locator_payload(item_id="item-page-001", content_hash=CONTENT_HASH, page_pdf=1):
    return {
        "schema_version": "1.0",
        "canonical_version_id": "CVER-M012-UNIT-0001",
        "document_id": "DOC-M012-UNIT-0001",
        "page_pdf": page_pdf,
        "item_id": item_id,
        "bbox": [0.10, 0.10, 0.50, 0.30],
        "content_hash": content_hash,
    }


def page_ref(page_pdf=1):
    return {
        "pilot_document_id": "PDOC-M012-UNIT-0001",
        "source_document_id": "DOC-M012-UNIT-0001",
        "canonical_version_id": "CVER-M012-UNIT-0001",
        "page_pdf": page_pdf,
    }


def corpus(original_path):
    return PilotCorpus(
        corpus_id="PCORP-M012-UNIT",
        policy_version="PilotCorpusCoveragePolicy-1.0",
        frozen_at="2026-07-06T00:00:00Z",
        documents=(
            PilotDocument(
                pilot_document_id="PDOC-M012-UNIT-0001",
                source_document_id="DOC-M012-UNIT-0001",
                original_path=original_path,
                original_sha256=SOURCE_HASH,
                source_processing_status="DIAGNOSED_ROUTED_CANONICAL_PUBLISHED",
                source_processing_ref={
                    "document_id": "DOC-M012-UNIT-0001",
                    "diagnostic_run_id": "SPRUN-M012-UNIT-0001",
                    "route_plan_id": "RPLAN-M012-UNIT-0001",
                    "canonical_version_id": "CVER-M012-UNIT-0001",
                    "canonical_artifact_sha256": ARTIFACT_HASH,
                },
                strata=frozenset({"DIGITAL_NATIVE_CLEAN"}),
                edition_family_id="EDITION-M012-UNIT",
                edition_label="2026",
                inclusion_justification="Document unitaire M-012.",
            ),
        ),
        exclusions=(),
        frozen_manifest_sha256="5" * 64,
    )


def valid_payload():
    return freeze_page_annotation_set(
        {
            "schema_version": "1.0",
            "annotation_set_id": "ASET-M012-UNIT-0001",
            "corpus_id": "PCORP-M012-UNIT",
            "policy_version": "AnnotationCompletenessPolicy-1.0",
            "annotation_version": "ANN-M012-UNIT-0001",
            "frozen": True,
            "frozen_at": "2026-07-06T00:00:00Z",
            "replaces_annotation_set_id": None,
            "historical_annotation_versions": [],
            "benchmark_pages": [page_ref()],
            "annotations": [
                {
                    "annotation_id": "PANN-M012-UNIT-0001",
                    "page_ref": page_ref(),
                    "annotation_version": "ANN-M012-UNIT-0001",
                    "annotation_author_type": "HUMAN_REVIEWER",
                    "generated_by_evaluated_system": False,
                    "expected_state": "EVALUABLE",
                    "expected_route": "NATIVE_TEXT",
                    "reference_transcription": "Résultat net +42 EUR.",
                    "critical_numeric_values": [
                        {
                            "value_id": "NUM-M012-UNIT-0001",
                            "signed_value": "+42",
                            "unit": "EUR",
                            "context": "Résultat net publié.",
                            "provenance_zone_id": "ZONE-M012-UNIT-0001",
                        }
                    ],
                    "table_cells": [
                        {
                            "table_id": "TABLE-M012-UNIT-0001",
                            "row_index": 1,
                            "column_index": 1,
                            "text": "+42 EUR",
                            "provenance_zone_id": "ZONE-M012-UNIT-0001",
                        }
                    ],
                    "reading_order": [
                        {
                            "order_index": 1,
                            "role": "paragraph",
                            "provenance_zone_id": "ZONE-M012-UNIT-0001",
                        }
                    ],
                    "provenance_zones": [
                        {
                            "provenance_zone_id": "ZONE-M012-UNIT-0001",
                            "source_locator": locator_payload(),
                            "human_label": "Résultat net dans le tableau.",
                        }
                    ],
                }
            ],
        }
    )


def expect_raises(expected_fragment, action):
    try:
        action()
    except Exception as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(
                f"Erreur inattendue. Fragment attendu: {expected_fragment}. Erreur: {exc}"
            ) from exc
        return
    raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def validate(payload, original_path):
    return AnnotationCompletenessPolicy().validate_payload(
        payload,
        pilot_corpus=corpus(original_path),
        source_locator_validation_policy=locator_policy(),
    )


with TemporaryDirectory() as temporary_directory:
    original_path = Path(temporary_directory) / "source.pdf"
    original_path.write_bytes(b"%PDF-1.4\n% annotation unit\n")
    valid = valid_payload()
    assert validate(valid, original_path).annotation_count == 1

    missing_annotation = deepcopy(valid)
    missing_annotation["annotations"] = []
    missing_annotation = freeze_page_annotation_set(missing_annotation)
    expect_raises("annotation absente", lambda: validate(missing_annotation, original_path))

    missing_route = deepcopy(valid)
    del missing_route["annotations"][0]["expected_route"]
    missing_route = freeze_page_annotation_set(missing_route)
    expect_raises("expected_route absent", lambda: validate(missing_route, original_path))

    missing_transcription = deepcopy(valid)
    missing_transcription["annotations"][0]["reference_transcription"] = ""
    missing_transcription = freeze_page_annotation_set(missing_transcription)
    expect_raises("transcription", lambda: validate(missing_transcription, original_path))

    incomplete_table = deepcopy(valid)
    del incomplete_table["annotations"][0]["table_cells"][0]["provenance_zone_id"]
    incomplete_table = freeze_page_annotation_set(incomplete_table)
    expect_raises("provenance_zone_id absent", lambda: validate(incomplete_table, original_path))

    missing_order = deepcopy(valid)
    missing_order["annotations"][0]["reading_order"] = []
    missing_order = freeze_page_annotation_set(missing_order)
    expect_raises("ordre de lecture", lambda: validate(missing_order, original_path))

    invalid_zone = deepcopy(valid)
    invalid_zone["annotations"][0]["provenance_zones"][0]["source_locator"] = locator_payload(
        content_hash="6" * 64
    )
    invalid_zone = freeze_page_annotation_set(invalid_zone)
    expect_raises("content_hash incoherent", lambda: validate(invalid_zone, original_path))

    empty_page_not_declared = deepcopy(valid)
    empty_page_not_declared["annotations"][0]["expected_state"] = "EMPTY_DECLARED"
    empty_page_not_declared["annotations"][0]["expected_route"] = "NO_ROUTE"
    empty_page_not_declared["annotations"][0]["reference_transcription"] = " "
    empty_page_not_declared["annotations"][0]["critical_numeric_values"] = []
    empty_page_not_declared["annotations"][0]["table_cells"] = []
    empty_page_not_declared = freeze_page_annotation_set(empty_page_not_declared)
    expect_raises("page vide", lambda: validate(empty_page_not_declared, original_path))

    state_route_conflict = deepcopy(valid)
    state_route_conflict["annotations"][0]["expected_state"] = "REJECTED_DECLARED"
    state_route_conflict["annotations"][0]["empty_or_rejection_reason"] = "Page rejetée par annotation humaine."
    state_route_conflict = freeze_page_annotation_set(state_route_conflict)
    expect_raises("conflit", lambda: validate(state_route_conflict, original_path))

    generated_by_system = deepcopy(valid)
    generated_by_system["annotations"][0]["annotation_author_type"] = "EVALUATED_SYSTEM"
    generated_by_system = freeze_page_annotation_set(generated_by_system)
    expect_raises("systeme evalue", lambda: validate(generated_by_system, original_path))

    historical_removed = deepcopy(valid)
    historical_removed["replaces_annotation_set_id"] = "ASET-M012-UNIT-OLD"
    historical_removed = freeze_page_annotation_set(historical_removed)
    expect_raises("historique", lambda: validate(historical_removed, original_path))

print("Tests unitaires AnnotationCompletenessPolicy M-012: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m012_page_annotation_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0) {
        throw "Tests unitaires AnnotationCompletenessPolicy M-012 invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
