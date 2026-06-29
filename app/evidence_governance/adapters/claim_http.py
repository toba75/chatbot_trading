"""Adaptateur HTTP public pour les commandes EG de claims."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.contracts.identity import DomainIdentifier
from app.contracts.source_references import SourceLocator, SourceLocatorValidationPolicy
from app.evidence_governance.application.extract_claims import (
    ExtractClaimsFromEvidenceCommand,
    ClaimExtractionResult,
)
from app.evidence_governance.application.verify_claim import (
    SubmitClaimForVerification,
    VerifyClaimResult,
)
from app.evidence_governance.domain.claim_evidence import Claim, ClaimStatus, CanonicalEvidenceSpan


_EXTRACT_BODY_FIELDS = frozenset(
    {
        "evidence_candidates",
        "extraction_schema_version",
        "requested_by_context",
        "idempotency_key",
        "occurred_at",
    }
)
_VERIFY_BODY_FIELDS = frozenset(
    {
        "verification_policy_version",
        "verifier_profile_id",
        "idempotency_key",
        "occurred_at",
    }
)
_EVIDENCE_CANDIDATE_FIELDS = frozenset(
    {
        "chunk_id",
        "text",
        "source_locator",
        "content_hash",
    }
)
_EXPLICITLY_FORBIDDEN_EXTRACT_FIELDS = frozenset(
    {
        "prompt_override",
        "verified_state",
        "qdrant_collection",
    }
)
_EXPLICITLY_FORBIDDEN_VERIFY_FIELDS = frozenset(
    {
        "verdict_override",
        "calibrated_score_as_verdict",
        "qdrant_point_id",
    }
)
_PUBLIC_CLAIM_STATUSES = frozenset(
    {
        ClaimStatus.VERIFIED,
        ClaimStatus.REJECTED,
        ClaimStatus.SUPERSEDED,
    }
)


class ExtractClaimsHandlerPort(Protocol):
    """Port applicatif d'extraction appele par l'adaptateur."""

    def extract(self, command: ExtractClaimsFromEvidenceCommand) -> ClaimExtractionResult:
        """Execute la commande d'extraction EG."""


class VerifyClaimHandlerPort(Protocol):
    """Port applicatif de verification appele par l'adaptateur."""

    def verify(self, command: SubmitClaimForVerification) -> VerifyClaimResult:
        """Execute la commande de verification EG."""


class ClaimReaderPort(Protocol):
    """Port de lecture publique de claims EG."""

    def read_claim(self, claim_id: str) -> Claim:
        """Retourne le claim consultable par identifiant."""


class CanonicalEvidenceReaderPort(Protocol):
    """Port de resolution publique des preuves EG."""

    def resolve(self, source_locator: SourceLocator) -> CanonicalEvidenceSpan:
        """Retourne le span canonique associe au SourceLocator."""


class ClaimHttpRequestValidationError(ValueError):
    """Erreur de validation transport avec champ public stable."""

    def __init__(self, message: str, *, field: str) -> None:
        self.field = _ensure_text(field, "field")
        super().__init__(message)


@dataclass(frozen=True)
class HttpRequest:
    """Requete HTTP minimale et testable sans framework."""

    method: str
    path: str
    body: Mapping[str, Any]
    authenticated_context: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "method", _ensure_http_method(self.method))
        object.__setattr__(self, "path", _ensure_path(self.path))
        object.__setattr__(self, "body", _ensure_mapping(self.body, "body"))
        object.__setattr__(
            self,
            "authenticated_context",
            _ensure_authenticated_context(self.authenticated_context),
        )


@dataclass(frozen=True)
class HttpResponse:
    """Reponse HTTP minimale et stable pour le contrat EG."""

    status_code: int
    body: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "status_code", _ensure_status_code(self.status_code))
        object.__setattr__(self, "body", _ensure_mapping(self.body, "body"))


@dataclass(frozen=True)
class EvidenceCandidateDto:
    """DTO public de preuve candidate consommee par l'extraction EG."""

    chunk_id: str
    text: str
    source_locator: SourceLocator
    content_hash: str

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        source_locator_validation_policy: SourceLocatorValidationPolicy,
    ) -> "EvidenceCandidateDto":
        parsed_payload = _ensure_mapping(payload, "evidence_candidate")
        _ensure_allowed_fields(parsed_payload, _EVIDENCE_CANDIDATE_FIELDS, "evidence_candidate")
        if "source_locator" not in parsed_payload:
            raise ClaimHttpRequestValidationError("source_locator absent", field="source_locator")
        raw_locator = parsed_payload["source_locator"]
        if not isinstance(raw_locator, Mapping):
            raise ClaimHttpRequestValidationError("source_locator non objet", field="source_locator")
        try:
            source_locator = SourceLocator.from_payload(
                raw_locator,
                validation_policy=source_locator_validation_policy,
            )
        except ValueError as exc:
            raise ClaimHttpRequestValidationError("source_locator non resolvable", field="source_locator") from exc
        return cls(
            chunk_id=_required_text(parsed_payload, "chunk_id"),
            text=_required_text(parsed_payload, "text"),
            source_locator=source_locator,
            content_hash=_required_text(parsed_payload, "content_hash"),
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "chunk_id", _ensure_chunk_id(self.chunk_id))
        object.__setattr__(self, "text", _ensure_text(self.text, "text"))
        if not isinstance(self.source_locator, SourceLocator):
            raise ValueError("source_locator invalide")
        object.__setattr__(self, "content_hash", _ensure_text(self.content_hash, "content_hash"))
        if self.content_hash != self.source_locator.content_hash:
            raise ValueError("content_hash incoherent avec SourceLocator")


@dataclass(frozen=True)
class ClaimExtractionRequestDto:
    """DTO public de requete `POST /v1/claims/extract`."""

    evidence_candidates: tuple[EvidenceCandidateDto, ...]
    extraction_schema_version: str
    requested_by_context: str
    idempotency_key: str
    occurred_at: str

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        source_locator_validation_policy: SourceLocatorValidationPolicy,
    ) -> "ClaimExtractionRequestDto":
        _ensure_source_locator_validation_policy(source_locator_validation_policy)
        parsed_payload = _ensure_mapping(payload, "body")
        actual_fields = frozenset(parsed_payload.keys())
        if len(actual_fields & _EXPLICITLY_FORBIDDEN_EXTRACT_FIELDS) > 0:
            raise ClaimHttpRequestValidationError("body champ interdit", field="body")
        _ensure_allowed_fields(parsed_payload, _EXTRACT_BODY_FIELDS, "body")
        _ensure_required_fields(parsed_payload, _EXTRACT_BODY_FIELDS)
        return cls(
            evidence_candidates=_evidence_candidates_from_payload(
                parsed_payload["evidence_candidates"],
                source_locator_validation_policy=source_locator_validation_policy,
            ),
            extraction_schema_version=parsed_payload["extraction_schema_version"],
            requested_by_context=parsed_payload["requested_by_context"],
            idempotency_key=parsed_payload["idempotency_key"],
            occurred_at=parsed_payload["occurred_at"],
        )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "evidence_candidates",
            _ensure_evidence_candidate_dtos(self.evidence_candidates),
        )
        object.__setattr__(
            self,
            "extraction_schema_version",
            _ensure_text(self.extraction_schema_version, "extraction_schema_version"),
        )
        object.__setattr__(
            self,
            "requested_by_context",
            _ensure_text(self.requested_by_context, "requested_by_context"),
        )
        object.__setattr__(self, "idempotency_key", _ensure_text(self.idempotency_key, "idempotency_key"))
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))

    def to_command(self) -> ExtractClaimsFromEvidenceCommand:
        return ExtractClaimsFromEvidenceCommand(
            evidence_candidates=self.evidence_candidates,
            extraction_schema_version=self.extraction_schema_version,
            requested_by_context=self.requested_by_context,
            idempotency_key=self.idempotency_key,
            occurred_at=self.occurred_at,
        )


@dataclass(frozen=True)
class ClaimVerificationRequestDto:
    """DTO public de requete `POST /v1/claims/{claim_id}/verify`."""

    verification_policy_version: str
    verifier_profile_id: str
    idempotency_key: str
    occurred_at: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ClaimVerificationRequestDto":
        parsed_payload = _ensure_mapping(payload, "body")
        actual_fields = frozenset(parsed_payload.keys())
        if len(actual_fields & _EXPLICITLY_FORBIDDEN_VERIFY_FIELDS) > 0:
            raise ClaimHttpRequestValidationError("body champ interdit", field="body")
        _ensure_allowed_fields(parsed_payload, _VERIFY_BODY_FIELDS, "body")
        _ensure_required_fields(parsed_payload, _VERIFY_BODY_FIELDS)
        return cls(
            verification_policy_version=parsed_payload["verification_policy_version"],
            verifier_profile_id=parsed_payload["verifier_profile_id"],
            idempotency_key=parsed_payload["idempotency_key"],
            occurred_at=parsed_payload["occurred_at"],
        )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "verification_policy_version",
            _ensure_text(self.verification_policy_version, "verification_policy_version"),
        )
        object.__setattr__(
            self,
            "verifier_profile_id",
            _ensure_text(self.verifier_profile_id, "verifier_profile_id"),
        )
        object.__setattr__(self, "idempotency_key", _ensure_text(self.idempotency_key, "idempotency_key"))
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))

    def to_command(self, *, claim_id: str) -> SubmitClaimForVerification:
        parsed_claim_id = _ensure_claim_id(claim_id)
        return SubmitClaimForVerification(
            claim_id=parsed_claim_id,
            verification_case_id=_verification_case_id_for(
                claim_id=parsed_claim_id,
                verification_policy_version=self.verification_policy_version,
                verifier_profile_id=self.verifier_profile_id,
                idempotency_key=self.idempotency_key,
            ),
            verification_policy_version=self.verification_policy_version,
            verifier_profile_id=self.verifier_profile_id,
            occurred_at=self.occurred_at,
        )


class ClaimHttpAdapter:
    """Route explicitement les endpoints publics EG de claims."""

    def __init__(
        self,
        *,
        extract_claims_handler: ExtractClaimsHandlerPort,
        verify_claim_handler: VerifyClaimHandlerPort,
        claim_reader: ClaimReaderPort,
        canonical_evidence_reader: CanonicalEvidenceReaderPort,
        source_locator_validation_policy: SourceLocatorValidationPolicy,
    ) -> None:
        if not callable(getattr(extract_claims_handler, "extract", None)):
            raise ValueError("extract_claims_handler sans extract")
        if not callable(getattr(verify_claim_handler, "verify", None)):
            raise ValueError("verify_claim_handler sans verify")
        if not callable(getattr(claim_reader, "read_claim", None)):
            raise ValueError("claim_reader sans read_claim")
        if not callable(getattr(canonical_evidence_reader, "resolve", None)):
            raise ValueError("canonical_evidence_reader sans resolve")
        _ensure_source_locator_validation_policy(source_locator_validation_policy)
        self._extract_claims_handler = extract_claims_handler
        self._verify_claim_handler = verify_claim_handler
        self._claim_reader = claim_reader
        self._canonical_evidence_reader = canonical_evidence_reader
        self._source_locator_validation_policy = source_locator_validation_policy

    def handle(self, request: HttpRequest) -> HttpResponse:
        parsed_request = _ensure_http_request(request)
        if parsed_request.method == "POST" and parsed_request.path == "/v1/claims/extract":
            return self._handle_extract(parsed_request)

        verify_claim_id = _claim_id_from_verify_path(parsed_request.path)
        if parsed_request.method == "POST" and verify_claim_id is not None:
            return self._handle_verify(parsed_request, verify_claim_id)

        evidence_claim_id = _claim_id_from_evidence_path(parsed_request.path)
        if parsed_request.method == "GET" and evidence_claim_id is not None:
            return self._handle_read_evidence(evidence_claim_id)

        read_claim_id = _claim_id_from_read_path(parsed_request.path)
        if parsed_request.method == "GET" and read_claim_id is not None:
            return self._handle_read_claim(read_claim_id)

        return HttpResponse(
            status_code=404,
            body={"error_code": "ENDPOINT_NOT_FOUND", "path": parsed_request.path},
        )

    def _handle_extract(self, request: HttpRequest) -> HttpResponse:
        try:
            request_dto = ClaimExtractionRequestDto.from_payload(
                request.body,
                source_locator_validation_policy=self._source_locator_validation_policy,
            )
            result = self._extract_claims_handler.extract(request_dto.to_command())
        except ClaimHttpRequestValidationError as exc:
            if exc.field == "source_locator":
                return _public_error_response("CLAIM_EVIDENCE_SOURCE_UNRESOLVABLE", 422)
            return _bad_request_response(exc.field)
        except ValueError as exc:
            return _domain_error_response(exc)

        return HttpResponse(
            status_code=202,
            body={
                "request_id": _request_id_for(request_dto.idempotency_key),
                "draft_claims": tuple(_draft_claim_payload(draft) for draft in result.draft_claims),
                "rejected_candidates": (),
                "trace_id": _trace_id_for(request_dto.idempotency_key),
            },
        )

    def _handle_verify(self, request: HttpRequest, claim_id: str) -> HttpResponse:
        try:
            request_dto = ClaimVerificationRequestDto.from_payload(request.body)
            parsed_claim_id = _ensure_claim_id(claim_id)
            self._read_claim(parsed_claim_id)
            result = self._verify_claim_handler.verify(request_dto.to_command(claim_id=parsed_claim_id))
        except ClaimHttpRequestValidationError as exc:
            return _bad_request_response(exc.field)
        except ValueError as exc:
            return _domain_error_response(exc)

        decision = result.verification_case.decision
        if decision is None:
            return _public_error_response("CLAIM_STATE_INVALID", 409)
        return HttpResponse(
            status_code=200,
            body={
                "status": result.status,
                "claim_id": result.claim.claim_id,
                "claim_version": result.claim.claim_version,
                "verification_case_id": result.verification_case.verification_case_id,
                "state": result.claim.status.value,
                "verdict": decision.verdict.value,
                "reason_codes": tuple(reason_code.value for reason_code in decision.reason_codes),
                "verified_claim_ref": _optional_verified_claim_ref_payload(result.verified_claim_ref),
            },
        )

    def _handle_read_claim(self, claim_id: str) -> HttpResponse:
        try:
            claim = self._read_claim(claim_id)
            _ensure_claim_publication_allowed(claim)
        except ValueError as exc:
            return _domain_error_response(exc)

        return HttpResponse(
            status_code=200,
            body={
                "claim_id": claim.claim_id,
                "claim_version": claim.claim_version,
                "state": claim.status.value,
                "canonical_proposition": {
                    "text": claim.canonical_proposition.text,
                    "hash": _sha256_text(claim.canonical_proposition.text),
                },
                "scope": claim.scope.to_payload(),
                "superseded_by": None if claim.superseded_by is None else claim.superseded_by.to_payload(),
                "verified_claim_ref": _optional_verified_claim_ref_payload(claim.verified_claim_ref),
            },
        )

    def _handle_read_evidence(self, claim_id: str) -> HttpResponse:
        try:
            claim = self._read_claim(claim_id)
            _ensure_claim_publication_allowed(claim)
            if claim.verified_claim_ref is None:
                return _public_error_response("CLAIM_EVIDENCE_REQUIRED", 422)
            for association in claim.evidence_associations:
                canonical_span = self._canonical_evidence_reader.resolve(association.source_locator)
                if not isinstance(canonical_span, CanonicalEvidenceSpan):
                    return _public_error_response("CLAIM_EVIDENCE_SOURCE_UNRESOLVABLE", 422)
                if canonical_span.source_locator != association.source_locator:
                    return _public_error_response("CLAIM_EVIDENCE_SOURCE_UNRESOLVABLE", 422)
                if canonical_span.quoted_span_hash != association.quoted_span_hash:
                    return _public_error_response("CLAIM_EVIDENCE_SOURCE_UNRESOLVABLE", 422)
        except ValueError as exc:
            return _domain_error_response(exc)

        return HttpResponse(
            status_code=200,
            body={
                "claim_id": claim.claim_id,
                "claim_version": claim.claim_version,
                "evidence_refs": tuple(
                    association.evidence_ref.to_payload() for association in claim.evidence_associations
                ),
                "dependency_groups": claim.verified_claim_ref.dependency_group_ids,
                "verification_cases": (claim.accepted_verification_id,),
            },
        )

    def _read_claim(self, claim_id: str) -> Claim:
        claim = self._claim_reader.read_claim(_ensure_claim_id(claim_id))
        if not isinstance(claim, Claim):
            raise ValueError("claim invalide")
        return claim


def _evidence_candidates_from_payload(
    value: Any,
    *,
    source_locator_validation_policy: SourceLocatorValidationPolicy,
) -> tuple[EvidenceCandidateDto, ...]:
    if value is None:
        raise ClaimHttpRequestValidationError("evidence_candidates absent", field="evidence_candidates")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ClaimHttpRequestValidationError("evidence_candidates invalides", field="evidence_candidates")
    candidates = tuple(
        EvidenceCandidateDto.from_payload(
            item,
            source_locator_validation_policy=source_locator_validation_policy,
        )
        for item in value
    )
    if len(candidates) == 0:
        raise ClaimHttpRequestValidationError("evidence_candidates absents", field="evidence_candidates")
    return candidates


def _ensure_evidence_candidate_dtos(
    value: Sequence[EvidenceCandidateDto],
) -> tuple[EvidenceCandidateDto, ...]:
    if value is None:
        raise ClaimHttpRequestValidationError("evidence_candidates absents", field="evidence_candidates")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ClaimHttpRequestValidationError("evidence_candidates invalides", field="evidence_candidates")
    candidates = tuple(value)
    if len(candidates) == 0:
        raise ClaimHttpRequestValidationError("evidence_candidates absents", field="evidence_candidates")
    chunk_ids = tuple(candidate.chunk_id for candidate in candidates)
    if len(chunk_ids) != len(set(chunk_ids)):
        raise ClaimHttpRequestValidationError("evidence_candidates dupliques", field="evidence_candidates")
    for candidate in candidates:
        if not isinstance(candidate, EvidenceCandidateDto):
            raise ClaimHttpRequestValidationError("evidence_candidate invalide", field="evidence_candidates")
    return candidates


def _draft_claim_payload(draft: Any) -> dict[str, Any]:
    return {
        "claim_id": draft.claim_id,
        "claim_version": draft.claim_version,
        "state": draft.status.value,
        "canonical_proposition": {
            "text": draft.canonical_proposition.text,
            "hash": draft.proposition_hash,
        },
        "scope": draft.scope.to_payload(),
        "evidence_span": draft.evidence_span.to_payload(),
    }


def _optional_verified_claim_ref_payload(value: Any) -> Mapping[str, Any] | None:
    if value is None:
        return None
    return value.to_payload()


def _ensure_claim_publication_allowed(claim: Claim) -> None:
    if claim.status not in _PUBLIC_CLAIM_STATUSES:
        raise ValueError("CLAIM_PUBLICATION_FORBIDDEN")


def _domain_error_response(exc: ValueError) -> HttpResponse:
    message = str(exc)
    if "claim inconnu" in message:
        claim_id = _claim_id_from_error_message(message)
        body: dict[str, Any] = {"error_code": "CLAIM_NOT_FOUND"}
        if claim_id is not None:
            body["claim_id"] = claim_id
        return HttpResponse(status_code=404, body=body)
    if "source_locator" in message or "SourceLocator" in message or "quoted_span_hash incoherent" in message:
        return _public_error_response("CLAIM_EVIDENCE_SOURCE_UNRESOLVABLE", 422)
    if "CLAIM_SCOPE_EXCEEDS_EVIDENCE" in message:
        return _public_error_response("CLAIM_SCOPE_EXCEEDS_EVIDENCE", 422)
    if "INSUFFICIENT_DIRECT_EVIDENCE" in message:
        return _public_error_response("INSUFFICIENT_DIRECT_EVIDENCE", 422)
    if "CLAIM_VERIFICATION_POLICY_MISSING" in message:
        return _public_error_response("CLAIM_VERIFICATION_POLICY_MISSING", 422)
    if "CLAIM_PUBLICATION_FORBIDDEN" in message:
        return _public_error_response("CLAIM_PUBLICATION_FORBIDDEN", 409)
    if "transition claim interdite" in message:
        return _public_error_response("CLAIM_STATE_INVALID", 409)
    return _bad_request_response("body")


def _claim_id_from_error_message(message: str) -> str | None:
    match = re.search(r"(CLM-[A-Z0-9][A-Z0-9-]*)", message)
    if match is None:
        return None
    return match.group(1)


def _public_error_response(error_code: str, status_code: int) -> HttpResponse:
    return HttpResponse(status_code=status_code, body={"error_code": error_code})


def _bad_request_response(field_name: str) -> HttpResponse:
    return HttpResponse(
        status_code=400,
        body={"error_code": "HTTP_REQUEST_INVALID", "field": field_name},
    )


def _claim_id_from_verify_path(path: str) -> str | None:
    parsed_path = _ensure_path(path)
    prefix = "/v1/claims/"
    suffix = "/verify"
    if not parsed_path.startswith(prefix) or not parsed_path.endswith(suffix):
        return None
    claim_id = parsed_path[len(prefix) : -len(suffix)]
    if "/" in claim_id or claim_id == "":
        return None
    return claim_id


def _claim_id_from_evidence_path(path: str) -> str | None:
    parsed_path = _ensure_path(path)
    prefix = "/v1/claims/"
    suffix = "/evidence"
    if not parsed_path.startswith(prefix) or not parsed_path.endswith(suffix):
        return None
    claim_id = parsed_path[len(prefix) : -len(suffix)]
    if "/" in claim_id or claim_id == "":
        return None
    return claim_id


def _claim_id_from_read_path(path: str) -> str | None:
    parsed_path = _ensure_path(path)
    prefix = "/v1/claims/"
    if not parsed_path.startswith(prefix):
        return None
    claim_id = parsed_path[len(prefix) :]
    if "/" in claim_id or claim_id == "":
        return None
    return claim_id


def _verification_case_id_for(
    *,
    claim_id: str,
    verification_policy_version: str,
    verifier_profile_id: str,
    idempotency_key: str,
) -> str:
    seed = "|".join(
        (
            _ensure_claim_id(claim_id),
            _ensure_text(verification_policy_version, "verification_policy_version"),
            _ensure_text(verifier_profile_id, "verifier_profile_id"),
            _ensure_text(idempotency_key, "idempotency_key"),
        )
    )
    return f"VER-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:24].upper()}"


def _request_id_for(idempotency_key: str) -> str:
    return f"REQ-{hashlib.sha256(_ensure_text(idempotency_key, 'idempotency_key').encode('utf-8')).hexdigest()[:24].upper()}"


def _trace_id_for(idempotency_key: str) -> str:
    return f"TRC-{hashlib.sha256(('trace|' + _ensure_text(idempotency_key, 'idempotency_key')).encode('utf-8')).hexdigest()[:24].upper()}"


def _ensure_http_request(value: HttpRequest) -> HttpRequest:
    if not isinstance(value, HttpRequest):
        raise ValueError("requete HTTP invalide")
    return value


def _ensure_http_method(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("methode HTTP invalide")
    if value.strip() == "":
        raise ValueError("methode HTTP vide")
    if value != value.strip():
        raise ValueError("methode HTTP non normalisee")
    if value != value.upper():
        raise ValueError("methode HTTP non normalisee")
    return value


def _ensure_path(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("chemin HTTP invalide")
    if value.strip() == "":
        raise ValueError("chemin HTTP vide")
    if value != value.strip():
        raise ValueError("chemin HTTP non normalise")
    if not value.startswith("/"):
        raise ValueError("chemin HTTP invalide")
    return value


def _ensure_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ClaimHttpRequestValidationError(f"{field_name} non objet", field=field_name)
    return dict(value)


def _ensure_status_code(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("status_code invalide")
    if value < 100 or value > 599:
        raise ValueError("status_code invalide")
    return value


def _ensure_authenticated_context(value: Any) -> str:
    text = _ensure_text(value, "authenticated_context")
    if text not in {"EG", "RA", "SD"}:
        raise ValueError("authenticated_context inconnu")
    return text


def _ensure_source_locator_validation_policy(value: Any) -> None:
    if not isinstance(value, SourceLocatorValidationPolicy):
        raise ValueError("source_locator_validation_policy invalide")


def _ensure_allowed_fields(payload: Mapping[str, Any], allowed_fields: frozenset[str], label: str) -> None:
    unexpected_fields = frozenset(payload.keys()) - allowed_fields
    if len(unexpected_fields) > 0:
        raise ClaimHttpRequestValidationError(
            f"{label} champ interdit: {sorted(unexpected_fields)[0]}",
            field=label,
        )


def _ensure_required_fields(payload: Mapping[str, Any], required_fields: frozenset[str]) -> None:
    missing_fields = required_fields - frozenset(payload.keys())
    if len(missing_fields) > 0:
        missing_field = sorted(missing_fields)[0]
        raise ClaimHttpRequestValidationError(f"{missing_field} absent", field=missing_field)


def _required_text(payload: Mapping[str, Any], field_name: str) -> str:
    if field_name not in payload:
        raise ClaimHttpRequestValidationError(f"{field_name} absent", field=field_name)
    return _ensure_text(payload[field_name], field_name)


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ClaimHttpRequestValidationError(f"{field_name} non textuel", field=field_name)
    if value.strip() == "":
        raise ClaimHttpRequestValidationError(f"{field_name} vide", field=field_name)
    if value != value.strip():
        raise ClaimHttpRequestValidationError(f"{field_name} non normalise", field=field_name)
    return value


def _ensure_chunk_id(value: Any) -> str:
    text = _ensure_text(value, "chunk_id")
    if not text.startswith("KCHK-"):
        raise ClaimHttpRequestValidationError("chunk_id invalide", field="chunk_id")
    return text


def _ensure_claim_id(value: Any) -> str:
    try:
        return str(DomainIdentifier.parse_with_prefix(_ensure_text(value, "claim_id"), "CLM"))
    except ValueError as exc:
        raise ClaimHttpRequestValidationError("claim_id invalide", field="claim_id") from exc


def _ensure_utc_instant(value: Any, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", text) is None:
        raise ClaimHttpRequestValidationError(f"{field_name} invalide", field=field_name)
    return text


def _sha256_text(value: str) -> str:
    return hashlib.sha256(_ensure_text(value, "text").encode("utf-8")).hexdigest()


__all__ = [
    "ClaimExtractionRequestDto",
    "ClaimHttpAdapter",
    "ClaimHttpRequestValidationError",
    "ClaimVerificationRequestDto",
    "HttpRequest",
    "HttpResponse",
]
