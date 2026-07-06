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
from app.evaluation.domain.page_annotation import (
    AnnotationSetManifestValidator,
    freeze_page_annotation_set,
)
from app.evaluation.domain.pilot_corpus import PilotCorpus, PilotDocument


CONTENT_HASH = "a" * 64
ARTIFACT_HASH = "b" * 64
SOURCE_HASH = "c" * 64


def canonical_ref():
    return CanonicalSourceRef.from_payload(
        {
            "schema_version": "1.0",
            "canonical_source_id": "CSRC-M012-ANNOT-0001",
            "document_id": "DOC-M012-ANNOT-0001",
            "canonical_version_id": "CVER-M012-ANNOT-0001",
            "source_sha256": SOURCE_HASH,
            "canonical_artifact_sha256": ARTIFACT_HASH,
            "page_count": 2,
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
                "item-table-cell-001": CONTENT_HASH,
                "item-empty-page-002": "d" * 64,
            }
        },
    )


def locator_payload(item_id="item-table-cell-001", content_hash=CONTENT_HASH, page_pdf=1):
    return {
        "schema_version": "1.0",
        "canonical_version_id": "CVER-M012-ANNOT-0001",
        "document_id": "DOC-M012-ANNOT-0001",
        "page_pdf": page_pdf,
        "item_id": item_id,
        "bbox": [0.10, 0.20, 0.40, 0.35],
        "content_hash": content_hash,
    }


def page_ref(page_pdf=1):
    return {
        "pilot_document_id": "PDOC-M012-ANNOT-0001",
        "source_document_id": "DOC-M012-ANNOT-0001",
        "canonical_version_id": "CVER-M012-ANNOT-0001",
        "page_pdf": page_pdf,
    }


def pilot_corpus(original_path):
    document = PilotDocument(
        pilot_document_id="PDOC-M012-ANNOT-0001",
        source_document_id="DOC-M012-ANNOT-0001",
        original_path=original_path,
        original_sha256=SOURCE_HASH,
        source_processing_status="DIAGNOSED_ROUTED_CANONICAL_PUBLISHED",
        source_processing_ref={
            "document_id": "DOC-M012-ANNOT-0001",
            "diagnostic_run_id": "SPRUN-M012-ANNOT-0001",
            "route_plan_id": "RPLAN-M012-ANNOT-0001",
            "canonical_version_id": "CVER-M012-ANNOT-0001",
            "canonical_artifact_sha256": ARTIFACT_HASH,
        },
        strata=frozenset({"FINANCIAL_TABLES"}),
        edition_family_id="EDITION-M012-ANNOT",
        edition_label="2026",
        inclusion_justification="Document pilote avec tableau financier requis pour l'oracle M-012.",
    )
    return PilotCorpus(
        corpus_id="PCORP-M012-ANNOT",
        policy_version="PilotCorpusCoveragePolicy-1.0",
        frozen_at="2026-07-06T00:00:00Z",
        documents=(document,),
        exclusions=(),
        frozen_manifest_sha256="e" * 64,
    )


def valid_annotation_set():
    payload = {
        "schema_version": "1.0",
        "annotation_set_id": "ASET-M012-PAGE-0001",
        "corpus_id": "PCORP-M012-ANNOT",
        "policy_version": "AnnotationCompletenessPolicy-1.0",
        "annotation_version": "ANN-M012-PAGE-0001",
        "frozen": True,
        "frozen_at": "2026-07-06T00:00:00Z",
        "replaces_annotation_set_id": None,
        "historical_annotation_versions": [],
        "benchmark_pages": [page_ref()],
        "annotations": [
            {
                "annotation_id": "PANN-M012-0001",
                "page_ref": page_ref(),
                "annotation_version": "ANN-M012-PAGE-0001",
                "annotation_author_type": "HUMAN_REVIEWER",
                "generated_by_evaluated_system": False,
                "expected_state": "EVALUABLE",
                "expected_route": "OCR_WITH_TABLES",
                "reference_transcription": "Chiffre d'affaires -12,50 % sur la période.",
                "critical_numeric_values": [
                    {
                        "value_id": "NUM-M012-0001",
                        "signed_value": "-12.50",
                        "unit": "%",
                        "context": "Variation annuelle du chiffre d'affaires.",
                        "provenance_zone_id": "ZONE-M012-0001",
                    }
                ],
                "table_cells": [
                    {
                        "table_id": "TABLE-M012-0001",
                        "row_index": 1,
                        "column_index": 2,
                        "text": "-12,50 %",
                        "provenance_zone_id": "ZONE-M012-0001",
                    }
                ],
                "reading_order": [
                    {
                        "order_index": 1,
                        "role": "table_cell",
                        "provenance_zone_id": "ZONE-M012-0001",
                    }
                ],
                "provenance_zones": [
                    {
                        "provenance_zone_id": "ZONE-M012-0001",
                        "source_locator": locator_payload(),
                        "human_label": "Cellule variation annuelle.",
                    }
                ],
            }
        ],
    }
    return freeze_page_annotation_set(payload)


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


with TemporaryDirectory() as temporary_directory:
    original_path = Path(temporary_directory) / "source.pdf"
    original_path.write_bytes(b"%PDF-1.4\n% annotation acceptance\n")
    corpus = pilot_corpus(original_path)
    validator = AnnotationSetManifestValidator()
    policy = locator_policy()

    # Given un corpus pilote figé.
    manifest = valid_annotation_set()

    # When le jeu annoté page par page est publié.
    annotation_set = validator.validate_payload(
        manifest,
        pilot_corpus=corpus,
        source_locator_validation_policy=policy,
    )

    # Then chaque page évaluée porte des attentes complètes et résolubles avant benchmark.
    assert annotation_set.annotation_count == 1
    assert annotation_set.benchmark_page_count == 1
    assert annotation_set.annotations[0].critical_numeric_values[0].signed_value == "-12.50"
    assert annotation_set.annotations[0].critical_numeric_values[0].unit == "%"

    missing_annotation = deepcopy(manifest)
    missing_annotation["annotations"] = []
    missing_annotation = freeze_page_annotation_set(missing_annotation)
    expect_raises(
        "annotation absente",
        lambda: validator.validate_payload(
            missing_annotation,
            pilot_corpus=corpus,
            source_locator_validation_policy=policy,
        ),
    )

    unresolved_zone = deepcopy(manifest)
    unresolved_zone["annotations"][0]["provenance_zones"][0]["source_locator"] = locator_payload(
        item_id="item-inconnu"
    )
    unresolved_zone = freeze_page_annotation_set(unresolved_zone)
    expect_raises(
        "item_id non resolvable",
        lambda: validator.validate_payload(
            unresolved_zone,
            pilot_corpus=corpus,
            source_locator_validation_policy=policy,
        ),
    )

    unsigned_value = deepcopy(manifest)
    unsigned_value["annotations"][0]["critical_numeric_values"][0]["signed_value"] = "12.50"
    unsigned_value = freeze_page_annotation_set(unsigned_value)
    expect_raises(
        "signe",
        lambda: validator.validate_payload(
            unsigned_value,
            pilot_corpus=corpus,
            source_locator_validation_policy=policy,
        ),
    )

    missing_unit = deepcopy(manifest)
    missing_unit["annotations"][0]["critical_numeric_values"][0]["unit"] = ""
    missing_unit = freeze_page_annotation_set(missing_unit)
    expect_raises(
        "unit",
        lambda: validator.validate_payload(
            missing_unit,
            pilot_corpus=corpus,
            source_locator_validation_policy=policy,
        ),
    )

    generated_by_system = deepcopy(manifest)
    generated_by_system["annotations"][0]["generated_by_evaluated_system"] = True
    generated_by_system = freeze_page_annotation_set(generated_by_system)
    expect_raises(
        "systeme evalue",
        lambda: validator.validate_payload(
            generated_by_system,
            pilot_corpus=corpus,
            source_locator_validation_policy=policy,
        ),
    )

    state_route_conflict = deepcopy(manifest)
    state_route_conflict["annotations"][0]["expected_state"] = "EMPTY_DECLARED"
    state_route_conflict["annotations"][0]["empty_or_rejection_reason"] = "Page blanche déclarée par l'annotateur."
    state_route_conflict = freeze_page_annotation_set(state_route_conflict)
    expect_raises(
        "conflit",
        lambda: validator.validate_payload(
            state_route_conflict,
            pilot_corpus=corpus,
            source_locator_validation_policy=policy,
        ),
    )

print("Test d'acceptation du jeu annoté page par page M-012: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m012_page_annotation_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Test d'acceptation du jeu annoté page par page M-012 invalide. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
