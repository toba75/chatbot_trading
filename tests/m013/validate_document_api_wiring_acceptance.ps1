$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ostrading-document-api-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $env:OST_REPO_ROOT = $repoRoot
    $env:OST_DOCUMENT_API_TEMP_ROOT = $temporaryRoot

    @'
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["OST_REPO_ROOT"])

from app.platform.document_api import build_local_document_api


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Attendu={expected!r}, obtenu={actual!r}")


def one_page_pdf():
    objects = (
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n",
    )
    payload = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for item in objects:
        offsets.append(len(payload))
        payload.extend(item)
    xref_offset = len(payload)
    payload.extend(b"xref\n0 4\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        payload.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    payload.extend(
        b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n"
        + str(xref_offset).encode("ascii")
        + b"\n%%EOF\n"
    )
    return bytes(payload)


storage_root = Path(os.environ["OST_DOCUMENT_API_TEMP_ROOT"])
api = build_local_document_api(
    corpus_root=storage_root / "corpus",
    projection_root=storage_root / "projections",
    configuration_hash="a" * 64,
    code_version="acceptance-test",
    model_version="document-diagnostic-v1",
)
pdf_content = one_page_pdf()

# Given l'API orchestratrice dispose d'un stockage documentaire local vide.
# When un PDF est enregistre par le contrat public POST /v1/documents.
registered = api.handle_post(
    path="/v1/documents",
    body={
        "original_content": pdf_content,
        "bibliographic_metadata": {
            "title": "Document de validation",
            "authors": ["Equipe OSTrading"],
            "publication_year": 2026,
            "edition": "1",
        },
    },
)

# Then la commande atteint le cas d'usage SP reel et le document est lisible dans le corpus public.
assert_equal(registered.status_code, 201, "L'enregistrement doit creer la source.")
document_id = registered.json_body["document_id"]
listed = api.handle_get(path="/v1/documents")
assert_equal(listed.status_code, 200, "Le corpus public doit etre lisible.")
assert_equal(len(listed.json_body["documents"]), 1, "Le corpus doit contenir le PDF enregistre.")
assert_equal(listed.json_body["documents"][0]["document_id"], document_id, "Le DocumentId doit rester stable.")
assert_equal(listed.json_body["documents"][0]["diagnostic_status"], "DIAGNOSTIC_NOT_REQUESTED", "Le diagnostic initial doit etre explicite.")

# When le diagnostic est demande par POST /v1/documents/{id}/diagnose.
diagnosis_requested = api.handle_post(
    path=f"/v1/documents/{document_id}/diagnose",
    body={},
)

# Then la commande atteint le cas d'usage SP et sa sortie detaillee devient lisible.
assert_equal(diagnosis_requested.status_code, 202, "Le diagnostic doit etre accepte.")
diagnosis = api.handle_get(path=f"/v1/documents/{document_id}/diagnostic")
assert_equal(diagnosis.status_code, 200, "Le diagnostic public doit etre lisible.")
assert_equal(diagnosis.json_body["diagnostic_status"], "DIAGNOSTIC_REQUESTED", "La demande de diagnostic doit etre visible.")
assert_equal(diagnosis.json_body["source_page_count"], 1, "Le manifeste doit exposer le nombre de pages.")
assert_equal(diagnosis.json_body["pages"], [{"page_number": 1, "manifest_state": "PRESENT", "diagnostic": None}], "Chaque page doit rester inspectable.")

# Then les sorties absentes de conversion et projection restent lisibles sans etat invente.
conversion = api.handle_get(path=f"/v1/documents/{document_id}/conversion")
projection = api.handle_get(path=f"/v1/documents/{document_id}/projection")
assert_equal(conversion.status_code, 200, "La lecture de conversion doit etre operationnelle.")
assert_equal(conversion.json_body, {"document_id": document_id, "conversion_status": "CONVERSION_NOT_REQUESTED", "canonical_version_id": None, "rejection_error_code": None}, "La conversion absente doit etre explicite.")
assert_equal(projection.status_code, 200, "La lecture de projection doit etre operationnelle.")
assert_equal(projection.json_body, {"document_id": document_id, "projection_status": "PROJECTION_NOT_REQUESTED", "projection_id": None, "canonical_version_id": None, "profile": None, "chunk_count": None}, "La projection absente doit etre explicite.")

# Then le PDF original est recupere par un contrat controle sans reference de stockage interne.
original = api.handle_get(path=f"/v1/documents/{document_id}/original")
assert_equal(original.status_code, 200, "Le PDF original doit etre recuperable.")
assert_equal(original.content_type, "application/pdf", "Le type MIME doit rester PDF.")
assert_equal(original.binary_body, pdf_content, "L'original doit etre restitue bit a bit.")
for payload in (listed.json_body, diagnosis.json_body, conversion.json_body, projection.json_body):
    if "original_storage_ref" in repr(payload):
        raise AssertionError("Une reference de stockage interne ne doit jamais etre exposee.")

print("Test d'acceptation raccordement contrats documentaires orchestrator-api: OK")
'@ | & (Join-Path $repoRoot ".venv/Scripts/python.exe") -

    if ($LASTEXITCODE -ne 0) {
        throw "Le test d'acceptation du raccordement documentaire a echoue."
    }
}
finally {
    Remove-Item Env:OST_REPO_ROOT -ErrorAction SilentlyContinue
    Remove-Item Env:OST_DOCUMENT_API_TEMP_ROOT -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force -ErrorAction SilentlyContinue
}
