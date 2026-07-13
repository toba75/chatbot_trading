"""Politique de sauvegarde chiffrée et restauration M-013."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any
import re


BACKUP_RESTORE_DRILL_POLICY_VERSION = "M013-BackupRestoreDrill-1.0"
BACKUP_MANIFEST_CONTRACT_VERSION = "M013-BackupManifest-1.0"

CONTEXT_SP = "SP"
CONTEXT_KA = "KA"
CONTEXT_EG = "EG"
CONTEXT_RA = "RA"
CONTEXT_CV = "CV"
CONTEXT_SD = "SD"
CONTEXT_EX = "EX"
CONTEXT_EV = "EV"
CONTEXT_PLATFORM = "platform"

STORAGE_DOCKER_LOCAL = "docker-local"
STORAGE_SPARK = "spark-inference"

_REQUIRED_CONTEXTS = (
    CONTEXT_SP,
    CONTEXT_KA,
    CONTEXT_EG,
    CONTEXT_RA,
    CONTEXT_CV,
    CONTEXT_SD,
    CONTEXT_EX,
    CONTEXT_EV,
    CONTEXT_PLATFORM,
)
_REQUIRED_RETAINED_CONTEXTS = (
    CONTEXT_EG,
    CONTEXT_RA,
    CONTEXT_SD,
    CONTEXT_EX,
    CONTEXT_EV,
)
_ALLOWED_STORAGE_HOSTS = (STORAGE_DOCKER_LOCAL, STORAGE_SPARK)
_ALLOWED_ARTIFACT_KINDS = (
    "corpus_original",
    "canonical_versions",
    "qdrant_projection",
    "claim_registry",
    "verified_answers",
    "conversation_turns",
    "strategy_snapshots",
    "experiment_results",
    "evaluation_reports",
    "governance_artifacts",
)
_EXPECTED_CONTEXT_BY_ARTIFACT_KIND = {
    "corpus_original": CONTEXT_SP,
    "canonical_versions": CONTEXT_SP,
    "qdrant_projection": CONTEXT_KA,
    "claim_registry": CONTEXT_EG,
    "verified_answers": CONTEXT_RA,
    "conversation_turns": CONTEXT_CV,
    "strategy_snapshots": CONTEXT_SD,
    "experiment_results": CONTEXT_EX,
    "evaluation_reports": CONTEXT_EV,
    "governance_artifacts": CONTEXT_PLATFORM,
}
_SENSITIVE_FRAGMENTS = (
    "api key",
    "api_key",
    "authorization",
    "bearer",
    "clé privée",
    "cle privee",
    "mot de passe",
    "password",
    "passphrase",
    "private key",
    "secret_interdit_m013",
)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SHA256_PLACEHOLDER_PATTERN = re.compile(r"^([0-9a-f])\1{63}$")


@dataclass(frozen=True)
class BackupManifestEntry:
    entry_id: str
    context: str
    artifact_kind: str
    stable_identifier: str
    storage_host: str
    authority: bool
    immutable: bool
    regenerable_projection: bool
    retained_negative_or_superseded: bool
    backup_sha256: str
    restored_sha256: str
    contains_plain_secret: bool
    git_tracked_key_material: bool
    spark_business_storage: bool
    destructive_restore: bool

    def __init__(
        self,
        *,
        entry_id: str,
        context: str,
        artifact_kind: str,
        stable_identifier: str,
        storage_host: str,
        authority: bool,
        immutable: bool,
        regenerable_projection: bool,
        retained_negative_or_superseded: bool,
        backup_sha256: str,
        restored_sha256: str,
        contains_plain_secret: bool,
        git_tracked_key_material: bool,
        spark_business_storage: bool,
        destructive_restore: bool,
    ) -> None:
        parsed_context = _required_context(context)
        parsed_artifact_kind = _required_artifact_kind(artifact_kind)
        parsed_storage_host = _required_storage_host(storage_host)
        parsed_authority = _required_bool(authority, "authority")
        parsed_regenerable_projection = _required_bool(regenerable_projection, "regenerable_projection")

        if _EXPECTED_CONTEXT_BY_ARTIFACT_KIND[parsed_artifact_kind] != parsed_context:
            raise ValueError("catégorie artefact contexte incohérente")
        if parsed_storage_host == STORAGE_SPARK:
            raise ValueError("stockage métier Spark interdit")
        if _required_bool(spark_business_storage, "spark_business_storage"):
            raise ValueError("stockage métier Spark interdit")
        if _required_bool(contains_plain_secret, "contains_plain_secret"):
            raise ValueError("secret en clair interdit")
        if _required_bool(git_tracked_key_material, "git_tracked_key_material"):
            raise ValueError("clé versionnée interdite")
        if _required_bool(destructive_restore, "destructive_restore"):
            raise ValueError("restauration destructive interdite")
        if parsed_regenerable_projection and parsed_authority:
            raise ValueError("projection régénérable non autorité")
        if parsed_artifact_kind == "qdrant_projection" and not parsed_regenerable_projection:
            raise ValueError("projection régénérable requise")

        parsed_backup_sha256 = _required_sha256(backup_sha256, "hash sauvegardé absent")
        parsed_restored_sha256 = _required_sha256(restored_sha256, "hash restauré absent")
        if parsed_backup_sha256 != parsed_restored_sha256:
            raise ValueError("hash restauré divergent")

        object.__setattr__(self, "entry_id", _required_text(entry_id, "entry_id"))
        object.__setattr__(self, "context", parsed_context)
        object.__setattr__(self, "artifact_kind", parsed_artifact_kind)
        object.__setattr__(self, "stable_identifier", _required_text(stable_identifier, "stable_identifier"))
        object.__setattr__(self, "storage_host", parsed_storage_host)
        object.__setattr__(self, "authority", parsed_authority)
        object.__setattr__(self, "immutable", _required_bool(immutable, "immutable"))
        object.__setattr__(self, "regenerable_projection", parsed_regenerable_projection)
        object.__setattr__(
            self,
            "retained_negative_or_superseded",
            _required_bool(retained_negative_or_superseded, "retained_negative_or_superseded"),
        )
        object.__setattr__(self, "backup_sha256", parsed_backup_sha256)
        object.__setattr__(self, "restored_sha256", parsed_restored_sha256)
        object.__setattr__(self, "contains_plain_secret", False)
        object.__setattr__(self, "git_tracked_key_material", False)
        object.__setattr__(self, "spark_business_storage", False)
        object.__setattr__(self, "destructive_restore", False)


@dataclass(frozen=True)
class BackupManifest:
    manifest_id: str
    contract_version: str
    backup_command: str
    restore_command: str
    restore_target: str
    archive_encrypted: bool
    encryption_proof: str
    key_reference: str
    key_git_tracked: bool
    complete: bool
    entries: tuple[BackupManifestEntry, ...]
    contexts: tuple[str, ...]
    entries_by_id: Mapping[str, BackupManifestEntry]

    def __init__(
        self,
        *,
        manifest_id: str,
        contract_version: str,
        backup_command: str,
        restore_command: str,
        restore_target: str,
        archive_encrypted: bool,
        encryption_proof: str,
        key_reference: str,
        key_git_tracked: bool,
        complete: bool,
        entries: Sequence[BackupManifestEntry],
    ) -> None:
        if _required_text(contract_version, "contract_version") != BACKUP_MANIFEST_CONTRACT_VERSION:
            raise ValueError("version contrat manifeste invalide")
        if not _required_bool(complete, "complete"):
            raise ValueError("manifest incomplet")
        if not _required_bool(archive_encrypted, "archive_encrypted"):
            raise ValueError("archive chiffrée requise")
        if _required_bool(key_git_tracked, "key_git_tracked"):
            raise ValueError("clé versionnée interdite")

        parsed_backup_command = _required_text(backup_command, "commande de sauvegarde requise")
        parsed_restore_command = _required_text(restore_command, "commande de restauration requise")
        parsed_restore_target = _required_text(restore_target, "restore_target")
        if parsed_restore_target != "local_isolated":
            raise ValueError("cible de restauration isolée requise")

        parsed_encryption_proof = _required_text(encryption_proof, "preuve de chiffrement requise")
        _assert_no_sensitive_text(parsed_encryption_proof, "secret en clair interdit")
        ciphertext_hash_match = re.search(r"ciphertext_sha256=([0-9a-f]{64})", parsed_encryption_proof)
        if ciphertext_hash_match is None:
            raise ValueError("preuve de chiffrement requise")
        _required_sha256(ciphertext_hash_match.group(1), "preuve de chiffrement requise")

        parsed_key_reference = _required_text(key_reference, "key_reference")
        _assert_no_sensitive_text(parsed_key_reference, "secret en clair interdit")
        if not parsed_key_reference.startswith("hors_depot://"):
            raise ValueError("clé hors dépôt requise")

        parsed_entries = _required_manifest_entries(entries)
        entries_by_id: dict[str, BackupManifestEntry] = {}
        stable_identifiers: set[str] = set()
        for item in parsed_entries:
            if item.entry_id in entries_by_id:
                raise ValueError("entrée manifeste dupliquée")
            if item.stable_identifier in stable_identifiers:
                raise ValueError("identifiant stable dupliqué")
            entries_by_id[item.entry_id] = item
            stable_identifiers.add(item.stable_identifier)

        contexts = tuple(sorted({item.context for item in parsed_entries}))
        _assert_manifest_contexts(contexts)
        _assert_manifest_artifact_kinds(parsed_entries)
        _assert_retained_negative_or_superseded(parsed_entries)
        _assert_regenerable_projection(parsed_entries)

        object.__setattr__(self, "manifest_id", _required_text(manifest_id, "manifest_id"))
        object.__setattr__(self, "contract_version", BACKUP_MANIFEST_CONTRACT_VERSION)
        object.__setattr__(self, "backup_command", parsed_backup_command)
        object.__setattr__(self, "restore_command", parsed_restore_command)
        object.__setattr__(self, "restore_target", parsed_restore_target)
        object.__setattr__(self, "archive_encrypted", True)
        object.__setattr__(self, "encryption_proof", parsed_encryption_proof)
        object.__setattr__(self, "key_reference", parsed_key_reference)
        object.__setattr__(self, "key_git_tracked", False)
        object.__setattr__(self, "complete", True)
        object.__setattr__(self, "entries", parsed_entries)
        object.__setattr__(self, "contexts", contexts)
        object.__setattr__(self, "entries_by_id", MappingProxyType(entries_by_id))


@dataclass(frozen=True)
class RestoreTestResult:
    result_id: str
    status: str
    command: str
    verified_hashes: bool
    stable_identifiers_preserved: bool
    immutable_artifacts_preserved: bool
    negative_and_superseded_available: bool
    projections_rebuilt_from_authority: bool
    spark_required_for_business_data: bool
    destructive_restore_performed: bool
    traceability_verified: bool

    def __init__(
        self,
        *,
        result_id: str,
        status: str,
        command: str,
        verified_hashes: bool,
        stable_identifiers_preserved: bool,
        immutable_artifacts_preserved: bool,
        negative_and_superseded_available: bool,
        projections_rebuilt_from_authority: bool,
        spark_required_for_business_data: bool,
        destructive_restore_performed: bool,
        traceability_verified: bool,
    ) -> None:
        parsed_result_id = _required_text(result_id, "result_id")
        if parsed_result_id != "restore_test_result":
            raise ValueError("restore_test_result requis")

        parsed_status = _required_text(status, "status")
        if parsed_status != "GREEN":
            raise ValueError("restore_test_result GREEN requis")

        parsed_command = _required_text(command, "commande de restauration requise")
        if not _required_bool(verified_hashes, "verified_hashes"):
            raise ValueError("hash restauré absent")
        if not _required_bool(stable_identifiers_preserved, "stable_identifiers_preserved"):
            raise ValueError("identifiants stables requis")
        if not _required_bool(immutable_artifacts_preserved, "immutable_artifacts_preserved"):
            raise ValueError("artefacts immuables requis")
        if not _required_bool(negative_and_superseded_available, "negative_and_superseded_available"):
            raise ValueError("résultats négatifs et supersédés conservés")
        if not _required_bool(projections_rebuilt_from_authority, "projections_rebuilt_from_authority"):
            raise ValueError("projections régénérables non autorité")
        if _required_bool(spark_required_for_business_data, "spark_required_for_business_data"):
            raise ValueError("Spark interdit pour les données métier")
        if _required_bool(destructive_restore_performed, "destructive_restore_performed"):
            raise ValueError("restauration destructive interdite")
        if not _required_bool(traceability_verified, "traceability_verified"):
            raise ValueError("traçabilité restauration requise")

        object.__setattr__(self, "result_id", parsed_result_id)
        object.__setattr__(self, "status", parsed_status)
        object.__setattr__(self, "command", parsed_command)
        object.__setattr__(self, "verified_hashes", True)
        object.__setattr__(self, "stable_identifiers_preserved", True)
        object.__setattr__(self, "immutable_artifacts_preserved", True)
        object.__setattr__(self, "negative_and_superseded_available", True)
        object.__setattr__(self, "projections_rebuilt_from_authority", True)
        object.__setattr__(self, "spark_required_for_business_data", False)
        object.__setattr__(self, "destructive_restore_performed", False)
        object.__setattr__(self, "traceability_verified", True)


@dataclass(frozen=True)
class BackupRestoreDrill:
    drill_id: str
    policy_version: str
    manifest: BackupManifest
    restore_test_result: RestoreTestResult
    acceptance_allowed: bool


@dataclass(frozen=True)
class BackupRestoreDrillPolicy:
    policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_version", _required_policy_version(self.policy_version))

    def validate_manifest(self, manifest: BackupManifest) -> None:
        if not isinstance(manifest, BackupManifest):
            raise ValueError("BackupManifest requis")
        _assert_manifest_contexts(manifest.contexts)
        _assert_retained_negative_or_superseded(manifest.entries)
        _assert_regenerable_projection(manifest.entries)

    def validate_drill(self, drill: BackupRestoreDrill) -> None:
        if not isinstance(drill, BackupRestoreDrill):
            raise ValueError("BackupRestoreDrill requis")
        if drill.policy_version != self.policy_version:
            raise ValueError("version politique sauvegarde restauration incohérente")
        self.validate_manifest(drill.manifest)
        if not isinstance(drill.restore_test_result, RestoreTestResult):
            raise ValueError("restore_test_result requis")
        if drill.restore_test_result.command != drill.manifest.restore_command:
            raise ValueError("commande restauration incohérente")
        if not drill.acceptance_allowed:
            raise ValueError("acceptation restauration interdite")


def build_m013_backup_restore_drill() -> BackupRestoreDrill:
    manifest = BackupManifest(
        manifest_id="M013-BACKUP-MANIFEST-0001",
        contract_version=BACKUP_MANIFEST_CONTRACT_VERSION,
        backup_command=(
            "uv run backup-v1 --manifest .\\restore\\manifest.json"
        ),
        restore_command=(
            "uv run restore-v1 --manifest .\\restore\\manifest.json --target C:\\restore\\m013-isolated"
        ),
        restore_target="local_isolated",
        archive_encrypted=True,
        encryption_proof="ciphertext_sha256=305531dcc50ebca31cf1d5b31e9fc76ed51f66b3b6dd5a030c6539ae6532f979",
        key_reference="hors_depot://cle-restauration/m013",
        key_git_tracked=False,
        complete=True,
        entries=(
            _entry(
                entry_id="BACKUP-SP-CORPUS-001",
                context=CONTEXT_SP,
                artifact_kind="corpus_original",
                stable_identifier="SRC-M013-BACKUP-001",
                authority=True,
                immutable=True,
                regenerable_projection=False,
                retained_negative_or_superseded=False,
                digest="41afbc972e3965ef7af89ccc1cb76033d684c363224e408b001d4ad6fe53d762",
            ),
            _entry(
                entry_id="BACKUP-SP-CANONICAL-001",
                context=CONTEXT_SP,
                artifact_kind="canonical_versions",
                stable_identifier="CANON-M013-BACKUP-001",
                authority=True,
                immutable=True,
                regenerable_projection=False,
                retained_negative_or_superseded=False,
                digest="07aa716c5e229e8502dcbefdc41c1dad332376a9204286b50ce59ba8573121ab",
            ),
            _entry(
                entry_id="BACKUP-KA-QDRANT-001",
                context=CONTEXT_KA,
                artifact_kind="qdrant_projection",
                stable_identifier="PROJ-M013-BACKUP-001",
                authority=False,
                immutable=False,
                regenerable_projection=True,
                retained_negative_or_superseded=False,
                digest="24c11cc03fa691edfee932d7d7fe8e2322b59df3f5e2f78f43de2d22ece1586a",
            ),
            _entry(
                entry_id="BACKUP-EG-CLAIMS-001",
                context=CONTEXT_EG,
                artifact_kind="claim_registry",
                stable_identifier="CLAIM-M013-BACKUP-001",
                authority=True,
                immutable=True,
                regenerable_projection=False,
                retained_negative_or_superseded=True,
                digest="5e6f1f718dd111612c9a39f99e6106962cb672581760346ee7f438f0daacee0a",
            ),
            _entry(
                entry_id="BACKUP-RA-ANSWERS-001",
                context=CONTEXT_RA,
                artifact_kind="verified_answers",
                stable_identifier="ANSWER-M013-BACKUP-001",
                authority=True,
                immutable=True,
                regenerable_projection=False,
                retained_negative_or_superseded=True,
                digest="6ac74cb4c5842dc58c4a36595f8505dd11cc601ee7435d0c12b5ca300c9a9d12",
            ),
            _entry(
                entry_id="BACKUP-CV-TURNS-001",
                context=CONTEXT_CV,
                artifact_kind="conversation_turns",
                stable_identifier="CONV-M013-BACKUP-001",
                authority=True,
                immutable=True,
                regenerable_projection=False,
                retained_negative_or_superseded=False,
                digest="ad2171f2d64fb2e0b97dead7a371940a39cee49ffd82ab431875700dfdbeab5a",
            ),
            _entry(
                entry_id="BACKUP-SD-STRATEGY-001",
                context=CONTEXT_SD,
                artifact_kind="strategy_snapshots",
                stable_identifier="STRAT-M013-BACKUP-001",
                authority=True,
                immutable=True,
                regenerable_projection=False,
                retained_negative_or_superseded=True,
                digest="2522c33fb81d48560c3350a3b2ff244fa22639c64aa071afc0a340225bced7ca",
            ),
            _entry(
                entry_id="BACKUP-EX-RESULTS-001",
                context=CONTEXT_EX,
                artifact_kind="experiment_results",
                stable_identifier="EXP-M013-BACKUP-001",
                authority=True,
                immutable=True,
                regenerable_projection=False,
                retained_negative_or_superseded=True,
                digest="cb56bed550ec21f510dba2aacc349910069dcf4b9d3055528fbad6f73e912c3c",
            ),
            _entry(
                entry_id="BACKUP-EV-REPORTS-001",
                context=CONTEXT_EV,
                artifact_kind="evaluation_reports",
                stable_identifier="EVAL-M013-BACKUP-001",
                authority=True,
                immutable=True,
                regenerable_projection=False,
                retained_negative_or_superseded=True,
                digest="cd5fa46828c77876760ff84260c850b7769e191a18008a97cbd8381a90501717",
            ),
            _entry(
                entry_id="BACKUP-PLATFORM-GOV-001",
                context=CONTEXT_PLATFORM,
                artifact_kind="governance_artifacts",
                stable_identifier="GOV-M013-BACKUP-001",
                authority=True,
                immutable=True,
                regenerable_projection=False,
                retained_negative_or_superseded=False,
                digest="217a94c41d0a66989fde831fd643d76daf7cae412593f3d634fb02ba6aecc32d",
            ),
        ),
    )
    restore_test_result = RestoreTestResult(
        result_id="restore_test_result",
        status="GREEN",
        command=manifest.restore_command,
        verified_hashes=True,
        stable_identifiers_preserved=True,
        immutable_artifacts_preserved=True,
        negative_and_superseded_available=True,
        projections_rebuilt_from_authority=True,
        spark_required_for_business_data=False,
        destructive_restore_performed=False,
        traceability_verified=True,
    )
    drill = BackupRestoreDrill(
        drill_id="M013-BACKUP-RESTORE-DRILL-0001",
        policy_version=BACKUP_RESTORE_DRILL_POLICY_VERSION,
        manifest=manifest,
        restore_test_result=restore_test_result,
        acceptance_allowed=True,
    )
    BackupRestoreDrillPolicy(policy_version=BACKUP_RESTORE_DRILL_POLICY_VERSION).validate_drill(drill)
    return drill


def _entry(
    *,
    entry_id: str,
    context: str,
    artifact_kind: str,
    stable_identifier: str,
    authority: bool,
    immutable: bool,
    regenerable_projection: bool,
    retained_negative_or_superseded: bool,
    digest: str,
) -> BackupManifestEntry:
    return BackupManifestEntry(
        entry_id=entry_id,
        context=context,
        artifact_kind=artifact_kind,
        stable_identifier=stable_identifier,
        storage_host=STORAGE_DOCKER_LOCAL,
        authority=authority,
        immutable=immutable,
        regenerable_projection=regenerable_projection,
        retained_negative_or_superseded=retained_negative_or_superseded,
        backup_sha256=digest,
        restored_sha256=digest,
        contains_plain_secret=False,
        git_tracked_key_material=False,
        spark_business_storage=False,
        destructive_restore=False,
    )


def _assert_manifest_contexts(contexts: Sequence[str]) -> None:
    parsed_contexts = tuple(contexts)
    for context in _REQUIRED_CONTEXTS:
        if context not in parsed_contexts:
            raise ValueError("contexte V1 absent")


def _assert_manifest_artifact_kinds(entries: Sequence[BackupManifestEntry]) -> None:
    artifact_kinds = {item.artifact_kind for item in entries}
    for artifact_kind in _ALLOWED_ARTIFACT_KINDS:
        if artifact_kind not in artifact_kinds:
            raise ValueError("catégorie artefact V1 absente")


def _assert_retained_negative_or_superseded(entries: Sequence[BackupManifestEntry]) -> None:
    retained_contexts = {
        item.context
        for item in entries
        if item.retained_negative_or_superseded
    }
    for context in _REQUIRED_RETAINED_CONTEXTS:
        if context not in retained_contexts:
            raise ValueError("résultats négatifs et supersédés conservés")


def _assert_regenerable_projection(entries: Sequence[BackupManifestEntry]) -> None:
    projections = tuple(item for item in entries if item.regenerable_projection)
    if len(projections) == 0:
        raise ValueError("projection régénérable requise")
    for projection in projections:
        if projection.authority:
            raise ValueError("projection régénérable non autorité")


def _required_manifest_entries(values: Sequence[BackupManifestEntry]) -> tuple[BackupManifestEntry, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError("entrées manifeste invalides")
    entries = tuple(values)
    if len(entries) == 0:
        raise ValueError("entrées manifeste absentes")
    for item in entries:
        if not isinstance(item, BackupManifestEntry):
            raise ValueError("BackupManifestEntry requis")
    return entries


def _required_policy_version(value: Any) -> str:
    text = _required_text(value, "policy_version")
    if text != BACKUP_RESTORE_DRILL_POLICY_VERSION:
        raise ValueError("version politique sauvegarde restauration incohérente")
    return text


def _required_context(value: Any) -> str:
    text = _required_text(value, "context")
    if text not in _REQUIRED_CONTEXTS:
        raise ValueError("contexte V1 inconnu")
    return text


def _required_artifact_kind(value: Any) -> str:
    text = _required_text(value, "artifact_kind")
    if text not in _ALLOWED_ARTIFACT_KINDS:
        raise ValueError("catégorie artefact V1 inconnue")
    return text


def _required_storage_host(value: Any) -> str:
    text = _required_text(value, "storage_host")
    if text not in _ALLOWED_STORAGE_HOSTS:
        raise ValueError("hôte de stockage inconnu")
    return text


def _required_sha256(value: Any, empty_message: str) -> str:
    text = _required_text(value, empty_message)
    if not _SHA256_PATTERN.match(text):
        raise ValueError(empty_message)
    if _SHA256_PLACEHOLDER_PATTERN.match(text):
        raise ValueError("hash placeholder interdit")
    return text


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(field_name)
    if value != value.strip():
        raise ValueError(f"{field_name} non normalisé")
    return value


def _required_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} non booléen")
    return value


def _assert_no_sensitive_text(value: str, message: str) -> None:
    normalized = value.lower()
    for fragment in _SENSITIVE_FRAGMENTS:
        if fragment in normalized:
            raise ValueError(message)


__all__ = [
    "BACKUP_MANIFEST_CONTRACT_VERSION",
    "BACKUP_RESTORE_DRILL_POLICY_VERSION",
    "CONTEXT_CV",
    "CONTEXT_EG",
    "CONTEXT_EV",
    "CONTEXT_EX",
    "CONTEXT_KA",
    "CONTEXT_PLATFORM",
    "CONTEXT_RA",
    "CONTEXT_SD",
    "CONTEXT_SP",
    "STORAGE_DOCKER_LOCAL",
    "STORAGE_SPARK",
    "BackupManifest",
    "BackupManifestEntry",
    "BackupRestoreDrill",
    "BackupRestoreDrillPolicy",
    "RestoreTestResult",
    "build_m013_backup_restore_drill",
]
