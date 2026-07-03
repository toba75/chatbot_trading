"""Résolution RA des dépendances de claims vérifiés."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.contracts.evidence_claims import EvidenceRef
from app.research_answering.domain.evidence_set import EvidenceSet
from app.research_answering.domain.research_case import ResearchCase


_UTC_INSTANT_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_CLAIM_ID_PATTERN = re.compile(r"^CLM-[A-Z0-9][A-Z0-9-]*$")
_EVIDENCE_ID_PATTERN = re.compile(r"^EVS-[A-Z0-9][A-Z0-9-]*$")
_DEPENDENCY_GROUP_ID_PATTERN = re.compile(r"^DEP-[A-Z0-9][A-Z0-9-]*$")
_VERIFICATION_CASE_ID_PATTERN = re.compile(r"^VER-[A-Z0-9][A-Z0-9-]*$")
_RESEARCH_CASE_ID_PATTERN = re.compile(r"^RSC-[A-Z0-9][A-Z0-9-]*$")


class PublicVerifiedClaimEvidenceCatalog(Protocol):
    """Port RA vers la lecture publique des preuves de claim EG."""

    def read_evidence(self, claim_id: str, claim_version: int) -> object:
        """Retourne le claim et ses preuves publiques publiées par EG."""


class ResearchCaseRepository(Protocol):
    """Port RA de persistance du ResearchCase après résolution EG."""

    def case_for_id(self, research_case_id: str) -> ResearchCase:
        """Retourne le cas de recherche existant."""

    def update(self, research_case: ResearchCase) -> ResearchCase:
        """Remplace le cas de recherche par sa nouvelle version métier."""


@dataclass(frozen=True)
class ResolveVerifiedClaimDependenciesCommand:
    """Commande RA de résolution des dépendances d'un EvidenceSet approfondi."""

    evidence_set: EvidenceSet
    occurred_at: str

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_set, EvidenceSet):
            raise ValueError("evidence_set invalide")
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at))


@dataclass(frozen=True)
class VerifiedClaimDependency:
    """Dépendance RA résolue pour une version de claim vérifiée."""

    claim_id: str
    claim_version: int
    verification_case_id: str
    accepted_evidence_ids: Sequence[str]
    dependency_group_ids: Sequence[str]
    independent_confirmation_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", _ensure_claim_id(self.claim_id))
        object.__setattr__(self, "claim_version", _ensure_claim_version(self.claim_version))
        object.__setattr__(
            self,
            "verification_case_id",
            _ensure_verification_case_id(self.verification_case_id),
        )
        object.__setattr__(
            self,
            "accepted_evidence_ids",
            _ensure_evidence_ids(self.accepted_evidence_ids),
        )
        object.__setattr__(
            self,
            "dependency_group_ids",
            _ensure_dependency_group_ids(self.dependency_group_ids),
        )
        object.__setattr__(
            self,
            "independent_confirmation_count",
            _ensure_non_negative_integer(
                self.independent_confirmation_count,
                "independent_confirmation_count",
            ),
        )
        if self.independent_confirmation_count != len(self.dependency_group_ids):
            raise ValueError("confirmation independante incoherente")

    @property
    def verified_claim_version_ref(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "claim_version": self.claim_version,
            "verification_case_id": self.verification_case_id,
        }

    def to_payload(self) -> dict[str, object]:
        return {
            **self.verified_claim_version_ref,
            "accepted_evidence_ids": self.accepted_evidence_ids,
            "dependency_group_ids": self.dependency_group_ids,
            "independent_confirmation_count": self.independent_confirmation_count,
        }


@dataclass(frozen=True)
class VerifiedClaimDependencySet:
    """Structure RA consultable avant synthèse multi-sources."""

    research_case_id: str
    evidence_set_id: str
    claim_dependencies: Sequence[VerifiedClaimDependency]

    def __post_init__(self) -> None:
        object.__setattr__(self, "research_case_id", _ensure_research_case_id(self.research_case_id))
        object.__setattr__(self, "evidence_set_id", _ensure_evidence_id(self.evidence_set_id))
        dependencies = _ensure_claim_dependencies(self.claim_dependencies)
        claim_refs = tuple(
            (dependency.claim_id, dependency.claim_version)
            for dependency in dependencies
        )
        if len(claim_refs) != len(set(claim_refs)):
            raise ValueError("claim_dependency dupliquee")
        object.__setattr__(self, "claim_dependencies", dependencies)

    def to_payload(self) -> dict[str, object]:
        return {
            "research_case_id": self.research_case_id,
            "evidence_set_id": self.evidence_set_id,
            "claim_dependencies": [
                dependency.to_payload()
                for dependency in self.claim_dependencies
            ],
        }


@dataclass(frozen=True)
class ClaimDependencyGroupResolved:
    """Événement RA de résolution d'un groupe de dépendance EG publié."""

    research_case_id: str
    evidence_set_id: str
    claim_id: str
    claim_version: int
    verification_case_id: str
    dependency_group_id: str
    occurred_at: str

    @property
    def event_type(self) -> str:
        return "ClaimDependencyGroupResolved"

    def __post_init__(self) -> None:
        object.__setattr__(self, "research_case_id", _ensure_research_case_id(self.research_case_id))
        object.__setattr__(self, "evidence_set_id", _ensure_evidence_id(self.evidence_set_id))
        object.__setattr__(self, "claim_id", _ensure_claim_id(self.claim_id))
        object.__setattr__(self, "claim_version", _ensure_claim_version(self.claim_version))
        object.__setattr__(
            self,
            "verification_case_id",
            _ensure_verification_case_id(self.verification_case_id),
        )
        object.__setattr__(
            self,
            "dependency_group_id",
            _ensure_dependency_group_id(self.dependency_group_id),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at))

    def to_payload(self) -> dict[str, object]:
        return {
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "payload": {
                "research_case_id": self.research_case_id,
                "evidence_set_id": self.evidence_set_id,
                "verified_claim_version_ref": {
                    "claim_id": self.claim_id,
                    "claim_version": self.claim_version,
                    "verification_case_id": self.verification_case_id,
                },
                "dependency_group_id": self.dependency_group_id,
            },
        }


@dataclass(frozen=True)
class ResolveVerifiedClaimDependenciesResult:
    """Résultat observable de résolution des dépendances de claims."""

    status: str
    dependency_set: VerifiedClaimDependencySet
    events: Sequence[ClaimDependencyGroupResolved]

    def __post_init__(self) -> None:
        if self.status != "VERIFIED_CLAIM_DEPENDENCIES_RESOLVED":
            raise ValueError("status ResolveVerifiedClaimDependencies invalide")
        if not isinstance(self.dependency_set, VerifiedClaimDependencySet):
            raise ValueError("claim_dependency_set invalide")
        object.__setattr__(self, "events", _ensure_events(self.events))


@dataclass(frozen=True)
class ResolveVerifiedClaimDependenciesHandler:
    """Résout les dépendances EG publiées sans accès au registre propriétaire."""

    verified_claim_catalog: PublicVerifiedClaimEvidenceCatalog
    research_case_repository: ResearchCaseRepository | None = None

    def __post_init__(self) -> None:
        if not callable(getattr(self.verified_claim_catalog, "read_evidence", None)):
            raise ValueError("verified_claim_catalog sans read_evidence")
        if self.research_case_repository is not None:
            if not callable(getattr(self.research_case_repository, "case_for_id", None)):
                raise ValueError("research_case_repository sans case_for_id")
            if not callable(getattr(self.research_case_repository, "update", None)):
                raise ValueError("research_case_repository sans update")

    def resolve(
        self,
        command: ResolveVerifiedClaimDependenciesCommand,
    ) -> ResolveVerifiedClaimDependenciesResult:
        parsed_command = _ensure_command(command)
        evidence_set = parsed_command.evidence_set
        evidence_ids = tuple(evidence_ref.evidence_id for evidence_ref in evidence_set.evidence_refs)
        dependencies = tuple(
            self._resolve_claim_dependency(
                evidence_set_evidence_ids=evidence_ids,
                claim_ref=claim_ref,
            )
            for claim_ref in evidence_set.verified_claim_refs
        )
        dependency_set = VerifiedClaimDependencySet(
            research_case_id=evidence_set.research_case_id,
            evidence_set_id=evidence_set.evidence_set_id,
            claim_dependencies=dependencies,
        )
        events = tuple(
            ClaimDependencyGroupResolved(
                research_case_id=evidence_set.research_case_id,
                evidence_set_id=evidence_set.evidence_set_id,
                claim_id=dependency.claim_id,
                claim_version=dependency.claim_version,
                verification_case_id=dependency.verification_case_id,
                dependency_group_id=dependency_group_id,
                occurred_at=parsed_command.occurred_at,
            )
            for dependency in dependencies
            for dependency_group_id in dependency.dependency_group_ids
        )
        if self.research_case_repository is not None:
            research_case = self.research_case_repository.case_for_id(evidence_set.research_case_id)
            if not isinstance(research_case, ResearchCase):
                raise ValueError("research_case invalide")
            updated_case = research_case.record_claim_dependency_resolutions(
                evidence_set_id=evidence_set.evidence_set_id,
                claim_dependencies=dependencies,
            )
            self.research_case_repository.update(updated_case)
        return ResolveVerifiedClaimDependenciesResult(
            status="VERIFIED_CLAIM_DEPENDENCIES_RESOLVED",
            dependency_set=dependency_set,
            events=events,
        )

    def _resolve_claim_dependency(
        self,
        *,
        evidence_set_evidence_ids: Sequence[str],
        claim_ref: object,
    ) -> VerifiedClaimDependency:
        expected_claim_id = _ensure_claim_id(getattr(claim_ref, "claim_id", None))
        expected_claim_version = _ensure_claim_version(getattr(claim_ref, "claim_version", None))
        _ensure_verified_status(getattr(claim_ref, "status", None))

        public_result = self.verified_claim_catalog.read_evidence(
            expected_claim_id,
            expected_claim_version,
        )
        public_claim = getattr(public_result, "claim", None)
        if public_claim is None:
            raise ValueError("claim public absent")
        if _status_value(getattr(public_claim, "status", None)) != "VERIFIED":
            raise ValueError("claim non verifie")

        public_claim_ref = getattr(public_claim, "verified_claim_ref", None)
        if public_claim_ref is None:
            raise ValueError("claim non verifie")
        _ensure_verified_status(getattr(public_claim_ref, "status", None))
        if _ensure_claim_id(getattr(public_claim_ref, "claim_id", None)) != expected_claim_id:
            raise ValueError("claim_id incoherent")
        public_claim_version = _ensure_claim_version(getattr(public_claim_ref, "claim_version", None))
        if public_claim_version != expected_claim_version:
            raise ValueError("claim_version incoherente")

        verification_case_id = _resolve_verification_case_id(public_result, public_claim_ref)
        accepted_evidence_ids = _resolve_accepted_evidence_ids(
            evidence_set_evidence_ids=evidence_set_evidence_ids,
            expected_claim_ref=claim_ref,
            public_claim_ref=public_claim_ref,
            public_evidence_refs=getattr(public_result, "evidence_refs", None),
        )
        dependency_group_ids = _resolve_dependency_group_ids(
            public_result=public_result,
            public_claim_ref=public_claim_ref,
        )
        independent_confirmation_count = len(dependency_group_ids)
        provided_count = getattr(public_result, "independent_confirmation_count", None)
        if provided_count is not None and provided_count != independent_confirmation_count:
            raise ValueError("confirmation independante incoherente")

        return VerifiedClaimDependency(
            claim_id=expected_claim_id,
            claim_version=expected_claim_version,
            verification_case_id=verification_case_id,
            accepted_evidence_ids=accepted_evidence_ids,
            dependency_group_ids=dependency_group_ids,
            independent_confirmation_count=independent_confirmation_count,
        )


def _resolve_verification_case_id(public_result: object, public_claim_ref: object) -> str:
    verification_case_ids = _ensure_verification_case_ids(
        getattr(public_result, "verification_case_ids", None)
    )
    if len(verification_case_ids) != 1:
        raise ValueError("verification_case_id incoherent")
    verification_case_id = verification_case_ids[0]
    if _ensure_verification_case_id(getattr(public_claim_ref, "verification_id", None)) != verification_case_id:
        raise ValueError("verification_case_id incoherent")
    return verification_case_id


def _resolve_accepted_evidence_ids(
    *,
    evidence_set_evidence_ids: Sequence[str],
    expected_claim_ref: object,
    public_claim_ref: object,
    public_evidence_refs: object,
) -> tuple[str, ...]:
    parsed_evidence_set_ids = _ensure_evidence_ids(evidence_set_evidence_ids)
    public_evidence_ids = {
        evidence_ref.evidence_id
        for evidence_ref in _ensure_evidence_refs(public_evidence_refs)
    }
    expected_claim_evidence_ids = tuple(
        evidence_ref.evidence_id
        for evidence_ref in _ensure_evidence_refs(getattr(expected_claim_ref, "evidence_refs", None))
        if evidence_ref.evidence_id in parsed_evidence_set_ids
    )
    public_claim_evidence_ids = {
        evidence_ref.evidence_id
        for evidence_ref in _ensure_evidence_refs(getattr(public_claim_ref, "evidence_refs", None))
    }
    if len(expected_claim_evidence_ids) == 0:
        raise ValueError("evidence_ref non attachee")
    for evidence_id in expected_claim_evidence_ids:
        if evidence_id not in public_claim_evidence_ids or evidence_id not in public_evidence_ids:
            raise ValueError("evidence_ref non attachee")
    return expected_claim_evidence_ids


def _resolve_dependency_group_ids(
    *,
    public_result: object,
    public_claim_ref: object,
) -> tuple[str, ...]:
    result_group_ids = _ensure_dependency_group_ids(getattr(public_result, "dependency_group_ids", None))
    claim_group_ids = _ensure_dependency_group_ids(getattr(public_claim_ref, "dependency_group_ids", None))
    for dependency_group_id in claim_group_ids:
        if dependency_group_id not in result_group_ids:
            raise ValueError("dependency_group absent")
    return result_group_ids


def _ensure_command(value: ResolveVerifiedClaimDependenciesCommand) -> ResolveVerifiedClaimDependenciesCommand:
    if not isinstance(value, ResolveVerifiedClaimDependenciesCommand):
        raise ValueError("commande ResolveVerifiedClaimDependencies invalide")
    return value


def _ensure_claim_dependencies(
    value: Sequence[VerifiedClaimDependency],
) -> tuple[VerifiedClaimDependency, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("claim_dependencies invalides")
    dependencies = tuple(value)
    if len(dependencies) == 0:
        raise ValueError("claim_dependencies absentes")
    for dependency in dependencies:
        if not isinstance(dependency, VerifiedClaimDependency):
            raise ValueError("claim_dependency invalide")
    return dependencies


def _ensure_events(
    value: Sequence[ClaimDependencyGroupResolved],
) -> tuple[ClaimDependencyGroupResolved, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events invalides")
    events = tuple(value)
    if len(events) == 0:
        raise ValueError("events absents")
    for event in events:
        if not isinstance(event, ClaimDependencyGroupResolved):
            raise ValueError("event ClaimDependencyGroupResolved invalide")
    return events


def _ensure_evidence_refs(value: object) -> tuple[EvidenceRef, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("evidence_refs invalides")
    evidence_refs = tuple(value)
    if len(evidence_refs) == 0:
        raise ValueError("evidence_refs absentes")
    ids: list[str] = []
    for evidence_ref in evidence_refs:
        if not isinstance(evidence_ref, EvidenceRef):
            raise ValueError("evidence_ref invalide")
        if evidence_ref.evidence_id in ids:
            raise ValueError("evidence_ref dupliquee")
        ids.append(evidence_ref.evidence_id)
    return evidence_refs


def _ensure_evidence_ids(value: object) -> tuple[str, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("evidence_ids invalides")
    evidence_ids = tuple(_ensure_evidence_id(item) for item in value)
    if len(evidence_ids) == 0:
        raise ValueError("evidence_ids absents")
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("evidence_ids dupliques")
    return evidence_ids


def _ensure_dependency_group_ids(value: object) -> tuple[str, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("dependency_group absent")
    dependency_group_ids = tuple(_ensure_dependency_group_id(item) for item in value)
    if len(dependency_group_ids) == 0:
        raise ValueError("dependency_group absent")
    if len(dependency_group_ids) != len(set(dependency_group_ids)):
        raise ValueError("dependency_group duplique")
    return dependency_group_ids


def _ensure_verification_case_ids(value: object) -> tuple[str, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("verification_case_id absent")
    verification_case_ids = tuple(_ensure_verification_case_id(item) for item in value)
    if len(verification_case_ids) == 0:
        raise ValueError("verification_case_id absent")
    if len(verification_case_ids) != len(set(verification_case_ids)):
        raise ValueError("verification_case_id duplique")
    return verification_case_ids


def _ensure_verified_status(value: object) -> str:
    status = _status_value(value)
    if status != "VERIFIED":
        raise ValueError("claim non verifie")
    return status


def _status_value(value: object) -> str:
    if value is None:
        raise ValueError("claim non verifie")
    status = getattr(value, "value", value)
    if not isinstance(status, str):
        raise ValueError("claim non verifie")
    if status.strip() == "":
        raise ValueError("claim non verifie")
    return status


def _ensure_claim_id(value: object) -> str:
    text = _ensure_text(value, "claim_id")
    if _CLAIM_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("claim_id invalide")
    return text


def _ensure_claim_version(value: object) -> int:
    if value is None:
        raise ValueError("claim_version absente")
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("claim_version invalide")
    return value


def _ensure_evidence_id(value: object) -> str:
    text = _ensure_text(value, "evidence_id")
    if _EVIDENCE_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("evidence_id invalide")
    return text


def _ensure_dependency_group_id(value: object) -> str:
    text = _ensure_text(value, "dependency_group_id")
    if _DEPENDENCY_GROUP_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("dependency_group_id invalide")
    return text


def _ensure_verification_case_id(value: object) -> str:
    text = _ensure_text(value, "verification_case_id")
    if _VERIFICATION_CASE_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("verification_case_id invalide")
    return text


def _ensure_research_case_id(value: object) -> str:
    text = _ensure_text(value, "research_case_id")
    if _RESEARCH_CASE_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("research_case_id invalide")
    return text


def _ensure_utc_instant(value: object) -> str:
    text = _ensure_text(value, "occurred_at")
    if _UTC_INSTANT_PATTERN.fullmatch(text) is None:
        raise ValueError("occurred_at invalide")
    return text


def _ensure_non_negative_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


__all__ = [
    "ClaimDependencyGroupResolved",
    "PublicVerifiedClaimEvidenceCatalog",
    "ResearchCaseRepository",
    "ResolveVerifiedClaimDependenciesCommand",
    "ResolveVerifiedClaimDependenciesHandler",
    "ResolveVerifiedClaimDependenciesResult",
    "VerifiedClaimDependency",
    "VerifiedClaimDependencySet",
]
