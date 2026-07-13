"""Politique V1 de rétention et purge administrative M-013."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any


RETENTION_POLICY_VERSION = "M013-RetentionPolicy-1.0"

ORDINARY_PURGE = "ORDINARY_PURGE"
ADMINISTRATIVE_PURGE = "ADMINISTRATIVE_PURGE"
LOGICAL_ARCHIVE = "LOGICAL_ARCHIVE"
PURGE_CONVERSATION_CONTENT = "PURGE_CONVERSATION_CONTENT"
PURGE_REGENERABLE_PROJECTION = "PURGE_REGENERABLE_PROJECTION"

CONTEXT_SP = "SP"
CONTEXT_KA = "KA"
CONTEXT_EG = "EG"
CONTEXT_RA = "RA"
CONTEXT_CV = "CV"
CONTEXT_SD = "SD"
CONTEXT_EX = "EX"
CONTEXT_EV = "EV"

CATEGORY_SP_ORIGINALS = "SP_ORIGINALS"
CATEGORY_SP_CANONICAL_VERSIONS = "SP_CANONICAL_VERSIONS"
CATEGORY_KA_REGENERABLE_PROJECTIONS = "KA_REGENERABLE_PROJECTIONS"
CATEGORY_EG_CLAIMS = "EG_CLAIMS"
CATEGORY_RA_VERIFIED_ANSWERS = "RA_VERIFIED_ANSWERS"
CATEGORY_CV_CONVERSATIONS = "CV_CONVERSATIONS"
CATEGORY_SD_STRATEGY_SNAPSHOTS = "SD_STRATEGY_SNAPSHOTS"
CATEGORY_EX_EXPERIMENT_RESULTS = "EX_EXPERIMENT_RESULTS"
CATEGORY_EV_GOVERNANCE_DECISIONS = "EV_GOVERNANCE_DECISIONS"

_EXPECTED_CATEGORY_IDS = (
    CATEGORY_SP_ORIGINALS,
    CATEGORY_SP_CANONICAL_VERSIONS,
    CATEGORY_KA_REGENERABLE_PROJECTIONS,
    CATEGORY_EG_CLAIMS,
    CATEGORY_RA_VERIFIED_ANSWERS,
    CATEGORY_CV_CONVERSATIONS,
    CATEGORY_SD_STRATEGY_SNAPSHOTS,
    CATEGORY_EX_EXPERIMENT_RESULTS,
    CATEGORY_EV_GOVERNANCE_DECISIONS,
)

_EXPECTED_CONTEXTS = (CONTEXT_SP, CONTEXT_KA, CONTEXT_EG, CONTEXT_RA, CONTEXT_CV, CONTEXT_SD, CONTEXT_EX, CONTEXT_EV)
_EXPECTED_CONTEXT_BY_CATEGORY = {
    CATEGORY_SP_ORIGINALS: CONTEXT_SP,
    CATEGORY_SP_CANONICAL_VERSIONS: CONTEXT_SP,
    CATEGORY_KA_REGENERABLE_PROJECTIONS: CONTEXT_KA,
    CATEGORY_EG_CLAIMS: CONTEXT_EG,
    CATEGORY_RA_VERIFIED_ANSWERS: CONTEXT_RA,
    CATEGORY_CV_CONVERSATIONS: CONTEXT_CV,
    CATEGORY_SD_STRATEGY_SNAPSHOTS: CONTEXT_SD,
    CATEGORY_EX_EXPERIMENT_RESULTS: CONTEXT_EX,
    CATEGORY_EV_GOVERNANCE_DECISIONS: CONTEXT_EV,
}
_ALLOWED_OPERATIONS = (LOGICAL_ARCHIVE, PURGE_CONVERSATION_CONTENT, PURGE_REGENERABLE_PROJECTION)
_REQUIRED_NEGATIVE_RETENTION_CATEGORIES = (
    CATEGORY_SP_CANONICAL_VERSIONS,
    CATEGORY_EG_CLAIMS,
    CATEGORY_RA_VERIFIED_ANSWERS,
    CATEGORY_SD_STRATEGY_SNAPSHOTS,
    CATEGORY_EX_EXPERIMENT_RESULTS,
    CATEGORY_EV_GOVERNANCE_DECISIONS,
)
_EXPECTED_RETENTION_MONTHS_BY_CATEGORY = {
    CATEGORY_SP_ORIGINALS: 120,
    CATEGORY_SP_CANONICAL_VERSIONS: 120,
    CATEGORY_KA_REGENERABLE_PROJECTIONS: 3,
    CATEGORY_EG_CLAIMS: 120,
    CATEGORY_RA_VERIFIED_ANSWERS: 120,
    CATEGORY_CV_CONVERSATIONS: 18,
    CATEGORY_SD_STRATEGY_SNAPSHOTS: 120,
    CATEGORY_EX_EXPERIMENT_RESULTS: 120,
    CATEGORY_EV_GOVERNANCE_DECISIONS: 120,
}
_COMMAND_PREFIX = "uv run rebuild-knowledge-projection"


@dataclass(frozen=True)
class RetentionCategory:
    category_id: str
    context: str
    artifact_kind: str
    retention_months: int
    allowed_operation: str
    requires_justification: bool
    requires_audit: bool
    preserve_negative_or_superseded: bool
    regenerable_projection: bool
    reconstruction_command: str
    read_compatibility_rule: str
    ordinary_purge_allowed: bool
    cascade_allowed_to_knowledge: bool
    cascade_allowed_to_experiments: bool

    def __init__(
        self,
        *,
        category_id: str,
        context: str,
        artifact_kind: str,
        retention_months: int,
        allowed_operation: str,
        requires_justification: bool,
        requires_audit: bool,
        preserve_negative_or_superseded: bool,
        regenerable_projection: bool,
        reconstruction_command: str,
        read_compatibility_rule: str,
        ordinary_purge_allowed: bool,
        cascade_allowed_to_knowledge: bool,
        cascade_allowed_to_experiments: bool,
    ) -> None:
        parsed_category_id = _required_category_id(category_id)
        parsed_context = _required_context(context)
        parsed_allowed_operation = _required_allowed_operation(allowed_operation)
        parsed_regenerable_projection = _required_bool(regenerable_projection, "regenerable_projection")
        parsed_reconstruction_command = _required_text(reconstruction_command, "commande de reconstruction")
        parsed_ordinary_purge_allowed = _required_bool(ordinary_purge_allowed, "ordinary_purge_allowed")
        parsed_retention_months = _required_positive_int(retention_months, "durée de rétention absente")

        if parsed_ordinary_purge_allowed:
            raise ValueError("suppression ordinaire interdite")
        if _EXPECTED_CONTEXT_BY_CATEGORY[parsed_category_id] != parsed_context:
            raise ValueError("contexte de catégorie durable incohérent")
        if parsed_retention_months != _EXPECTED_RETENTION_MONTHS_BY_CATEGORY[parsed_category_id]:
            raise ValueError("durée de rétention incohérente")
        if parsed_regenerable_projection and not _is_command(parsed_reconstruction_command):
            raise ValueError("projection régénérable avec reconstruction requise")
        if not parsed_regenerable_projection and parsed_reconstruction_command.startswith(_COMMAND_PREFIX):
            raise ValueError("commande de reconstruction réservée aux projections")
        if parsed_category_id == CATEGORY_CV_CONVERSATIONS:
            if _required_bool(cascade_allowed_to_knowledge, "cascade_allowed_to_knowledge"):
                raise ValueError("conversation sans cascade vers connaissances ou expériences")
            if _required_bool(cascade_allowed_to_experiments, "cascade_allowed_to_experiments"):
                raise ValueError("conversation sans cascade vers connaissances ou expériences")

        object.__setattr__(self, "category_id", parsed_category_id)
        object.__setattr__(self, "context", parsed_context)
        object.__setattr__(self, "artifact_kind", _required_text(artifact_kind, "artifact_kind"))
        object.__setattr__(self, "retention_months", parsed_retention_months)
        object.__setattr__(self, "allowed_operation", parsed_allowed_operation)
        object.__setattr__(self, "requires_justification", _required_bool(requires_justification, "requires_justification"))
        object.__setattr__(self, "requires_audit", _required_bool(requires_audit, "requires_audit"))
        object.__setattr__(
            self,
            "preserve_negative_or_superseded",
            _required_bool(preserve_negative_or_superseded, "preserve_negative_or_superseded"),
        )
        object.__setattr__(self, "regenerable_projection", parsed_regenerable_projection)
        object.__setattr__(self, "reconstruction_command", parsed_reconstruction_command)
        object.__setattr__(
            self,
            "read_compatibility_rule",
            _required_text(read_compatibility_rule, "compatibilité de lecture requise"),
        )
        object.__setattr__(self, "ordinary_purge_allowed", False)
        object.__setattr__(self, "cascade_allowed_to_knowledge", False)
        object.__setattr__(self, "cascade_allowed_to_experiments", False)

    def with_retention_months(self, retention_months: int) -> "RetentionCategory":
        return RetentionCategory(
            category_id=self.category_id,
            context=self.context,
            artifact_kind=self.artifact_kind,
            retention_months=retention_months,
            allowed_operation=self.allowed_operation,
            requires_justification=self.requires_justification,
            requires_audit=self.requires_audit,
            preserve_negative_or_superseded=self.preserve_negative_or_superseded,
            regenerable_projection=self.regenerable_projection,
            reconstruction_command=self.reconstruction_command,
            read_compatibility_rule=self.read_compatibility_rule,
            ordinary_purge_allowed=self.ordinary_purge_allowed,
            cascade_allowed_to_knowledge=self.cascade_allowed_to_knowledge,
            cascade_allowed_to_experiments=self.cascade_allowed_to_experiments,
        )


@dataclass(frozen=True)
class RetentionOperationRequest:
    request_id: str
    category_id: str
    operation: str
    justification: str
    audit_event_id: str
    requested_by: str
    requested_at: str
    target_stable_identifiers: tuple[str, ...]
    cascade_to_knowledge: bool
    cascade_to_experiments: bool
    reconstruction_command: str
    read_compatibility_proof: str
    retains_negative_or_superseded: bool

    def __init__(
        self,
        *,
        request_id: str,
        category_id: str,
        operation: str,
        justification: str,
        audit_event_id: str,
        requested_by: str,
        requested_at: str,
        target_stable_identifiers: Sequence[str],
        cascade_to_knowledge: bool,
        cascade_to_experiments: bool,
        reconstruction_command: str,
        read_compatibility_proof: str,
        retains_negative_or_superseded: bool,
    ) -> None:
        parsed_category_id = _required_category_id(category_id)
        parsed_operation = _required_request_operation(operation)
        parsed_targets = _required_text_tuple(target_stable_identifiers, "identifiant stable ciblé")
        parsed_retains_negative_or_superseded = _required_bool(
            retains_negative_or_superseded,
            "retains_negative_or_superseded",
        )
        if _required_bool(cascade_to_knowledge, "cascade_to_knowledge"):
            raise ValueError("conversation sans cascade vers connaissances ou expériences")
        if _required_bool(cascade_to_experiments, "cascade_to_experiments"):
            raise ValueError("conversation sans cascade vers connaissances ou expériences")
        if parsed_category_id in _REQUIRED_NEGATIVE_RETENTION_CATEGORIES and not parsed_retains_negative_or_superseded:
            raise ValueError("résultat négatif ou supersédé doit rester conservé")

        object.__setattr__(self, "request_id", _required_text(request_id, "request_id"))
        object.__setattr__(self, "category_id", parsed_category_id)
        object.__setattr__(self, "operation", parsed_operation)
        object.__setattr__(self, "justification", _required_text(justification, "justification administrative requise"))
        object.__setattr__(self, "audit_event_id", _required_text(audit_event_id, "audit administratif requis"))
        object.__setattr__(self, "requested_by", _required_text(requested_by, "requested_by"))
        object.__setattr__(self, "requested_at", _required_text(requested_at, "requested_at"))
        object.__setattr__(self, "target_stable_identifiers", parsed_targets)
        object.__setattr__(self, "cascade_to_knowledge", False)
        object.__setattr__(self, "cascade_to_experiments", False)
        if parsed_operation == PURGE_REGENERABLE_PROJECTION:
            parsed_reconstruction_command = _required_text(
                reconstruction_command,
                "projection régénérable avec reconstruction requise",
            )
        else:
            parsed_reconstruction_command = _required_text(reconstruction_command, "commande de reconstruction")
        object.__setattr__(self, "reconstruction_command", parsed_reconstruction_command)
        object.__setattr__(
            self,
            "read_compatibility_proof",
            _required_text(read_compatibility_proof, "compatibilité de lecture requise"),
        )
        object.__setattr__(
            self,
            "retains_negative_or_superseded",
            parsed_retains_negative_or_superseded,
        )


@dataclass(frozen=True)
class RetentionPolicy:
    policy_version: str
    categories: tuple[RetentionCategory, ...]
    categories_by_id: Mapping[str, RetentionCategory]

    def __init__(
        self,
        *,
        policy_version: str,
        categories: Sequence[RetentionCategory],
    ) -> None:
        parsed_policy_version = _required_policy_version(policy_version)
        parsed_categories = _required_category_tuple(categories)
        categories_by_id: dict[str, RetentionCategory] = {}
        for category in parsed_categories:
            if category.category_id in categories_by_id:
                raise ValueError("catégorie durable dupliquée")
            categories_by_id[category.category_id] = category

        for expected_category_id in _EXPECTED_CATEGORY_IDS:
            if expected_category_id not in categories_by_id:
                raise ValueError("catégorie durable absente")

        for category_id in _REQUIRED_NEGATIVE_RETENTION_CATEGORIES:
            if not categories_by_id[category_id].preserve_negative_or_superseded:
                raise ValueError("résultat négatif ou supersédé doit rester conservé")

        projection = categories_by_id[CATEGORY_KA_REGENERABLE_PROJECTIONS]
        if not projection.regenerable_projection:
            raise ValueError("projection régénérable avec reconstruction requise")
        if not _is_command(projection.reconstruction_command):
            raise ValueError("projection régénérable avec reconstruction requise")

        conversation = categories_by_id[CATEGORY_CV_CONVERSATIONS]
        if conversation.allowed_operation != PURGE_CONVERSATION_CONTENT:
            raise ValueError("opération conversationnelle invalide")
        if conversation.cascade_allowed_to_knowledge or conversation.cascade_allowed_to_experiments:
            raise ValueError("conversation sans cascade vers connaissances ou expériences")

        object.__setattr__(self, "policy_version", parsed_policy_version)
        object.__setattr__(self, "categories", parsed_categories)
        object.__setattr__(self, "categories_by_id", MappingProxyType(categories_by_id))

    def validate_operation(self, request: RetentionOperationRequest) -> None:
        if not isinstance(request, RetentionOperationRequest):
            raise ValueError("RetentionOperationRequest requise")
        category = self.categories_by_id[request.category_id]
        if request.operation != category.allowed_operation:
            raise ValueError("opération administrative non autorisée")
        if category.preserve_negative_or_superseded and not request.retains_negative_or_superseded:
            raise ValueError("résultat négatif ou supersédé doit rester conservé")
        if category.regenerable_projection and not _is_command(request.reconstruction_command):
            raise ValueError("projection régénérable avec reconstruction requise")
        if category.category_id == CATEGORY_CV_CONVERSATIONS:
            if request.cascade_to_knowledge or request.cascade_to_experiments:
                raise ValueError("conversation sans cascade vers connaissances ou expériences")
        _required_text(request.read_compatibility_proof, "compatibilité de lecture requise")


def build_m013_retention_policy() -> RetentionPolicy:
    return RetentionPolicy(
        policy_version=RETENTION_POLICY_VERSION,
        categories=(
            _category(
                category_id=CATEGORY_SP_ORIGINALS,
                context=CONTEXT_SP,
                artifact_kind="originaux du corpus",
                retention_months=120,
                allowed_operation=LOGICAL_ARCHIVE,
                preserve_negative_or_superseded=False,
                regenerable_projection=False,
                reconstruction_command="Non applicable: artefact d'autorité conservé.",
                read_compatibility_rule="SourceDocumentId et SourceLocator restent résolubles pendant 120 mois.",
            ),
            _category(
                category_id=CATEGORY_SP_CANONICAL_VERSIONS,
                context=CONTEXT_SP,
                artifact_kind="versions canoniques publiées",
                retention_months=120,
                allowed_operation=LOGICAL_ARCHIVE,
                preserve_negative_or_superseded=True,
                regenerable_projection=False,
                reconstruction_command="Non applicable: version canonique d'autorité conservée.",
                read_compatibility_rule="Les versions remplacées restent ouvertes par identifiant canonique stable.",
            ),
            _category(
                category_id=CATEGORY_KA_REGENERABLE_PROJECTIONS,
                context=CONTEXT_KA,
                artifact_kind="projection Qdrant et index de recherche",
                retention_months=3,
                allowed_operation=PURGE_REGENERABLE_PROJECTION,
                preserve_negative_or_superseded=False,
                regenerable_projection=True,
                reconstruction_command=(
                    "uv run rebuild-knowledge-projection --source SP --source-root .\\data\\sp-authority "
                    "--target .\\data\\ka-projection"
                ),
                read_compatibility_rule="La projection est reconstruite depuis les originaux et versions canoniques conservés.",
            ),
            _category(
                category_id=CATEGORY_EG_CLAIMS,
                context=CONTEXT_EG,
                artifact_kind="claims, relations, rejets et supersessions",
                retention_months=120,
                allowed_operation=LOGICAL_ARCHIVE,
                preserve_negative_or_superseded=True,
                regenerable_projection=False,
                reconstruction_command="Non applicable: registre EG d'autorité conservé.",
                read_compatibility_rule="ClaimId, relations et raisons de rejet restent consultables pendant 120 mois.",
            ),
            _category(
                category_id=CATEGORY_RA_VERIFIED_ANSWERS,
                context=CONTEXT_RA,
                artifact_kind="réponses vérifiées publiées et supersédées",
                retention_months=120,
                allowed_operation=LOGICAL_ARCHIVE,
                preserve_negative_or_superseded=True,
                regenerable_projection=False,
                reconstruction_command="Non applicable: réponse publiée d'autorité conservée.",
                read_compatibility_rule="AnswerId et citations publiées restent résolubles pendant 120 mois.",
            ),
            _category(
                category_id=CATEGORY_CV_CONVERSATIONS,
                context=CONTEXT_CV,
                artifact_kind="tours de conversation et contexte utilisateur",
                retention_months=18,
                allowed_operation=PURGE_CONVERSATION_CONTENT,
                preserve_negative_or_superseded=False,
                regenerable_projection=False,
                reconstruction_command="Non applicable: purge CV isolée sans reconstruction de conversation brute.",
                read_compatibility_rule="La purge CV ne cascade pas vers les réponses, claims, stratégies ou expériences publiés.",
            ),
            _category(
                category_id=CATEGORY_SD_STRATEGY_SNAPSHOTS,
                context=CONTEXT_SD,
                artifact_kind="snapshots de stratégie, diagnostics invalides et versions rejetées",
                retention_months=120,
                allowed_operation=LOGICAL_ARCHIVE,
                preserve_negative_or_superseded=True,
                regenerable_projection=False,
                reconstruction_command="Non applicable: snapshot SD d'autorité conservé.",
                read_compatibility_rule="StrategySnapshotId reste consultable avec diagnostics pendant 120 mois.",
            ),
            _category(
                category_id=CATEGORY_EX_EXPERIMENT_RESULTS,
                context=CONTEXT_EX,
                artifact_kind="résultats, échecs, séries et artefacts d'expérience",
                retention_months=120,
                allowed_operation=LOGICAL_ARCHIVE,
                preserve_negative_or_superseded=True,
                regenerable_projection=False,
                reconstruction_command="Non applicable: résultat EX d'autorité conservé.",
                read_compatibility_rule="ExperimentId, résultats négatifs et corrections liées restent consultables pendant 120 mois.",
            ),
            _category(
                category_id=CATEGORY_EV_GOVERNANCE_DECISIONS,
                context=CONTEXT_EV,
                artifact_kind="benchmarks, décisions de calibration, écarts V1 et ADR",
                retention_months=120,
                allowed_operation=LOGICAL_ARCHIVE,
                preserve_negative_or_superseded=True,
                regenerable_projection=False,
                reconstruction_command="Non applicable: décisions de gouvernance conservées.",
                read_compatibility_rule="Les décisions acceptées, rejetées, différées et bloquantes restent consultables pendant 120 mois.",
            ),
        ),
    )


def _category(
    *,
    category_id: str,
    context: str,
    artifact_kind: str,
    retention_months: int,
    allowed_operation: str,
    preserve_negative_or_superseded: bool,
    regenerable_projection: bool,
    reconstruction_command: str,
    read_compatibility_rule: str,
) -> RetentionCategory:
    return RetentionCategory(
        category_id=category_id,
        context=context,
        artifact_kind=artifact_kind,
        retention_months=retention_months,
        allowed_operation=allowed_operation,
        requires_justification=True,
        requires_audit=True,
        preserve_negative_or_superseded=preserve_negative_or_superseded,
        regenerable_projection=regenerable_projection,
        reconstruction_command=reconstruction_command,
        read_compatibility_rule=read_compatibility_rule,
        ordinary_purge_allowed=False,
        cascade_allowed_to_knowledge=False,
        cascade_allowed_to_experiments=False,
    )


def _required_policy_version(value: Any) -> str:
    text = _required_text(value, "version de politique")
    if text != RETENTION_POLICY_VERSION:
        raise ValueError("version de politique incohérente")
    return text


def _required_category_id(value: Any) -> str:
    text = _required_text(value, "catégorie durable")
    if text not in _EXPECTED_CATEGORY_IDS:
        raise ValueError("catégorie durable inconnue")
    return text


def _required_context(value: Any) -> str:
    text = _required_text(value, "contexte")
    if text not in _EXPECTED_CONTEXTS:
        raise ValueError("contexte V1 inconnu")
    return text


def _required_allowed_operation(value: Any) -> str:
    text = _required_text(value, "opération autorisée")
    if text == ORDINARY_PURGE:
        raise ValueError("suppression ordinaire interdite")
    if text not in _ALLOWED_OPERATIONS:
        raise ValueError("opération administrative non autorisée")
    return text


def _required_request_operation(value: Any) -> str:
    text = _required_text(value, "opération demandée")
    if text == ORDINARY_PURGE:
        raise ValueError("suppression ordinaire interdite")
    if text not in _ALLOWED_OPERATIONS:
        raise ValueError("opération administrative non autorisée")
    return text


def _required_category_tuple(values: Sequence[RetentionCategory]) -> tuple[RetentionCategory, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError("catégories durables invalides")
    categories = tuple(values)
    if len(categories) == 0:
        raise ValueError("catégories durables absentes")
    for category in categories:
        if not isinstance(category, RetentionCategory):
            raise ValueError("RetentionCategory requise")
    return categories


def _required_text_tuple(values: Sequence[str], field_name: str) -> tuple[str, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError(f"{field_name} invalide")
    parsed = tuple(_required_text(value, field_name) for value in values)
    if len(parsed) == 0:
        raise ValueError(field_name)
    if len(set(parsed)) != len(parsed):
        raise ValueError(f"{field_name} dupliqué")
    return parsed


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(field_name)
    if value != value.strip():
        raise ValueError(f"{field_name} non normalisé")
    return value


def _required_positive_int(value: Any, field_name: str) -> int:
    if not isinstance(value, int):
        raise ValueError(f"{field_name} non entier")
    if value <= 0:
        raise ValueError(field_name)
    return value


def _required_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} non booléen")
    return value


def _is_command(value: str) -> bool:
    return value.startswith(_COMMAND_PREFIX)


__all__ = [
    "ADMINISTRATIVE_PURGE",
    "CATEGORY_CV_CONVERSATIONS",
    "CATEGORY_EG_CLAIMS",
    "CATEGORY_EV_GOVERNANCE_DECISIONS",
    "CATEGORY_EX_EXPERIMENT_RESULTS",
    "CATEGORY_KA_REGENERABLE_PROJECTIONS",
    "CATEGORY_RA_VERIFIED_ANSWERS",
    "CATEGORY_SD_STRATEGY_SNAPSHOTS",
    "CATEGORY_SP_CANONICAL_VERSIONS",
    "CATEGORY_SP_ORIGINALS",
    "LOGICAL_ARCHIVE",
    "ORDINARY_PURGE",
    "PURGE_CONVERSATION_CONTENT",
    "PURGE_REGENERABLE_PROJECTION",
    "RETENTION_POLICY_VERSION",
    "RetentionCategory",
    "RetentionOperationRequest",
    "RetentionPolicy",
    "build_m013_retention_policy",
]
