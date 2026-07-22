from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest


def test_environment_resource_isolation_unit() -> None:
    from app.platform.configuration import load_application_configuration
    from app.platform.environment_resources import (
        RESOURCE_ISOLATION_VIOLATION,
        EnvironmentResourceIsolationError,
        validate_environment_resource_matrix,
    )

    repository_root = Path(__file__).resolve().parents[4]
    configurations = {
        environment: load_application_configuration(
            config_path=repository_root / "config" / "environments" / f"{environment}.yaml",
            environment_snapshot={},
        )
        for environment in ("development", "test", "production")
    }
    validate_environment_resource_matrix(configurations, repository_root=repository_root)

    def assert_collision(mutated_test_configuration) -> None:
        collided = dict(configurations)
        collided["test"] = mutated_test_configuration
        with pytest.raises(EnvironmentResourceIsolationError, match=RESOURCE_ISOLATION_VIOLATION):
            validate_environment_resource_matrix(collided, repository_root=repository_root)

    development = configurations["development"]
    test = configurations["test"]

    assert_collision(
        replace(
            test,
            services=replace(
                test.services,
                postgres=replace(test.services.postgres, url=development.services.postgres.url),
            ),
        )
    )
    assert_collision(
        replace(
            test,
            services=replace(
                test.services,
                postgres=replace(test.services.postgres, database=development.services.postgres.database),
            ),
        )
    )
    assert_collision(
        replace(
            test,
            services=replace(
                test.services,
                postgres=replace(test.services.postgres, role=development.services.postgres.role),
            ),
        )
    )
    assert_collision(
        replace(
            test,
            services=replace(
                test.services,
                qdrant=replace(
                    test.services.qdrant,
                    collections=replace(
                        test.services.qdrant.collections,
                        knowledge_access=development.services.qdrant.collections.knowledge_access,
                    ),
                ),
            ),
        )
    )
    assert_collision(
        replace(
            test,
            services=replace(
                test.services,
                workers=replace(
                    test.services.workers,
                    outbox_namespace=development.services.workers.outbox_namespace,
                ),
            ),
        )
    )
    assert_collision(
        replace(
            test,
            security=replace(
                test.security,
                secrets=replace(
                    test.security.secrets,
                    qdrant_api_key_path=development.security.secrets.qdrant_api_key_path,
                ),
            ),
        )
    )
    assert_collision(
        replace(
            test,
            paths=replace(test.paths, data_root=development.paths.corpus_root),
        )
    )

    missing_profile = dict(configurations)
    del missing_profile["production"]
    with pytest.raises(EnvironmentResourceIsolationError, match=RESOURCE_ISOLATION_VIOLATION):
        validate_environment_resource_matrix(missing_profile, repository_root=repository_root)

    aliased_profile = dict(configurations)
    aliased_profile["test"] = replace(
        test,
        application=replace(test.application, environment="development"),
    )
    with pytest.raises(EnvironmentResourceIsolationError, match=RESOURCE_ISOLATION_VIOLATION):
        validate_environment_resource_matrix(aliased_profile, repository_root=repository_root)

    malformed_postgres_url = dict(configurations)
    malformed_postgres_url["test"] = replace(
        test,
        services=replace(
            test.services,
            postgres=replace(
                test.services.postgres,
                url="postgresql+psycopg://wrong-role@postgres-test/wrong-database",
            ),
        ),
    )
    with pytest.raises(EnvironmentResourceIsolationError, match=RESOURCE_ISOLATION_VIOLATION):
        validate_environment_resource_matrix(malformed_postgres_url, repository_root=repository_root)
