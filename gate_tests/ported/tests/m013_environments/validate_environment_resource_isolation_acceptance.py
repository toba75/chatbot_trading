from __future__ import annotations

import json
from pathlib import Path


def test_environment_resource_isolation_acceptance(tmp_path: Path) -> None:
    from app.platform.configuration import load_application_configuration
    from app.platform.datastore_identity import DatastoreIdentity, FileRootIdentityPreflight
    from app.platform.environment_resources import (
        inventory_context_mutable_resources,
        mutable_file_roots,
        validate_environment_resource_matrix,
    )

    repository_root = Path(__file__).resolve().parents[4]
    configuration_paths = {
        environment: repository_root / "config" / "environments" / f"{environment}.yaml"
        for environment in ("development", "test", "production")
    }
    assert all(path.is_file() for path in configuration_paths.values())

    configurations = {
        environment: load_application_configuration(
            config_path=path,
            environment_snapshot={},
        )
        for environment, path in configuration_paths.items()
    }
    matrix = validate_environment_resource_matrix(
        configurations,
        repository_root=repository_root,
    )

    registry_payload = json.loads(
        (repository_root / "app" / "context_registry.json").read_text(encoding="utf-8-sig")
    )
    expected_storage_ids = {
        storage["id"]
        for context in registry_payload["contexts"]
        for storage in context["owned_storages"]
    } | {
        storage["id"]
        for storage in registry_payload["platform"]["owned_storages"]
    }
    assert set(inventory_context_mutable_resources(repository_root / "app" / "context_registry.json")) == (
        expected_storage_ids
    )
    assert set(matrix.context_storage_ids) == expected_storage_ids

    for environment, configuration in configurations.items():
        assert configuration.application.environment == environment
        assert environment in configuration.application.deployment_id
        assert environment in configuration.services.postgres.database
        assert environment in configuration.services.postgres.role
        assert environment in configuration.services.postgres.data_volume
        assert environment in configuration.services.qdrant.instance_id
        assert environment in configuration.services.qdrant.storage_volume
        assert environment in configuration.services.qdrant.collections.datastore_identity
        assert environment in configuration.services.qdrant.collections.knowledge_access
        assert environment in configuration.services.workers.queue_name
        assert environment in configuration.services.workers.outbox_namespace
        assert environment in configuration.services.workers.progress_namespace

    sentinels = {
        environment: f"SENTINEL-{environment}-T005"
        for environment in configurations
    }
    roots_by_environment: dict[str, dict[str, Path]] = {}
    for environment, configuration in configurations.items():
        roots = {
            name: tmp_path / relative_root
            for name, relative_root in mutable_file_roots(configuration).items()
        }
        roots_by_environment[environment] = roots
        identity = DatastoreIdentity(
            environment=environment,
            deployment_id=configuration.application.deployment_id,
        )
        for resource_name, root in roots.items():
            FileRootIdentityPreflight(root=root, expected_identity=identity).run(
                initialize_if_empty=True,
            )
            suffix = ".pdf" if resource_name == "corpus_root" else ".sentinel"
            (root / f"{sentinels[environment]}{suffix}").write_bytes(
                b"%PDF-1.7\n% T-005 real filesystem sentinel\n"
                if suffix == ".pdf"
                else sentinels[environment].encode("ascii")
            )

    for producer_environment, sentinel in sentinels.items():
        for observer_environment, observer_roots in roots_by_environment.items():
            for resource_name, observer_root in observer_roots.items():
                suffix = ".pdf" if resource_name == "corpus_root" else ".sentinel"
                visible = (observer_root / f"{sentinel}{suffix}").exists()
                assert visible is (observer_environment == producer_environment)

    production_secret_paths = {
        value
        for value in matrix.coordinates["production"].values()
        if value.startswith("config/secrets/production/")
    }
    for environment in ("development", "test"):
        non_production_text = configuration_paths[environment].read_text(encoding="utf-8-sig")
        assert all(secret_path not in non_production_text for secret_path in production_secret_paths)
