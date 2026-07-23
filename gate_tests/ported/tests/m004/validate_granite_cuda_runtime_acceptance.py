"""Contrat d'exécution CUDA stricte de Granite-Docling (ADR-051)."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[4]


def _torch_runtime(*, built: bool, available: bool, device_count: int) -> SimpleNamespace:
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

    # Then Granite cible CUDA 0 et le conteneur worker reçoit explicitement le GPU.
    assert device == "cuda:0"
    assert pipeline_options.accelerator_options.device == "cuda:0"
    compose = yaml.safe_load(
        (REPO_ROOT / "deploy/local-compose/compose.yaml").read_text(encoding="utf-8")
    )
    assert compose["services"]["worker-documents"]["gpus"] == "all"

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
