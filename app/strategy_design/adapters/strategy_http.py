"""Adaptateur HTTP public SD pour compilation et lecture de strategies."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from app.contracts.identity import DomainIdentifier
from app.strategy_design.application.compile_strategy_candidate import (
    CompileStrategyCandidateCommand,
)
from app.strategy_design.application.create_strategy_snapshot import (
    CreateStrategySnapshotCommand,
)
from app.strategy_design.domain.strategy_candidate import (
    CompilationDiagnostic,
    CompatibilityFindingCode,
    CompilationDiagnosticCode,
    StrategyCandidate,
    StrategyCandidateNotFoundError,
    StrategyCompilationResult,
    StrategyCompilationStatus,
)


_COMPILE_FIELDS = frozenset(
    {
        "strategy_id",
        "expected_version",
        "create_snapshot",
        "idempotency_key",
        "occurred_at",
        "snapshot_created_at",
        "correlation_id",
        "causation_id",
        "supersedes_snapshot_id",
    }
)
_COMPILE_BASE_FIELDS = frozenset(
    {
        "strategy_id",
        "expected_version",
        "create_snapshot",
        "idempotency_key",
        "occurred_at",
    }
)
_SNAPSHOT_REQUEST_FIELDS = frozenset(
    {
        "snapshot_created_at",
        "correlation_id",
        "causation_id",
        "supersedes_snapshot_id",
    }
)
_GET_BODY_FIELDS = frozenset()
_FORBIDDEN_BODY_FIELDS = frozenset(
    {
        "backtest_result",
        "backtest_result_override",
        "eg_registry_table",
        "internal_strategy_table",
        "market_price_override",
        "mutable_snapshot_payload",
        "mutable_strategy_state",
        "profitability",
        "profitability_claim",
        "prompt_override",
        "prompt_text",
        "qdrant_collection",
        "ra_repository_table",
        "raw_research_payload",
    }
)
_PUBLIC_DIAGNOSTIC_CODES = {
    CompilationDiagnosticCode.STRATEGY_RULE_REQUIRED.value: "STRATEGY_RULE_ORIGIN_MISSING",
    CompilationDiagnosticCode.RULE_ORIGIN_REQUIRED.value: "STRATEGY_RULE_ORIGIN_MISSING",
    CompilationDiagnosticCode.SOURCE_EVIDENCE_REQUIRED.value: "SOURCE_EVIDENCE_REQUIRED",
    CompilationDiagnosticCode.DESIGN_CHOICE_JUSTIFICATION_REQUIRED.value: (
        "DESIGN_CHOICE_JUSTIFICATION_REQUIRED"
    ),
    CompilationDiagnosticCode.STRATEGY_MANDATE_REQUIRED.value: "STRATEGY_MANDATE_REQUIRED",
    CompilationDiagnosticCode.PARAMETER_CALIBRATION_REQUIRED.value: (
        "PARAMETER_CALIBRATION_REQUIRED"
    ),
    CompilationDiagnosticCode.VALIDATION_PLAN_REQUIRED.value: "VALIDATION_PLAN_REQUIRED",
    CompilationDiagnosticCode.STRATEGY_CONFLICT_BLOCKING.value: (
        "STRATEGY_CONFLICT_UNRESOLVED"
    ),
    CompilationDiagnosticCode.STRATEGY_NOT_COMPILABLE.value: "STRATEGY_NOT_COMPILABLE",
    CompilationDiagnosticCode.RULE_EXPRESSION_INVALID.value: "RULE_EXPRESSION_INVALID",
    CompilationDiagnosticCode.RULE_NON_DETERMINISTIC.value: "RULE_NON_DETERMINISTIC",
    CompatibilityFindingCode.POINT_IN_TIME_VIOLATION.value: "CURRENT_DATA_REQUIRED",
    CompatibilityFindingCode.DATA_FREQUENCY_INCOMPATIBLE.value: (
        "STRATEGY_COMPATIBILITY_FAILED"
    ),
    CompatibilityFindingCode.CALENDAR_UNAVAILABLE.value: "STRATEGY_COMPATIBILITY_FAILED",
    CompatibilityFindingCode.IMPLICIT_COST_MODEL.value: "STRATEGY_COMPATIBILITY_FAILED",
    CompatibilityFindingCode.TURNOVER_CONSTRAINT_VIOLATION.value: (
        "STRATEGY_COMPATIBILITY_FAILED"
    ),
    CompatibilityFindingCode.LIQUIDITY_CONSTRAINT_VIOLATION.value: (
        "STRATEGY_COMPATIBILITY_FAILED"
    ),
    CompatibilityFindingCode.LEVERAGE_CONSTRAINT_VIOLATION.value: (
        "STRATEGY_COMPATIBILITY_FAILED"
    ),
    CompatibilityFindingCode.HORIZON_MISMATCH.value: "STRATEGY_COMPATIBILITY_FAILED",
    CompatibilityFindingCode.EVIDENCE_SCOPE_MISMATCH.value: (
        "STRATEGY_COMPATIBILITY_FAILED"
    ),
}
_PUBLIC_ERROR_STATUS = {
    "CURRENT_DATA_REQUIRED": 422,
    "DESIGN_CHOICE_JUSTIFICATION_REQUIRED": 422,
    "HTTP_REQUEST_INVALID": 400,
    "PARAMETER_CALIBRATION_REQUIRED": 422,
    "PUBLIC_STORAGE_FIELD_FORBIDDEN": 400,
    "RULE_EXPRESSION_INVALID": 422,
    "RULE_NON_DETERMINISTIC": 422,
    "SOURCE_EVIDENCE_REQUIRED": 422,
    "STRATEGY_COMPATIBILITY_FAILED": 409,
    "STRATEGY_CONFLICT_UNRESOLVED": 409,
    "STRATEGY_MANDATE_REQUIRED": 422,
    "STRATEGY_NOT_COMPILABLE": 409,
    "STRATEGY_RULE_ORIGIN_MISSING": 422,
    "VALIDATION_PLAN_REQUIRED": 422,
}
_GENERIC_REJECTION_CODE = "STRATEGY_NOT_COMPILABLE"


class CompileStrategyHandlerPort(Protocol):
    def handle(self, command: CompileStrategyCandidateCommand) -> StrategyCompilationResult:
        raise NotImplementedError


class StrategyRepositoryPort(Protocol):
    def get(self, strategy_id: str) -> StrategyCandidate:
        raise NotImplementedError


class StrategySnapshotHandlerPort(Protocol):
    def handle(self, command: CreateStrategySnapshotCommand) -> Any:
        raise NotImplementedError


class StrategySnapshotStorePort(Protocol):
    def snapshots(self) -> tuple[Any, ...]:
        raise NotImplementedError


@dataclass(frozen=True)
class HttpRequest:
    """Requete HTTP minimale pour tester le contrat sans framework."""

    method: str
    path: str
    body: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "method", _ensure_http_method(self.method))
        object.__setattr__(self, "path", _ensure_path(self.path))
        object.__setattr__(self, "body", _ensure_mapping(self.body, "body"))


@dataclass(frozen=True)
class HttpResponse:
    """Reponse HTTP minimale et stable pour le contrat public SD."""

    status_code: int
    body: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "status_code", _ensure_status_code(self.status_code))
        object.__setattr__(self, "body", _ensure_mapping(self.body, "body"))


class StrategyHttpRequestValidationError(ValueError):
    def __init__(self, *, error_code: str, field: str) -> None:
        self.error_code = _ensure_public_error_code(error_code)
        self.field = _ensure_text(field, "field")
        super().__init__(f"{self.error_code}: {self.field}")


@dataclass(frozen=True)
class CompileStrategyRequestDto:
    strategy_id: str
    expected_version: int
    create_snapshot: bool
    idempotency_key: str
    occurred_at: str
    snapshot_created_at: str | None
    correlation_id: str | None
    causation_id: str | None
    supersedes_snapshot_id: str | None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "CompileStrategyRequestDto":
        parsed = _ensure_mapping(payload, "body")
        _ensure_allowed_body_fields(parsed, _COMPILE_FIELDS)
        missing = _missing_field(parsed, _COMPILE_BASE_FIELDS)
        if missing is not None:
            raise StrategyHttpRequestValidationError(
                error_code="HTTP_REQUEST_INVALID",
                field=missing,
            )
        create_snapshot = _ensure_bool(parsed["create_snapshot"], "create_snapshot")
        snapshot_fields_present = frozenset(parsed.keys()) & _SNAPSHOT_REQUEST_FIELDS
        if create_snapshot:
            missing_snapshot_field = _missing_field(parsed, _SNAPSHOT_REQUEST_FIELDS)
            if missing_snapshot_field is not None:
                raise StrategyHttpRequestValidationError(
                    error_code="HTTP_REQUEST_INVALID",
                    field=missing_snapshot_field,
                )
        elif len(snapshot_fields_present) > 0:
            raise StrategyHttpRequestValidationError(
                error_code="HTTP_REQUEST_INVALID",
                field=sorted(snapshot_fields_present)[0],
            )
        return cls(
            strategy_id=parsed["strategy_id"],
            expected_version=parsed["expected_version"],
            create_snapshot=create_snapshot,
            idempotency_key=parsed["idempotency_key"],
            occurred_at=parsed["occurred_at"],
            snapshot_created_at=parsed.get("snapshot_created_at"),
            correlation_id=parsed.get("correlation_id"),
            causation_id=parsed.get("causation_id"),
            supersedes_snapshot_id=parsed.get("supersedes_snapshot_id"),
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "strategy_id", _ensure_strategy_id(self.strategy_id))
        object.__setattr__(
            self,
            "expected_version",
            _ensure_expected_version(self.expected_version),
        )
        if not isinstance(self.create_snapshot, bool):
            raise ValueError("create_snapshot non booleen")
        object.__setattr__(self, "idempotency_key", _ensure_text(self.idempotency_key, "idempotency_key"))
        object.__setattr__(self, "occurred_at", _ensure_utc_text(self.occurred_at, "occurred_at"))
        if self.create_snapshot:
            object.__setattr__(
                self,
                "snapshot_created_at",
                _ensure_utc_text(self.snapshot_created_at, "snapshot_created_at"),
            )
            object.__setattr__(self, "correlation_id", _ensure_text(self.correlation_id, "correlation_id"))
            object.__setattr__(self, "causation_id", _ensure_text(self.causation_id, "causation_id"))
            if self.supersedes_snapshot_id is not None:
                object.__setattr__(
                    self,
                    "supersedes_snapshot_id",
                    _ensure_strategy_version_id(self.supersedes_snapshot_id),
                )


class StrategyHttpAdapter:
    """Route explicitement les endpoints publics SD de strategie."""

    def __init__(
        self,
        *,
        compile_strategy_handler: CompileStrategyHandlerPort,
        strategy_repository: StrategyRepositoryPort,
        snapshot_handler: StrategySnapshotHandlerPort,
        snapshot_store: StrategySnapshotStorePort,
    ) -> None:
        if not callable(getattr(compile_strategy_handler, "handle", None)):
            raise ValueError("compile_strategy_handler sans handle")
        if not callable(getattr(strategy_repository, "get", None)):
            raise ValueError("strategy_repository sans get")
        if not callable(getattr(snapshot_handler, "handle", None)):
            raise ValueError("snapshot_handler sans handle")
        if not callable(getattr(snapshot_store, "snapshots", None)):
            raise ValueError("snapshot_store sans snapshots")
        self._compile_strategy_handler = compile_strategy_handler
        self._strategy_repository = strategy_repository
        self._snapshot_handler = snapshot_handler
        self._snapshot_store = snapshot_store

    def handle(self, request: HttpRequest) -> HttpResponse:
        parsed_request = _ensure_http_request(request)
        if parsed_request.method == "POST" and parsed_request.path == "/v1/strategies/compile":
            return self._handle_compile(parsed_request)

        strategy_id = _strategy_id_from_path(parsed_request.path)
        if parsed_request.method == "GET" and strategy_id is not None:
            return self._handle_read(strategy_id, parsed_request)

        return HttpResponse(
            status_code=404,
            body={"error_code": "ENDPOINT_NOT_FOUND", "path": parsed_request.path},
        )

    def _handle_compile(self, request: HttpRequest) -> HttpResponse:
        try:
            request_dto = CompileStrategyRequestDto.from_payload(request.body)
        except StrategyHttpRequestValidationError as exc:
            return _validation_error_response(exc)
        except ValueError:
            return _bad_request_response("body")

        try:
            result = self._compile_strategy_handler.handle(
                CompileStrategyCandidateCommand(
                    strategy_id=request_dto.strategy_id,
                    expected_version=request_dto.expected_version,
                )
            )
        except StrategyCandidateNotFoundError:
            return _strategy_not_found_response()
        except ValueError:
            return _bad_request_response("body")

        if not isinstance(result, StrategyCompilationResult):
            return HttpResponse(
                status_code=502,
                body={"error_code": "STRATEGY_COMPILATION_RESULT_INVALID"},
            )
        if result.compilation_status == StrategyCompilationStatus.REJECTED:
            return _compilation_rejected_response(result)

        body: dict[str, Any] = {
            "strategy_id": result.strategy_id,
            "strategy_version": result.strategy_version,
            "compilation_status": result.compilation_status,
            "diagnostics": (),
            "representation_ref": _representation_ref(result),
        }
        if request_dto.create_snapshot:
            try:
                snapshot_result = self._snapshot_handler.handle(
                    CreateStrategySnapshotCommand(
                        strategy_id=request_dto.strategy_id,
                        expected_version=request_dto.expected_version,
                        compilation_result=result,
                        created_at=_required_not_none(
                            request_dto.snapshot_created_at,
                            "snapshot_created_at",
                        ),
                        correlation_id=_required_not_none(
                            request_dto.correlation_id,
                            "correlation_id",
                        ),
                        causation_id=_required_not_none(
                            request_dto.causation_id,
                            "causation_id",
                        ),
                        supersedes_snapshot_id=request_dto.supersedes_snapshot_id,
                    )
                )
            except ValueError:
                return _public_error_response("STRATEGY_NOT_COMPILABLE")
            body["snapshot_ref"] = _snapshot_result_ref(snapshot_result)
        else:
            body["snapshot_ref"] = None
        return HttpResponse(status_code=202, body=body)

    def _handle_read(self, strategy_id: str, request: HttpRequest) -> HttpResponse:
        try:
            _ensure_allowed_body_fields(request.body, _GET_BODY_FIELDS)
        except StrategyHttpRequestValidationError as exc:
            return _validation_error_response(exc)

        try:
            candidate = self._strategy_repository.get(strategy_id)
        except StrategyCandidateNotFoundError:
            return _strategy_not_found_response()
        except ValueError:
            return _bad_request_response("strategy_id")

        return HttpResponse(
            status_code=200,
            body={
                "strategy_id": candidate.strategy_id,
                "latest_version": candidate.version,
                "strategy_status": candidate.status,
                "diagnostics": tuple(
                    _diagnostic_payload(diagnostic)
                    for diagnostic in candidate.compilation_diagnostics
                ),
                "rule_origin_summary": tuple(
                    _rule_origin_payload(rule)
                    for rule in sorted(candidate.rules, key=lambda current: current.rule_id)
                ),
                "snapshot_refs": _snapshot_refs_for_strategy(
                    candidate.strategy_id,
                    self._snapshot_store,
                ),
            },
        )


def _compilation_rejected_response(result: StrategyCompilationResult) -> HttpResponse:
    diagnostics = tuple(_diagnostic_payload(diagnostic) for diagnostic in result.diagnostics)
    error_code = _primary_public_error_code(diagnostics)
    return HttpResponse(
        status_code=_status_for_public_error(error_code),
        body={
            "error_code": error_code,
            "strategy_id": result.strategy_id,
            "strategy_version": result.strategy_version,
            "compilation_status": result.compilation_status,
            "diagnostics": diagnostics,
            "snapshot_ref": None,
        },
    )


def _representation_ref(result: StrategyCompilationResult) -> Mapping[str, Any]:
    if result.representation is None:
        raise ValueError("representation compilee absente")
    return {
        "strategy_id": result.strategy_id,
        "strategy_version": result.strategy_version,
        "representation_hash": result.representation.representation_hash,
    }


def _snapshot_result_ref(snapshot_result: Any) -> Mapping[str, Any]:
    snapshot_id = getattr(snapshot_result, "snapshot_id", None)
    snapshot_hash = getattr(snapshot_result, "snapshot_hash", None)
    return {
        "snapshot_id": _ensure_strategy_version_id(snapshot_id),
        "snapshot_hash": _ensure_hash_text(snapshot_hash, "snapshot_hash"),
    }


def _snapshot_refs_for_strategy(
    strategy_id: str,
    snapshot_store: StrategySnapshotStorePort,
) -> tuple[Mapping[str, Any], ...]:
    refs: list[Mapping[str, Any]] = []
    for record in snapshot_store.snapshots():
        snapshot = getattr(record, "snapshot", None)
        if getattr(snapshot, "strategy_id", None) == strategy_id:
            refs.append(
                {
                    "snapshot_id": snapshot.strategy_version_id,
                    "snapshot_hash": snapshot.spec_hash,
                    "created_at": snapshot.created_at,
                }
            )
    return tuple(sorted(refs, key=lambda ref: ref["snapshot_id"]))


def _rule_origin_payload(rule: Any) -> Mapping[str, Any]:
    origin = getattr(rule, "origin", None)
    payload: dict[str, Any] = {
        "rule_id": _ensure_text(getattr(rule, "rule_id", None), "rule_id"),
        "rule_kind": _ensure_text(getattr(rule, "rule_kind", None), "rule_kind"),
        "origin_type": None,
        "verified_claim_refs": (),
        "evidence_ref_count": 0,
    }
    if origin is not None:
        payload["origin_type"] = origin.origin_type.value
        payload["verified_claim_refs"] = tuple(
            str(claim_ref) for claim_ref in origin.verified_claim_refs
        )
        payload["evidence_ref_count"] = origin.evidence_ref_count
    return payload


def _diagnostic_payload(diagnostic: CompilationDiagnostic) -> Mapping[str, Any]:
    if not isinstance(diagnostic, CompilationDiagnostic):
        raise ValueError("CompilationDiagnostic attendu")
    payload: dict[str, Any] = {
        "error_code": _public_code_for_diagnostic(diagnostic),
        "source_code": _diagnostic_code_value(diagnostic.code),
        "blocking": diagnostic.blocking,
        "description": diagnostic.description,
    }
    if diagnostic.rule_id is not None:
        payload["rule_id"] = diagnostic.rule_id
    if diagnostic.parameter_id is not None:
        payload["parameter_id"] = diagnostic.parameter_id
    return payload


def _public_code_for_diagnostic(diagnostic: CompilationDiagnostic) -> str:
    source_code = _diagnostic_code_value(diagnostic.code)
    if source_code not in _PUBLIC_DIAGNOSTIC_CODES:
        raise ValueError(f"diagnostic public non mappe: {source_code}")
    return _PUBLIC_DIAGNOSTIC_CODES[source_code]


def _primary_public_error_code(diagnostics: tuple[Mapping[str, Any], ...]) -> str:
    if len(diagnostics) == 0:
        raise ValueError("diagnostic public requis")
    for diagnostic in diagnostics:
        error_code = _ensure_public_error_code(diagnostic["error_code"])
        if error_code != _GENERIC_REJECTION_CODE:
            return error_code
    return _ensure_public_error_code(diagnostics[0]["error_code"])


def _diagnostic_code_value(code: object) -> str:
    value = getattr(code, "value", code)
    return _ensure_text(value, "diagnostic code")


def _strategy_id_from_path(path: str) -> str | None:
    parsed_path = _ensure_path(path)
    prefix = "/v1/strategies/"
    if not parsed_path.startswith(prefix):
        return None
    suffix = parsed_path[len(prefix) :]
    if suffix == "" or "/" in suffix or suffix == "compile":
        return None
    return suffix


def _ensure_allowed_body_fields(
    body: Mapping[str, Any],
    allowed_fields: frozenset[str],
) -> None:
    actual_fields = frozenset(body.keys())
    if len(actual_fields & _FORBIDDEN_BODY_FIELDS) > 0:
        raise StrategyHttpRequestValidationError(
            error_code="PUBLIC_STORAGE_FIELD_FORBIDDEN",
            field="body",
        )
    if len(actual_fields - allowed_fields) > 0:
        raise StrategyHttpRequestValidationError(
            error_code="HTTP_REQUEST_INVALID",
            field="body",
        )


def _missing_field(body: Mapping[str, Any], expected_fields: frozenset[str]) -> str | None:
    missing = expected_fields - frozenset(body.keys())
    if len(missing) == 0:
        return None
    return sorted(missing)[0]


def _validation_error_response(exc: StrategyHttpRequestValidationError) -> HttpResponse:
    return HttpResponse(
        status_code=_status_for_public_error(exc.error_code),
        body={"error_code": exc.error_code, "field": exc.field},
    )


def _bad_request_response(field_name: str) -> HttpResponse:
    return HttpResponse(
        status_code=400,
        body={"error_code": "HTTP_REQUEST_INVALID", "field": field_name},
    )


def _strategy_not_found_response() -> HttpResponse:
    return HttpResponse(status_code=404, body={"error_code": "STRATEGY_NOT_FOUND"})


def _public_error_response(error_code: str) -> HttpResponse:
    return HttpResponse(
        status_code=_status_for_public_error(error_code),
        body={"error_code": error_code},
    )


def _status_for_public_error(error_code: str) -> int:
    parsed_error_code = _ensure_public_error_code(error_code)
    if parsed_error_code not in _PUBLIC_ERROR_STATUS:
        raise ValueError(f"statut public non mappe: {parsed_error_code}")
    return _PUBLIC_ERROR_STATUS[parsed_error_code]


def _ensure_http_request(value: object) -> HttpRequest:
    if not isinstance(value, HttpRequest):
        raise ValueError("requete HTTP invalide")
    return value


def _ensure_http_method(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("methode HTTP invalide")
    if value.strip() == "":
        raise ValueError("methode HTTP vide")
    if value != value.strip() or value != value.upper():
        raise ValueError("methode HTTP non normalisee")
    return value


def _ensure_path(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("chemin HTTP invalide")
    if value.strip() == "":
        raise ValueError("chemin HTTP vide")
    if value != value.strip() or not value.startswith("/"):
        raise ValueError("chemin HTTP invalide")
    return value


def _ensure_mapping(value: object, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    return dict(value)


def _ensure_status_code(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("status_code invalide")
    if value < 100 or value > 599:
        raise ValueError("status_code invalide")
    return value


def _ensure_strategy_id(value: object) -> str:
    text = _ensure_text(value, "strategy_id")
    try:
        return str(DomainIdentifier.parse_with_prefix(text, "STRAT"))
    except ValueError as exc:
        raise ValueError(f"strategy_id invalide: {exc}") from exc


def _ensure_strategy_version_id(value: object) -> str:
    text = _ensure_text(value, "strategy_version_id")
    try:
        return str(DomainIdentifier.parse_with_prefix(text, "SVER"))
    except ValueError as exc:
        raise ValueError(f"strategy_version_id invalide: {exc}") from exc


def _ensure_expected_version(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("expected_version non entier")
    if value < 0:
        raise ValueError("expected_version negatif")
    return value


def _ensure_bool(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} non booleen")
    return value


def _ensure_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_utc_text(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if len(text) != 20 or text[4] != "-" or text[7] != "-" or text[10] != "T" or text[19] != "Z":
        raise ValueError(f"{field_name} invalide")
    return text


def _ensure_public_error_code(value: object) -> str:
    return _ensure_text(value, "error_code")


def _ensure_hash_text(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if len(text) not in {32, 64}:
        raise ValueError(f"{field_name} invalide")
    int(text, 16)
    return text


def _required_not_none(value: str | None, field_name: str) -> str:
    if value is None:
        raise ValueError(f"{field_name} absent")
    return value


__all__ = [
    "CompileStrategyHandlerPort",
    "CompileStrategyRequestDto",
    "HttpRequest",
    "HttpResponse",
    "StrategyHttpAdapter",
    "StrategyHttpRequestValidationError",
    "StrategyRepositoryPort",
    "StrategySnapshotHandlerPort",
    "StrategySnapshotStorePort",
]
