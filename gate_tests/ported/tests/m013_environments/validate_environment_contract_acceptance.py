"""Contrat documentaire exécutable de M13-environments T-002.

Scénario BDD:
Given un opérateur choisit development, test ou production.
When le contrat de configuration de ce profil est validé.
Then son identité est complète, ses ressources sont isolées et aucune valeur
implicite ou variable système ne participe à sa configuration.
"""

from __future__ import annotations

from pathlib import Path


_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
_SPECIFICATION_PATH = (
    _REPOSITORY_ROOT
    / "docs"
    / "specs"
    / "m013_environments_environnements_explicites.md"
)
_ADR_016_PATH = (
    _REPOSITORY_ROOT
    / "docs"
    / "adr"
    / "ADR-016-configuration-applicative-fichier-unique.md"
)
_ADR_045_PATH = (
    _REPOSITORY_ROOT
    / "docs"
    / "adr"
    / "ADR-045-profils-execution-explicites-donnees-etanches.md"
)
_ADR_INDEX_PATH = _REPOSITORY_ROOT / "docs" / "adr" / "index.md"


def _read_required(path: Path, error_code: str) -> str:
    assert path.is_file(), f"{error_code}:{path.relative_to(_REPOSITORY_ROOT).as_posix()}"
    return path.read_text(encoding="utf-8")


def test_validate_environment_contract_acceptance() -> None:
    _assert_adr_045_replaces_adr_016_explicitly()
    _assert_contract_closes_profiles_identity_and_configuration_sources()
    _assert_contract_isolates_every_mutable_resource_and_worker()


def _assert_adr_045_replaces_adr_016_explicitly() -> None:
    adr_016 = _read_required(_ADR_016_PATH, "ADR_016_REQUIRED")
    adr_045 = _read_required(_ADR_045_PATH, "ADR_045_REQUIRED")
    adr_index = _read_required(_ADR_INDEX_PATH, "ADR_INDEX_REQUIRED")

    assert "**Statut :** Remplacée" in adr_016
    assert "**Remplacée par :** ADR-045" in adr_016
    assert "**Statut :** Acceptée" in adr_045
    assert "**Remplace :** ADR-016" in adr_045
    assert "ADR-045-profils-execution-explicites-donnees-etanches.md" in adr_index
    assert "| [ADR-045]" in adr_index
    assert "Prochaine ADR technique: ADR-046" in adr_index


def _assert_contract_closes_profiles_identity_and_configuration_sources() -> None:
    specification = _read_required(
        _SPECIFICATION_PATH,
        "M13_ENVIRONMENTS_SPEC_REQUIRED",
    )

    for profile in ("development", "test", "production"):
        assert f"`{profile}`" in specification
        assert f"`config/environments/{profile}.yaml`" in specification

    for required_contract in (
        "`ApplicationEnvironment`",
        "`environment`",
        "`deployment_id`",
        "configuration complète",
        "aucune fusion",
        "aucun héritage",
        "ensemble fermé",
        "`CONFIG_ENVIRONMENT_UNKNOWN`",
        "`CONFIG_ENVIRONMENT_MISMATCH`",
        "`DATASTORE_ENVIRONMENT_MISMATCH`",
        "`WORKER_ENVIRONMENT_MISMATCH`",
    ):
        assert required_contract in specification

    for forbidden_input in (
        "`.env`",
        "`os.environ`",
        "`getenv`",
        "`env_file`",
        "`environment:`",
    ):
        assert forbidden_input in specification

    assert "aucune valeur par défaut" in specification
    assert "aucun fallback" in specification
    assert "profil `local`" in specification


def _assert_contract_isolates_every_mutable_resource_and_worker() -> None:
    specification = _read_required(
        _SPECIFICATION_PATH,
        "M13_ENVIRONMENTS_SPEC_REQUIRED",
    )

    for mutable_resource in (
        "PostgreSQL",
        "Qdrant",
        "rôles",
        "credentials",
        "volumes",
        "réseaux",
        "racines de fichiers",
        "artefacts",
        "caches",
        "files de travaux",
        "outbox",
        "secrets",
    ):
        assert mutable_resource in specification

    for worker_invariant in (
        "avant toute lecture",
        "avant toute écriture",
        "avant toute migration",
        "avant toute prise de job",
        "API",
        "worker",
        "job",
        "état de santé",
        "progression publique",
        "preuve d'exécution",
    ):
        assert worker_invariant in specification

    assert "distinct" in specification
    assert "secret en clair" in specification
