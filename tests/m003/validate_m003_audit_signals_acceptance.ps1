$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$eAcute = [char] 0x00E9

$pythonCode = @'
from __future__ import annotations

import json
import sys

sys.path.insert(0, sys.argv[1])

from app.source_processing.application.audit_signals import (
    DocumentIngestionAuditEvent,
    SourceProcessingAuditLogEvent,
    SourceProcessingAuditSignalError,
    build_source_processing_audit_signals,
)
from app.source_processing.domain.document_processing_run import (
    DocumentProcessingRunStatus,
    PageRouteName,
    ProcessingRunId,
    RoutingPolicyVersion,
)
from app.source_processing.domain.source_document import DocumentId


DOCUMENT_CONTENT_CANARY = "CONTENU_INTEGRAL_DOCUMENT_M003_INTERDIT"
PAGE_TEXT_CANARY = "TEXTE_COMPLET_PAGE_M003_INTERDIT"


def assert_equal(actual, expected, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message} Obtenu: {actual!r}. Attendu: {expected!r}.")


def assert_error(expected_code: str, callback) -> None:
    try:
        callback()
    except SourceProcessingAuditSignalError as exc:
        if exc.code != expected_code:
            raise AssertionError(f"Code audit inattendu: {exc.code}, attendu: {expected_code}")
    else:
        raise AssertionError(f"Erreur audit attendue absente: {expected_code}")


def event(
    trace_id: str,
    document_id: str,
    run_id: str,
    route_name: PageRouteName | None,
    status: DocumentProcessingRunStatus | str,
    served_model: str,
    quarantined: bool,
    error_code: str | None,
) -> DocumentIngestionAuditEvent:
    return DocumentIngestionAuditEvent(
        trace_id=trace_id,
        document_id=DocumentId.from_value(document_id),
        processing_run_id=ProcessingRunId.from_value(run_id),
        phase="m003_source_routing",
        status=status,
        route_name=route_name,
        routing_policy_version=RoutingPolicyVersion.from_value("routing-v1"),
        served_model=served_model,
        page_count=3,
        latency_ms=25.5,
        quarantined=quarantined,
        error_code=error_code,
    )


# Given les comportements M-003 sont implémentés et testés.
# When les signaux d'audit de clôture sont produits.
# Then les métriques d'ingestion et logs d'audit sont présents sans contenu documentaire complet.
signals = build_source_processing_audit_signals(
    (
        event(
            "trace-m003-native",
            "DOC-M003-AUDIT-001",
            "RUN-M003-AUDIT-001",
            PageRouteName.NATIVE_STANDARD,
            DocumentProcessingRunStatus.ROUTE_PLANNED,
            "docling-standard",
            False,
            None,
        ),
        event(
            "trace-m003-granite",
            "DOC-M003-AUDIT-002",
            "RUN-M003-AUDIT-002",
            PageRouteName.SCAN_GRANITE,
            DocumentProcessingRunStatus.ROUTE_PLANNED,
            "granite-docling",
            False,
            None,
        ),
        event(
            "trace-m003-quarantine",
            "DOC-M003-AUDIT-003",
            "RUN-M003-AUDIT-003",
            None,
            DocumentProcessingRunStatus.QUARANTINED,
            "granite-docling",
            True,
            "UNSUPPORTED_OR_CORRUPT",
        ),
    )
)

log_mappings = [entry.to_mapping() for entry in signals.logs]
metric_mappings = [entry.to_mapping() for entry in signals.metrics]
serialized = json.dumps(
    {"logs": log_mappings, "metrics": metric_mappings},
    ensure_ascii=False,
    sort_keys=True,
)

for forbidden in (DOCUMENT_CONTENT_CANARY, PAGE_TEXT_CANARY, "original_content", "page_text", "document_content"):
    if forbidden in serialized:
        raise AssertionError(f"Contenu documentaire exposé dans l'audit M-003: {forbidden}")

assert_equal(len(log_mappings), 3, "Chaque document routé doit produire un log d'audit.")
for log_mapping in log_mappings:
    for required_field in (
        "trace_id",
        "document_id",
        "processing_run_id",
        "phase",
        "status",
        "routing_policy_version",
        "served_model",
        "page_count",
        "latency_ms",
        "quarantined",
        "error_code",
    ):
        if required_field not in log_mapping:
            raise AssertionError(f"Champ de log M-003 absent: {required_field}")
    if log_mapping["status"] == "ROUTE_PLANNED" and log_mapping["route_name"] is None:
        raise AssertionError("Un routage planifié doit exposer route_name.")
    if log_mapping["status"] == "QUARANTINED" and log_mapping["route_name"] is not None:
        raise AssertionError("Une quarantaine ne doit pas exposer de route fictive.")

metric_names = {metric["name"] for metric in metric_mappings}
assert_equal(
    metric_names,
    {"documents_par_route", "taux_quarantaine", "erreurs_par_modele"},
    "Les métriques M-003 obligatoires doivent être émises.",
)

documents_par_route = {
    metric["tags"]["route_name"]: metric["value"]
    for metric in metric_mappings
    if metric["name"] == "documents_par_route"
}
assert_equal(
    documents_par_route,
    {"NATIVE_STANDARD": 1.0, "SCAN_GRANITE": 1.0},
    "Le compteur documents_par_route doit agréger seulement les routes explicites.",
)

taux_quarantaine = [
    metric["value"]
    for metric in metric_mappings
    if metric["name"] == "taux_quarantaine"
]
assert_equal(taux_quarantaine, [1.0 / 3.0], "Le taux de quarantaine doit être calculé sur le lot audité.")

erreurs_par_modele = {
    (metric["tags"]["served_model"], metric["tags"]["error_code"]): metric["value"]
    for metric in metric_mappings
    if metric["name"] == "erreurs_par_modele"
}
assert_equal(
    erreurs_par_modele,
    {("granite-docling", "UNSUPPORTED_OR_CORRUPT"): 1.0},
    "Les erreurs par modèle doivent être agrégées sans contenu de document.",
)

assert_error("SP_AUDIT_EVENTS_REQUIRED", lambda: build_source_processing_audit_signals(()))
assert_error(
    "SP_AUDIT_ERROR_CODE_REQUIRED",
    lambda: event(
        "trace-m003-invalid",
        "DOC-M003-AUDIT-004",
        "RUN-M003-AUDIT-004",
        None,
        DocumentProcessingRunStatus.QUARANTINED,
        "granite-docling",
        True,
        None,
    ),
)
assert_error(
    "SP_AUDIT_ROUTE_REQUIRED",
    lambda: event(
        "trace-m003-route-missing",
        "DOC-M003-AUDIT-005",
        "RUN-M003-AUDIT-005",
        None,
        DocumentProcessingRunStatus.ROUTE_PLANNED,
        "granite-docling",
        False,
        None,
    ),
)
assert_error(
    "SP_AUDIT_ROUTE_FORBIDDEN",
    lambda: event(
        "trace-m003-route-forbidden",
        "DOC-M003-AUDIT-006",
        "RUN-M003-AUDIT-006",
        PageRouteName.SCAN_GRANITE,
        DocumentProcessingRunStatus.QUARANTINED,
        "granite-docling",
        True,
        "UNSUPPORTED_OR_CORRUPT",
    ),
)
assert_error(
    "SP_AUDIT_STATUS_INVALID",
    lambda: event(
        "trace-m003-status-invalid",
        "DOC-M003-AUDIT-007",
        "RUN-M003-AUDIT-007",
        PageRouteName.SCAN_GRANITE,
        "ROUTE_PLANEND",
        "granite-docling",
        False,
        None,
    ),
)

nominal_signals = build_source_processing_audit_signals(
    (
        event(
            "trace-m003-nominal-native",
            "DOC-M003-AUDIT-008",
            "RUN-M003-AUDIT-008",
            PageRouteName.NATIVE_STANDARD,
            DocumentProcessingRunStatus.ROUTE_PLANNED,
            "docling-standard",
            False,
            None,
        ),
    )
)
nominal_metric_names = {metric.name for metric in nominal_signals.metrics}
assert_equal(
    nominal_metric_names,
    {"documents_par_route", "taux_quarantaine"},
    "Un lot sans erreur ne doit pas exiger erreurs_par_modele.",
)

quarantine_only_signals = build_source_processing_audit_signals(
    (
        event(
            "trace-m003-quarantine-only",
            "DOC-M003-AUDIT-009",
            "RUN-M003-AUDIT-009",
            None,
            DocumentProcessingRunStatus.QUARANTINED,
            "granite-docling",
            True,
            "UNSUPPORTED_OR_CORRUPT",
        ),
    )
)
quarantine_only_metric_names = {metric.name for metric in quarantine_only_signals.metrics}
assert_equal(
    quarantine_only_metric_names,
    {"taux_quarantaine", "erreurs_par_modele"},
    "Un lot sans route ne doit pas exiger documents_par_route.",
)
assert_error(
    "SP_AUDIT_FIELD_NAME_FORBIDDEN",
    lambda: SourceProcessingAuditLogEvent(fields={"page_text": PAGE_TEXT_CANARY}),
)

print("Test d'acceptation signaux d'audit M-003: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m003_audit_signals_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation signaux d'audit M-003: OK"
