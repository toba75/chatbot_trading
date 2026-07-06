$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import hashlib
import sys
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.evaluation.domain.pilot_corpus import (
    PilotCoveragePolicy,
    freeze_pilot_corpus_manifest,
)


REQUIRED_STRATA = (
    "DIGITAL_NATIVE_CLEAN",
    "CLEAN_SCAN",
    "SKEWED_SCAN",
    "NOISY_SCAN",
    "DEFECTIVE_OCR_LAYER",
    "MIXED_DOCUMENT",
    "FRENCH_TEXT",
    "ENGLISH_TEXT",
    "FINANCIAL_TABLES",
    "EQUATIONS",
    "GRAPHICS",
    "MULTI_COLUMNS",
    "DIFFERENT_EDITION",
)


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_fixture_pdf(root, index, *, duplicate_of=None):
    path = root / f"unit_fixture_{index:03d}.pdf"
    content_index = index if duplicate_of is None else duplicate_of
    path.write_bytes(f"%PDF-1.4\n% M-012 unit fixture {content_index:03d}\n".encode("utf-8"))
    return path


def base_document(index, path, strata):
    content_hash = file_sha256(path)
    return {
        "pilot_document_id": f"PDOC-M012-UNIT-{index:04d}",
        "source_document_id": f"DOC-M012-UNIT-{index:04d}",
        "original_path": str(path),
        "original_sha256": content_hash,
        "original_immutable": True,
        "source_processing_status": "DIAGNOSED_ROUTED_CANONICAL_PUBLISHED",
        "source_processing_ref": {
            "document_id": f"DOC-M012-UNIT-{index:04d}",
            "diagnostic_run_id": f"SPRUN-M012-UNIT-{index:04d}",
            "route_plan_id": f"RPLAN-M012-UNIT-{index:04d}",
            "canonical_version_id": f"CVER-M012-UNIT-{index:04d}",
            "canonical_artifact_sha256": content_hash,
        },
        "strata": list(strata),
        "edition_family_id": "EDITION-M012-UNIT-PAIR" if "DIFFERENT_EDITION" in strata else f"EDITION-M012-UNIT-{index:04d}",
        "edition_label": "2024" if index % 2 == 0 else "2023",
        "inclusion_justification": f"Document unitaire {index:03d} requis pour la strate M-012.",
    }


def valid_manifest(root, count=50, duplicate_binary=False):
    manifest_root = root / f"manifest_{len([path for path in root.iterdir() if path.is_dir()]):03d}_{count}_{int(duplicate_binary)}"
    manifest_root.mkdir()
    documents = []
    for index in range(1, count + 1):
        duplicate_of = 1 if duplicate_binary and index == 2 else None
        path = write_fixture_pdf(manifest_root, index, duplicate_of=duplicate_of)
        strata = [REQUIRED_STRATA[(index - 1) % len(REQUIRED_STRATA)]]
        if index in (13, 26):
            strata = ["DIFFERENT_EDITION"]
        documents.append(base_document(index, path, strata))

    payload = {
        "schema_version": "1.0",
        "corpus_id": "PCORP-M012-PILOT-UNIT",
        "policy_version": "PilotCorpusCoveragePolicy-1.0",
        "frozen": True,
        "frozen_at": "2026-07-06T00:00:00Z",
        "documents": documents,
        "exclusions": [
            {
                "candidate_document_id": "DOC-M012-UNIT-EXCLUDED-0001",
                "exclusion_reason": "Ancienne source non diagnostiquée par SP.",
            }
        ],
    }
    return freeze_pilot_corpus_manifest(payload)


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


def without_stratum(payload, stratum):
    clone = deepcopy(payload)
    replacement = "CLEAN_SCAN" if stratum == "DIGITAL_NATIVE_CLEAN" else "DIGITAL_NATIVE_CLEAN"
    for document in clone["documents"]:
        document["strata"] = [
            item if item != stratum else replacement
            for item in document["strata"]
        ]
    return freeze_pilot_corpus_manifest(clone)


with TemporaryDirectory() as temporary_directory:
    fixture_root = Path(temporary_directory)
    policy = PilotCoveragePolicy()
    valid = valid_manifest(fixture_root, count=50)

    assert policy.validate_manifest_payload(valid).document_count == 50
    assert policy.validate_manifest_payload(valid_manifest(fixture_root, count=100)).document_count == 100

    expect_raises("entre 50 et 100", lambda: policy.validate_manifest_payload(valid_manifest(fixture_root, count=49)))
    expect_raises("entre 50 et 100", lambda: policy.validate_manifest_payload(valid_manifest(fixture_root, count=101)))

    missing_cases = {
        "PDF numérique propre manquant": ("DIGITAL_NATIVE_CLEAN", "DIGITAL_NATIVE_CLEAN"),
        "scan propre manquant": ("CLEAN_SCAN", "CLEAN_SCAN"),
        "scan incliné manquant": ("SKEWED_SCAN", "SKEWED_SCAN"),
        "scan bruité manquant": ("NOISY_SCAN", "NOISY_SCAN"),
        "ancienne couche OCR défectueuse absente": ("DEFECTIVE_OCR_LAYER", "DEFECTIVE_OCR_LAYER"),
        "document mixte absent": ("MIXED_DOCUMENT", "MIXED_DOCUMENT"),
        "couverture français absente": ("FRENCH_TEXT", "FRENCH_TEXT"),
        "couverture anglais absente": ("ENGLISH_TEXT", "ENGLISH_TEXT"),
        "tableau financier absent": ("FINANCIAL_TABLES", "FINANCIAL_TABLES"),
        "équation absente": ("EQUATIONS", "EQUATIONS"),
        "graphique absent": ("GRAPHICS", "GRAPHICS"),
        "colonnes multiples absentes": ("MULTI_COLUMNS", "MULTI_COLUMNS"),
        "édition différente absente": ("DIFFERENT_EDITION", "DIFFERENT_EDITION"),
    }
    for _, (stratum, fragment) in missing_cases.items():
        expect_raises(fragment, lambda stratum=stratum: policy.validate_manifest_payload(without_stratum(valid, stratum)))

    expect_raises(
        "doublon binaire",
        lambda: policy.validate_manifest_payload(valid_manifest(fixture_root, count=50, duplicate_binary=True)),
    )

    mutable_original = deepcopy(valid)
    mutable_original["documents"][0]["original_immutable"] = False
    mutable_original = freeze_pilot_corpus_manifest(mutable_original)
    expect_raises("original immuable", lambda: policy.validate_manifest_payload(mutable_original))

    missing_sp_reference = deepcopy(valid)
    del missing_sp_reference["documents"][0]["source_processing_ref"]
    missing_sp_reference = freeze_pilot_corpus_manifest(missing_sp_reference)
    expect_raises("reference SP", lambda: policy.validate_manifest_payload(missing_sp_reference))

    unmotivated_exclusion = deepcopy(valid)
    unmotivated_exclusion["exclusions"][0]["exclusion_reason"] = ""
    unmotivated_exclusion = freeze_pilot_corpus_manifest(unmotivated_exclusion)
    expect_raises("exclusion", lambda: policy.validate_manifest_payload(unmotivated_exclusion))

    modified_after_freeze = deepcopy(valid)
    modified_after_freeze["documents"][0]["inclusion_justification"] = "Modification post-gel non autorisée."
    expect_raises("modifie apres gel", lambda: policy.validate_manifest_payload(modified_after_freeze))

print("Tests unitaires PilotCoveragePolicy M-012: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m012_pilot_corpus_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Tests unitaires PilotCoveragePolicy M-012 invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
