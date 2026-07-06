$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import hashlib
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.evaluation.domain.pilot_corpus import (
    PilotCorpusManifestValidator,
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


def write_fixture_pdf(root, index):
    path = root / f"pilot_fixture_{index:03d}.pdf"
    path.write_bytes(f"%PDF-1.4\n% M-012 fixture {index:03d}\n".encode("utf-8"))
    return path


def base_document(index, path, strata):
    content_hash = file_sha256(path)
    return {
        "pilot_document_id": f"PDOC-M012-{index:04d}",
        "source_document_id": f"DOC-M012-{index:04d}",
        "original_path": str(path),
        "original_sha256": content_hash,
        "original_immutable": True,
        "source_processing_status": "DIAGNOSED_ROUTED_CANONICAL_PUBLISHED",
        "source_processing_ref": {
            "document_id": f"DOC-M012-{index:04d}",
            "diagnostic_run_id": f"SPRUN-M012-{index:04d}",
            "route_plan_id": f"RPLAN-M012-{index:04d}",
            "canonical_version_id": f"CVER-M012-{index:04d}",
            "canonical_artifact_sha256": content_hash,
        },
        "strata": list(strata),
        "edition_family_id": "EDITION-M012-ANNUAL" if "DIFFERENT_EDITION" in strata else f"EDITION-M012-{index:04d}",
        "edition_label": "2024" if index % 2 == 0 else "2023",
        "inclusion_justification": f"Document pilote {index:03d} requis pour la couverture M-012.",
    }


def valid_manifest(root, count=50):
    manifest_root = root / f"manifest_{len([path for path in root.iterdir() if path.is_dir()]):03d}_{count}"
    manifest_root.mkdir()
    documents = []
    for index in range(1, count + 1):
        path = write_fixture_pdf(manifest_root, index)
        strata = [REQUIRED_STRATA[(index - 1) % len(REQUIRED_STRATA)]]
        if index in (13, 26):
            strata = ["DIFFERENT_EDITION"]
        documents.append(base_document(index, path, strata))

    payload = {
        "schema_version": "1.0",
        "corpus_id": "PCORP-M012-PILOT-ACCEPTANCE",
        "policy_version": "PilotCorpusCoveragePolicy-1.0",
        "frozen": True,
        "frozen_at": "2026-07-06T00:00:00Z",
        "documents": documents,
        "exclusions": [
            {
                "candidate_document_id": "DOC-M012-EXCLUDED-0001",
                "exclusion_reason": "Source SP en quarantaine, non promouvable dans le corpus pilote.",
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


with TemporaryDirectory() as temporary_directory:
    fixture_root = Path(temporary_directory)
    validator = PilotCorpusManifestValidator()

    # Given des PDF personnels disponibles avec identifiants stables et originaux immuables.
    manifest = valid_manifest(fixture_root, count=50)
    manifest_path = fixture_root / "pilot_corpus_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    # When le corpus pilote M-012 est constitué.
    corpus = validator.validate_file(manifest_path)

    # Then il contient 50 à 100 documents, couvre explicitement les strates normatives et publie un manifeste figé.
    assert corpus.document_count == 50
    assert corpus.covered_strata == frozenset(REQUIRED_STRATA)
    assert corpus.corpus_id == "PCORP-M012-PILOT-ACCEPTANCE"

    expect_raises(
        "entre 50 et 100",
        lambda: validator.validate_payload(valid_manifest(fixture_root, count=49)),
    )
    expect_raises(
        "entre 50 et 100",
        lambda: validator.validate_payload(valid_manifest(fixture_root, count=101)),
    )

    without_stable_id = valid_manifest(fixture_root, count=50)
    del without_stable_id["documents"][0]["pilot_document_id"]
    without_stable_id = freeze_pilot_corpus_manifest(without_stable_id)
    expect_raises(
        "identifiant stable",
        lambda: validator.validate_payload(without_stable_id),
    )

    missing_stratum = valid_manifest(fixture_root, count=50)
    for document in missing_stratum["documents"]:
        document["strata"] = [
            item if item != "NOISY_SCAN" else "DIGITAL_NATIVE_CLEAN"
            for item in document["strata"]
        ]
    missing_stratum = freeze_pilot_corpus_manifest(missing_stratum)
    expect_raises(
        "NOISY_SCAN",
        lambda: validator.validate_payload(missing_stratum),
    )

    unresolved_path = valid_manifest(fixture_root, count=50)
    unresolved_path["documents"][0]["original_path"] = str(fixture_root / "absent.pdf")
    unresolved_path = freeze_pilot_corpus_manifest(unresolved_path)
    expect_raises(
        "chemin non resolvable",
        lambda: validator.validate_payload(unresolved_path),
    )

print("Test d'acceptation du corpus pilote représentatif M-012: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m012_pilot_corpus_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Test d'acceptation du corpus pilote représentatif M-012 invalide. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
