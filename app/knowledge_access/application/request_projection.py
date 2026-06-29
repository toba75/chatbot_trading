"""Commande applicative KA de demande de projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.contracts.event_envelope import EventEnvelope
from app.contracts.identity import DomainIdentifier
from app.contracts.source_references import (
    ACCEPTED_CANONICAL_VERSION_STATUS,
    CanonicalSourceRef,
)
from app.knowledge_access.application.projection_events import (
    KnowledgeProjectionEventFactory,
    ProjectionOutbox,
    append_projection_events_to_outbox,
)
from app.knowledge_access.domain.knowledge_projection import (
    BuildFingerprint,
    KnowledgeProjection,
    ProjectionProfile,
    ProjectionStatus,
)
from app.knowledge_access.domain.chunking import CanonicalChunkDocument


_CANONICAL_READ_STATUSES = frozenset(
    {
        "ACCEPTED",
        "SUPERSEDED",
        "QUARANTINED",
        "REJECTED",
        "RETIRED",
    }
)


class KnowledgeProjectionRepository(Protocol):
    """Port minimal de persistance de KnowledgeProjection."""

    def save_if_absent(
        self,
        projection: KnowledgeProjection,
    ) -> "ProjectionPersistenceDecision":
        """Persiste la projection si son empreinte de build n'existe pas."""

    def require_absent_build_fingerprint(self, build_fingerprint: BuildFingerprint) -> None:
        """Refuse explicitement une empreinte de build déjà demandée."""

    def projection_for_build_fingerprint(
        self,
        build_fingerprint: BuildFingerprint,
    ) -> KnowledgeProjection | None:
        """Retourne la projection existante pour une empreinte de build."""


class CanonicalSourceReader(Protocol):
    """Port de lecture KA des références canoniques publiées par SP."""

    def find_projection_source_by_document_id(
        self,
        document_id: str,
    ) -> "CanonicalSourceForProjection | None":
        """Lit une vue publique de version canonique sans accéder aux tables SP."""

    def find_chunking_source_by_version_id(
        self,
        canonical_version_id: str,
    ) -> CanonicalChunkDocument | None:
        """Lit le contenu canonique publié nécessaire au chunking KA."""


class ProcessedProjectionEventRegistry(Protocol):
    """Port de suivi idempotent des événements CanonicalSourcePublished."""

    def has_processed(self, event: EventEnvelope) -> bool:
        """Indique si l'event_id a déjà été traité."""

    def record_processed(self, event: EventEnvelope) -> None:
        """Enregistre l'event_id traité."""

    def record_duplicate(self, event: EventEnvelope) -> None:
        """Trace explicitement un event_id reçu en doublon."""


class KnowledgeProjectionCommandError(ValueError):
    """Erreur métier stable des commandes KA."""


class SourceNotFoundError(KnowledgeProjectionCommandError):
    """Erreur produite quand le document est inconnu de la lecture canonique."""

    def __init__(self, document_id: str) -> None:
        self.document_id = _ensure_document_id(document_id)
        super().__init__(f"source inconnue: {self.document_id}")


class SourceNotCanonicalError(KnowledgeProjectionCommandError):
    """Erreur produite quand aucune version canonique publiée n'est projetable."""

    def __init__(self, document_id: str, canonical_status: str) -> None:
        self.document_id = _ensure_document_id(document_id)
        self.canonical_status = _ensure_text(canonical_status, "canonical_status")
        super().__init__(f"source non canonique: {self.document_id}; {self.canonical_status}")


class SourceQuarantinedError(KnowledgeProjectionCommandError):
    """Erreur produite quand la source est explicitement non indexable."""

    def __init__(self, document_id: str, reason: str) -> None:
        self.document_id = _ensure_document_id(document_id)
        self.reason = _ensure_text(reason, "quarantine_reason")
        super().__init__(f"source en quarantaine: {self.document_id}; {self.reason}")


class ProjectionAlreadyRequestedError(KnowledgeProjectionCommandError):
    """Erreur produite quand une projection identique existe déjà."""

    def __init__(self, projection_id: str, build_fingerprint: BuildFingerprint) -> None:
        self.projection_id = _ensure_projection_id(projection_id)
        self.build_fingerprint = _ensure_build_fingerprint(build_fingerprint)
        super().__init__(f"projection deja demandee: {self.projection_id}")


class ProjectionProfileInvalidError(KnowledgeProjectionCommandError):
    """Erreur produite quand le profil public de projection est invalide."""

    def __init__(self, reason: str) -> None:
        self.reason = _ensure_text(reason, "reason")
        super().__init__(self.reason)


@dataclass(frozen=True)
class CanonicalSourceForProjection:
    """Vue publique minimale lue par KA pour décider l'éligibilité."""

    document_id: str
    canonical_ref: CanonicalSourceRef | None
    canonical_status: str
    quarantine_reason: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "document_id", _ensure_document_id(self.document_id))
        canonical_status = _ensure_text(self.canonical_status, "canonical_status")
        if canonical_status not in _CANONICAL_READ_STATUSES:
            raise ValueError(f"canonical_status inconnu: {canonical_status}")
        object.__setattr__(self, "canonical_status", canonical_status)
        if self.canonical_ref is not None and not isinstance(self.canonical_ref, CanonicalSourceRef):
            raise ValueError("CanonicalSourceRef invalide")
        if canonical_status == "QUARANTINED":
            if self.canonical_ref is not None:
                raise ValueError("CanonicalSourceRef interdite pour source en quarantaine")
            _ensure_text(self.quarantine_reason, "quarantine_reason")
        elif self.quarantine_reason is not None:
            raise ValueError("quarantine_reason interdite hors quarantaine")


@dataclass(frozen=True)
class ProjectionPersistenceDecision:
    """Décision observable d'une persistance idempotente."""

    projection: KnowledgeProjection
    created: bool

    def __post_init__(self) -> None:
        _ensure_projection(self.projection)
        if not isinstance(self.created, bool):
            raise ValueError("created non booleen")


@dataclass(frozen=True)
class RequestKnowledgeProjectionCommand:
    """Commande KA de projection d'une version canonique."""

    document_id: str
    projection_profile: ProjectionProfile

    def __post_init__(self) -> None:
        object.__setattr__(self, "document_id", _ensure_document_id(self.document_id))
        if not isinstance(self.projection_profile, ProjectionProfile):
            raise ProjectionProfileInvalidError("projection_profile invalide")


@dataclass(frozen=True)
class RequestKnowledgeProjectionAcceptance:
    """Réponse applicative publique de projection demandée."""

    projection_id: str
    document_id: str
    projection_status: ProjectionStatus
    canonical_version_id: str

    @classmethod
    def from_projection(
        cls,
        projection: KnowledgeProjection,
    ) -> "RequestKnowledgeProjectionAcceptance":
        parsed_projection = _ensure_projection(projection)
        return cls(
            projection_id=parsed_projection.projection_id,
            document_id=parsed_projection.document_id,
            projection_status=parsed_projection.status,
            canonical_version_id=parsed_projection.canonical_version_id,
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "projection_id", _ensure_projection_id(self.projection_id))
        object.__setattr__(self, "document_id", _ensure_document_id(self.document_id))
        object.__setattr__(
            self,
            "projection_status",
            ProjectionStatus.from_value(self.projection_status),
        )
        object.__setattr__(
            self,
            "canonical_version_id",
            _ensure_canonical_version_id(self.canonical_version_id),
        )


class ProjectionEligibilityPolicy:
    """Autorise seulement les versions canoniques publiées et non mises en quarantaine."""

    def require_eligible(
        self,
        projection_source: CanonicalSourceForProjection,
    ) -> CanonicalSourceRef:
        parsed_source = _ensure_projection_source(projection_source)
        if parsed_source.canonical_status == "QUARANTINED":
            raise SourceQuarantinedError(
                document_id=parsed_source.document_id,
                reason=str(parsed_source.quarantine_reason),
            )
        if parsed_source.canonical_status != ACCEPTED_CANONICAL_VERSION_STATUS:
            raise SourceNotCanonicalError(
                document_id=parsed_source.document_id,
                canonical_status=parsed_source.canonical_status,
            )
        if parsed_source.canonical_ref is None:
            raise SourceNotCanonicalError(
                document_id=parsed_source.document_id,
                canonical_status=parsed_source.canonical_status,
            )
        if parsed_source.canonical_ref.document_id != parsed_source.document_id:
            raise SourceNotCanonicalError(
                document_id=parsed_source.document_id,
                canonical_status=parsed_source.canonical_status,
            )
        return parsed_source.canonical_ref


class RequestKnowledgeProjectionHandler:
    """Cas d'usage KA de création d'une KnowledgeProjection REQUESTED."""

    def __init__(
        self,
        *,
        canonical_source_reader: CanonicalSourceReader,
        projection_repository: KnowledgeProjectionRepository,
        outbox: ProjectionOutbox,
    ) -> None:
        if not callable(getattr(canonical_source_reader, "find_projection_source_by_document_id", None)):
            raise ValueError("canonical_source_reader sans lecture par document_id")
        if not callable(getattr(projection_repository, "save_if_absent", None)):
            raise ValueError("projection_repository sans save_if_absent")
        if not callable(getattr(projection_repository, "require_absent_build_fingerprint", None)):
            raise ValueError("projection_repository sans controle d'empreinte")
        if not callable(getattr(outbox, "has_event", None)):
            raise ValueError("outbox invalide")
        if not callable(getattr(outbox, "append_many_in_transaction", None)):
            raise ValueError("outbox invalide")
        self._canonical_source_reader = canonical_source_reader
        self._projection_repository = projection_repository
        self._outbox = outbox
        self._eligibility_policy = ProjectionEligibilityPolicy()

    def request_projection(
        self,
        command: RequestKnowledgeProjectionCommand,
    ) -> RequestKnowledgeProjectionAcceptance:
        parsed_command = _ensure_request_command(command)
        projection_source = self._canonical_source_reader.find_projection_source_by_document_id(
            parsed_command.document_id
        )
        if projection_source is None:
            raise SourceNotFoundError(document_id=parsed_command.document_id)
        canonical_ref = self._eligibility_policy.require_eligible(projection_source)
        projection = KnowledgeProjection.request(
            canonical_ref=canonical_ref,
            projection_profile=parsed_command.projection_profile,
        )
        self._projection_repository.require_absent_build_fingerprint(projection.build_fingerprint)
        requested_event = KnowledgeProjectionEventFactory(
            occurred_at=canonical_ref.accepted_at,
            correlation_id=_correlation_id_for_projection(projection.projection_id),
            causation_id=_causation_id_for_projection(projection.projection_id),
        ).requested(projection=projection)
        append_projection_events_to_outbox(
            outbox=self._outbox,
            events=(requested_event,),
        )
        decision = self._projection_repository.save_if_absent(projection)
        if not decision.created:
            raise ProjectionAlreadyRequestedError(
                projection_id=decision.projection.projection_id,
                build_fingerprint=decision.projection.build_fingerprint,
            )
        return RequestKnowledgeProjectionAcceptance.from_projection(decision.projection)


@dataclass(frozen=True)
class ProjectionEventConsumptionDecision:
    """Décision observable après consommation de CanonicalSourcePublished."""

    projection: KnowledgeProjection
    created: bool
    duplicate: bool

    def __post_init__(self) -> None:
        _ensure_projection(self.projection)
        if not isinstance(self.created, bool):
            raise ValueError("created non booleen")
        if not isinstance(self.duplicate, bool):
            raise ValueError("duplicate non booleen")
        if self.created and self.duplicate:
            raise ValueError("decision de consommation incoherente")


class CanonicalSourcePublishedProjectionConsumer:
    """Consommateur idempotent de CanonicalSourcePublished pour KA."""

    def __init__(
        self,
        *,
        projection_repository: KnowledgeProjectionRepository,
        processed_events: ProcessedProjectionEventRegistry,
    ) -> None:
        if not callable(getattr(projection_repository, "save_if_absent", None)):
            raise ValueError("projection_repository sans save_if_absent")
        if not callable(getattr(processed_events, "has_processed", None)):
            raise ValueError("processed_events sans has_processed")
        if not callable(getattr(processed_events, "record_processed", None)):
            raise ValueError("processed_events sans record_processed")
        if not callable(getattr(processed_events, "record_duplicate", None)):
            raise ValueError("processed_events sans record_duplicate")
        self._projection_repository = projection_repository
        self._processed_events = processed_events

    def consume(
        self,
        *,
        event: EventEnvelope,
        projection_profile: ProjectionProfile,
    ) -> ProjectionEventConsumptionDecision:
        envelope = _ensure_event(event)
        parsed_profile = _ensure_projection_profile(projection_profile)
        canonical_ref = _canonical_ref_from_event(envelope)
        projection = KnowledgeProjection.request(
            canonical_ref=canonical_ref,
            projection_profile=parsed_profile,
        )
        if self._processed_events.has_processed(envelope):
            self._processed_events.record_duplicate(envelope)
            return ProjectionEventConsumptionDecision(
                projection=projection,
                created=False,
                duplicate=True,
            )
        decision = self._projection_repository.save_if_absent(projection)
        self._processed_events.record_processed(envelope)
        return ProjectionEventConsumptionDecision(
            projection=decision.projection,
            created=decision.created,
            duplicate=False,
        )


def _canonical_ref_from_event(event: EventEnvelope) -> CanonicalSourceRef:
    envelope = _ensure_event(event)
    if envelope.event_type != "CanonicalSourcePublished":
        raise ValueError("event_type CanonicalSourcePublished obligatoire")
    return CanonicalSourceRef.from_payload(dict(envelope.payload))


def _ensure_event(value: EventEnvelope) -> EventEnvelope:
    if not isinstance(value, EventEnvelope):
        raise ValueError("event invalide")
    return value


def _ensure_projection_profile(value: ProjectionProfile) -> ProjectionProfile:
    if not isinstance(value, ProjectionProfile):
        raise ProjectionProfileInvalidError("projection_profile invalide")
    return value


def _ensure_projection_source(value: CanonicalSourceForProjection) -> CanonicalSourceForProjection:
    if not isinstance(value, CanonicalSourceForProjection):
        raise ValueError("source de projection invalide")
    return value


def _ensure_request_command(value: RequestKnowledgeProjectionCommand) -> RequestKnowledgeProjectionCommand:
    if not isinstance(value, RequestKnowledgeProjectionCommand):
        raise ValueError("commande RequestKnowledgeProjection invalide")
    return value


def _ensure_projection(value: KnowledgeProjection) -> KnowledgeProjection:
    if not isinstance(value, KnowledgeProjection):
        raise ValueError("projection invalide")
    return value


def _ensure_build_fingerprint(value: BuildFingerprint) -> BuildFingerprint:
    if not isinstance(value, BuildFingerprint):
        raise ValueError("build_fingerprint invalide")
    return value


def _ensure_document_id(value: Any) -> str:
    return _ensure_domain_id(value, "DOC")


def _ensure_projection_id(value: Any) -> str:
    return _ensure_domain_id(value, "PROJ")


def _ensure_canonical_version_id(value: Any) -> str:
    return _ensure_domain_id(value, "CVER")


def _ensure_domain_id(value: Any, expected_prefix: str) -> str:
    if not isinstance(value, str):
        raise ValueError("identifiant de domaine invalide")
    try:
        return str(DomainIdentifier.parse_with_prefix(value, expected_prefix))
    except ValueError as exc:
        raise ValueError(f"identifiant {expected_prefix} invalide: {exc}") from exc


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _correlation_id_for_projection(projection_id: str) -> str:
    return f"CORR-{_projection_suffix(projection_id)}"


def _causation_id_for_projection(projection_id: str) -> str:
    return f"CMD-{_projection_suffix(projection_id)}"


def _projection_suffix(projection_id: str) -> str:
    return _ensure_projection_id(projection_id).removeprefix("PROJ-")


__all__ = [
    "CanonicalSourceForProjection",
    "CanonicalSourcePublishedProjectionConsumer",
    "CanonicalSourceReader",
    "KnowledgeProjectionCommandError",
    "KnowledgeProjectionRepository",
    "ProcessedProjectionEventRegistry",
    "ProjectionAlreadyRequestedError",
    "ProjectionEligibilityPolicy",
    "ProjectionEventConsumptionDecision",
    "ProjectionPersistenceDecision",
    "ProjectionProfileInvalidError",
    "RequestKnowledgeProjectionAcceptance",
    "RequestKnowledgeProjectionCommand",
    "RequestKnowledgeProjectionHandler",
    "SourceNotCanonicalError",
    "SourceNotFoundError",
    "SourceQuarantinedError",
]
