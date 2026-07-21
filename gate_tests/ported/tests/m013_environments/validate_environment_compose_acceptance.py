from __future__ import annotations

from pathlib import Path


def test_environment_compose_acceptance() -> None:
    # Given les trois configurations et leurs piles Compose dédiées existent.
    # When Docker Compose effectue le rendu réel de chaque profil.
    # Then les projets, réseaux, volumes, secrets et montages sont étanches,
    # et chaque service applicatif reçoit exactement la configuration du profil.
    from app.platform.environment_compose import (
        APPLICATION_SERVICE_IDS,
        ENVIRONMENTS,
        environment_stack_definition,
        render_environment_compose,
        validate_environment_compose_matrix,
    )

    repository_root = Path(__file__).resolve().parents[4]
    technical_environment = {
        "OSTRADING_IMAGE_REVISION": "a" * 40,
        "OSTRADING_POSTGRES_SCHEMA_VERSION": "019",
    }
    definitions = {
        environment: environment_stack_definition(
            environment,
            repository_root=repository_root,
        )
        for environment in ENVIRONMENTS
    }
    rendered = {
        environment: render_environment_compose(
            definition,
            technical_environment=technical_environment,
        )
        for environment, definition in definitions.items()
    }

    matrix = validate_environment_compose_matrix(
        rendered,
        definitions=definitions,
    )
    assert tuple(matrix) == ENVIRONMENTS
    assert len({definition.project_name for definition in definitions.values()}) == 3
    assert len({definition.edge_port for definition in definitions.values()}) == 3

    mutable_names: set[str] = set()
    for environment in ENVIRONMENTS:
        definition = definitions[environment]
        document = rendered[environment]
        assert document["name"] == definition.project_name
        assert Path(definition.configuration_path).is_file()
        assert Path(definition.compose_path).is_file()
        assert Path(definition.caddyfile_path).is_file()
        assert Path(definition.secrets_path).name == environment

        for service_id in APPLICATION_SERVICE_IDS:
            service = document["services"][service_id]
            assert "environment" not in service
            assert "env_file" not in service
            mounts = {mount["target"]: mount for mount in service["volumes"]}
            assert mounts["/workspace/config/application.yaml"]["read_only"] is True
            assert Path(mounts["/workspace/config/application.yaml"]["source"]).resolve() == Path(
                definition.configuration_path
            ).resolve()
            assert mounts["/workspace/config/application.schema.json"]["read_only"] is True
            secret_target = f"/workspace/config/secrets/{environment}"
            assert mounts[secret_target]["read_only"] is True
            assert Path(mounts[secret_target]["source"]).resolve() == Path(
                definition.secrets_path
            ).resolve()

        for resource in (*document["volumes"].values(), *document["networks"].values()):
            resource_name = resource["name"]
            assert environment in resource_name
            assert resource_name not in mutable_names
            mutable_names.add(resource_name)

        assert set(document.get("secrets", {})) == {"local_api_token", "postgres_password"}
        for secret in document["secrets"].values():
            assert environment in Path(secret["file"]).parts

        postgres_environment = document["services"]["postgres"]["environment"]
        assert set(postgres_environment) == {
            "POSTGRES_DB",
            "POSTGRES_PASSWORD_FILE",
            "POSTGRES_USER",
        }

        edge_ports = document["services"]["edge-gateway"]["ports"]
        assert edge_ports == [
            {
                "mode": "ingress",
                "target": 8443,
                "published": str(definition.edge_port),
                "protocol": "tcp",
                "host_ip": "127.0.0.1",
            }
        ]

        ocr_runtime = document["services"]["ocr-runtime"]
        assert ocr_runtime["privileged"] is True
        assert ocr_runtime["image"].startswith(
            "docker:27.5.1-dind@sha256:aa3df78ecf320f5fafdce71c659f1629e96e9de0968305fe1de670e0ca9176ce"
        )
        assert set(ocr_runtime["networks"]) == {"ocr-control", "ocr-egress"}
        assert "/var/run/docker.sock" not in {
            mount["source"]
            for service in document["services"].values()
            for mount in service.get("volumes", [])
            if mount.get("type") == "bind"
        }
        worker_documents = document["services"]["worker-documents"]
        assert "ocr-control" in worker_documents["networks"]
        assert worker_documents["depends_on"]["ocr-runtime"]["condition"] == "service_healthy"
        assert worker_documents["deploy"]["resources"]["limits"]["memory"] == str(
            8 * 1024**3
        )
        assert worker_documents["deploy"]["resources"]["limits"]["cpus"] == 4
        assert worker_documents["healthcheck"]["timeout"] == "30s"
        worker_mounts = {mount["target"]: mount for mount in worker_documents["volumes"]}
        for asset_kind in ("native", "granite"):
            target = f"/workspace/data/environments/{environment}/docling_assets/{asset_kind}"
            assert worker_mounts[target]["read_only"] is True
            assert Path(worker_mounts[target]["source"]).resolve() == (
                repository_root / "data" / "docling_assets" / asset_kind
            ).resolve()

    spark_endpoints = {
        document["services"]["llm-gateway"]["labels"]["org.ostrading.spark-endpoint"]
        for document in rendered.values()
    }
    assert spark_endpoints == {"http://192.168.1.120:8000/v1"}

    dockerfile = (repository_root / "deploy" / "local-compose" / "Dockerfile").read_text(
        encoding="utf-8"
    )
    for environment in ENVIRONMENTS:
        assert f"/workspace/data/environments/{environment}" in dockerfile
    assert "FROM docker:27.5.1-cli@sha256:851f91d241214e7c6db86513b270d58776379aacc5eb9c4a87e5b47115e3065c AS docker-cli" in dockerfile
    assert "config/ocrmypdf-image.json ./config/ocrmypdf-image.json" in dockerfile
    assert "config/docling-assets.native.json ./config/docling-assets.native.json" in dockerfile
    assert "config/docling-assets.granite.json ./config/docling-assets.granite.json" in dockerfile
