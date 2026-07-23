from __future__ import annotations

from pathlib import Path
import sys


def test_validate_review3_maintenance_acceptance() -> None:
    original_argv = sys.argv[:]
    repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    try:
        sys.argv = [str(Path(__file__)), str(repository_root)]
        source = 'from app.platform.job_runtime.postgres import _ClaimedJobRow, _JobRow\nfrom app.source_processing.adapters.postgres_document_persistence import (\n    _ManifestEntryRow,\n    _ProcessingRunRow,\n)\n\n_execution_requirement_fields = (\n    "execution_contract_name", "execution_contract_version", "capacity_capability",\n    "capacity_slots", "capacity_device", "storage_environment",\n    "source_artifact_ref", "result_artifact_ref", "execution_route_name",\n)\nassert _JobRow._fields == (\n    "sequence", "job_id", "environment", "deployment_id", "job_name", "priority", "input_hash",\n    "configuration_hash", "code_version", "model_version", *_execution_requirement_fields, "payload",\n    "status", "result", "failure_reason",\n)\nassert _ClaimedJobRow._fields == _JobRow._fields + (\n    "trace_id", "lease_owner", "lease_expires_at", "claim_generation",\n    "claim_token", "execution_attempts",\n)\nassert _ProcessingRunRow._fields == (\n    "processing_run_id", "document_id", "source_page_count", "status",\n    "manual_review_reason", "blocking_policy_version", "aggregate_version",\n    "failure_error_code",\n)\nassert _ManifestEntryRow._fields == ("page_number", "state")\n\n\ndef require_shape_error(factory, row):\n    try:\n        factory(row)\n    except RuntimeError as exc:\n        assert "SQL_ROW_SHAPE_INVALID" in str(exc), exc\n    else:\n        raise AssertionError("Une forme SQL divergente doit être refusée.")\n\n\nrequire_shape_error(_JobRow.from_database, tuple(range(20)))\nrequire_shape_error(_ClaimedJobRow.from_database, tuple(range(26)))\nrequire_shape_error(_ProcessingRunRow.from_database, tuple(range(7)))\nrequire_shape_error(_ManifestEntryRow.from_grouped, (1,))\nprint("DTO SQL nommés et formes strictes: OK")'
        namespace = {"__name__": __name__, "__file__": str(Path(__file__))}
        exec(compile(source, str(Path(__file__)), "exec"), namespace)
    finally:
        sys.argv = original_argv
