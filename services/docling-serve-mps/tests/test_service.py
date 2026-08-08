import hashlib
import json
from pathlib import Path

import pytest

from docling_serve_mps.service import (
    LABEL,
    MODEL_DIRECTORY,
    MODEL_REPOSITORY,
    launch_agent,
    service_environment,
    verify_model_assets,
)


def test_launch_agent_exposes_the_existing_api_without_key(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"

    environment = service_environment(repo_root, home)
    agent = launch_agent(repo_root, home)

    assert environment["UVICORN_HOST"] == "0.0.0.0"
    assert environment["UVICORN_PORT"] == "5001"
    assert environment["DOCLING_DEVICE"] == "mps"
    assert environment["DOCLING_SERVE_ALLOWED_VLM_ENGINES"] == "auto_inline"
    assert "DOCLING_SERVE_API_KEY" not in environment
    assert agent["Label"] == LABEL
    assert agent["KeepAlive"] is True
    assert agent["ProgramArguments"][-2:] == ["--repo-root", str(repo_root)]


def test_model_manifest_rejects_unlisted_files(tmp_path: Path) -> None:
    model_root = tmp_path / "data/docling_assets" / MODEL_DIRECTORY
    model_root.mkdir(parents=True)
    model_file = model_root / "model.safetensors"
    model_file.write_bytes(b"mlx")
    relative_path = f"{MODEL_DIRECTORY}/model.safetensors"
    manifest = {
        "model_repository": MODEL_REPOSITORY,
        "model_revision": "revision",
        "assets": [
            {
                "relative_path": relative_path,
                "sha256": hashlib.sha256(b"mlx").hexdigest(),
            }
        ],
    }
    config = tmp_path / "config"
    config.mkdir()
    (config / "granite-docling-258M-mlx.manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    assert verify_model_assets(tmp_path) == "revision"

    (model_root / "unexpected.json").write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="ajoutés"):
        verify_model_assets(tmp_path)
