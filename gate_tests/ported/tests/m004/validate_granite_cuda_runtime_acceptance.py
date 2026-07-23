"""Contrat d'exécution CUDA stricte de Granite-Docling (ADR-051)."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from app.platform.local_compose import (
    parse_local_compose_document,
    validate_local_compose,
)


REPO_ROOT = Path(__file__).resolve().parents[4]


def _torch_runtime(
    *, built: bool, available: bool, device_count: int
) -> SimpleNamespace:
    return SimpleNamespace(
        backends=SimpleNamespace(cuda=SimpleNamespace(is_built=lambda: built)),
        cuda=SimpleNamespace(
            is_available=lambda: available,
            device_count=lambda: device_count,
        ),
    )


def test_granite_exige_cuda_zero_sans_fallback_cpu(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given le worker documentaire courant traite une page routée vers Granite-Docling.
    worker = importlib.import_module(
        "app.source_processing.adapters.docling_granite_worker"
    )

    # When le runtime CUDA expose exactement la RTX locale et construit le pipeline.
    with monkeypatch.context() as cuda_context:
        cuda_context.setitem(
            sys.modules,
            "torch",
            _torch_runtime(built=True, available=True, device_count=1),
        )
        device = worker._required_cuda_device()
    pipeline_options = worker._build_pipeline_options(
        assets_root=tmp_path,
        device=device,
    )

    # Then Granite cible CUDA 0 et le conteneur worker ne reçoit que le GPU 0.
    assert device == "cuda:0"
    assert pipeline_options.accelerator_options.device == "cuda:0"
    for compose_path in (
        "deploy/environments/compose.base.yaml",
        "deploy/local-compose/compose.yaml",
    ):
        compose = yaml.safe_load((REPO_ROOT / compose_path).read_text(encoding="utf-8"))
        document_worker = compose["services"]["worker-documents"]
        assert "gpus" not in document_worker
        assert document_worker["deploy"]["resources"]["reservations"]["devices"] == [
            {
                "driver": "nvidia",
                "device_ids": ["0"],
                "capabilities": ["gpu"],
            }
        ]
        assert "environment" not in document_worker
        assert (
            "/triton-cache:rw,exec,nosuid,nodev,size=128m,mode=0770,gid=31000"
            in document_worker["tmpfs"]
        )
    local_compose_path = REPO_ROOT / "deploy/local-compose/compose.yaml"
    validate_local_compose(
        parse_local_compose_document(
            local_compose_path.read_text(encoding="utf-8"),
            source=str(local_compose_path),
        )
    )
    worker_dockerfile = (REPO_ROOT / "deploy/local-compose/Dockerfile").read_text(
        encoding="utf-8"
    )
    worker_stage = worker_dockerfile.split(
        "FROM runtime AS worker-documents", maxsplit=1
    )[1].split("FROM runtime AS worker-projection", maxsplit=1)[0]
    assert 'ENV TRITON_CACHE_DIR="/triton-cache"' in worker_stage
    assert "snapshot.debian.org/archive/debian/20250203T000000Z" in worker_stage
    assert (
        "snapshot.debian.org/archive/debian-security/20250203T000000Z" in worker_stage
    )
    assert "gcc=4:12.2.0-3" in worker_stage
    assert "libc6-dev=2.36-9+deb12u9" in worker_stage
    assert worker_stage.index("USER root") < worker_stage.index("USER ostrading")

    # Then l'absence de CUDA est terminale et ne sélectionne jamais le CPU.
    with monkeypatch.context() as cpu_only_context:
        cpu_only_context.setitem(
            sys.modules,
            "torch",
            _torch_runtime(built=False, available=False, device_count=0),
        )
        with pytest.raises(
            worker.GraniteDoclingWorkerError,
            match="GRANITE_CUDA_UNAVAILABLE",
        ) as failure:
            worker._required_cuda_device()
    assert failure.value.code == "GRANITE_CUDA_UNAVAILABLE"
