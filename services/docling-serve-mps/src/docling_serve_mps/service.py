from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import plistlib
import sys
from pathlib import Path

LABEL = "ch.chatbot-trading.docling-serve"
MODEL_REPOSITORY = "ibm-granite/granite-docling-258M-mlx"
MODEL_DIRECTORY = "ibm-granite--granite-docling-258M-mlx"
MANIFEST = "config/granite-docling-258M-mlx.manifest.json"


def service_environment(repo_root: Path, home: Path) -> dict[str, str]:
    project = repo_root / "services/docling-serve-mps"
    return {
        "HOME": str(home),
        "PATH": (
            f"{project / '.venv/bin'}:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        ),
        "PYTHONUNBUFFERED": "1",
        "UVICORN_HOST": "0.0.0.0",
        "UVICORN_PORT": "5001",
        "UVICORN_WORKERS": "1",
        "DOCLING_DEVICE": "mps",
        "DOCLING_NUM_THREADS": "4",
        "DOCLING_PERF_PAGE_BATCH_SIZE": "4",
        "DOCLING_SERVE_ARTIFACTS_PATH": str(repo_root / "data/docling_assets"),
        "DOCLING_SERVE_SCRATCH_PATH": str(
            home / "Library/Caches/chatbot-trading/docling-serve"
        ),
        "DOCLING_SERVE_ENABLE_UI": "false",
        "DOCLING_SERVE_ENABLE_REMOTE_SERVICES": "false",
        "DOCLING_SERVE_ALLOW_EXTERNAL_PLUGINS": "false",
        "DOCLING_SERVE_ALLOW_CUSTOM_VLM_CONFIG": "false",
        "DOCLING_SERVE_ALLOWED_VLM_PRESETS": "granite_docling",
        "DOCLING_SERVE_ALLOWED_VLM_ENGINES": "auto_inline",
        "DOCLING_SERVE_DEFAULT_VLM_PRESET": "granite_docling",
        "DOCLING_SERVE_LOAD_MODELS_AT_BOOT": "false",
        "DOCLING_SERVE_ENG_KIND": "local",
        "DOCLING_SERVE_ENG_LOC_NUM_WORKERS": "1",
        "DOCLING_SERVE_ENG_LOC_SHARE_MODELS": "true",
        "DOCLING_SERVE_OPTIONS_CACHE_SIZE": "1",
        "DOCLING_SERVE_MAX_FILE_SIZE": "104857600",
        "DOCLING_SERVE_MAX_NUM_PAGES": "1000",
        "DOCLING_SERVE_MAX_SYNC_WAIT": "86700",
        "DOCLING_SERVE_MAX_DOCUMENT_TIMEOUT": "86400",
        "DOCLING_SERVE_LOG_LEVEL": "INFO",
        "DOCLING_SERVE_DEBUG_ERROR_DETAILS": "false",
        "DOCLING_SERVE_SHOW_VERSION_INFO": "true",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
    }


def launch_agent(repo_root: Path, home: Path) -> dict[str, object]:
    project = repo_root / "services/docling-serve-mps"
    log_dir = home / "Library/Logs/chatbot-trading"
    return {
        "Label": LABEL,
        "ProgramArguments": [
            str(project / ".venv/bin/docling-serve-mps"),
            "run",
            "--repo-root",
            str(repo_root),
        ],
        "WorkingDirectory": str(project),
        "EnvironmentVariables": service_environment(repo_root, home),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
        "ProcessType": "Interactive",
        "StandardOutPath": str(log_dir / "docling-serve.out.log"),
        "StandardErrorPath": str(log_dir / "docling-serve.err.log"),
    }


def install_launch_agent(repo_root: Path, home: Path) -> Path:
    repo_root = repo_root.resolve()
    executable = repo_root / "services/docling-serve-mps/.venv/bin/docling-serve-mps"
    if not executable.is_file():
        raise RuntimeError(f"Environnement Docling absent : {executable}")

    (home / "Library/Logs/chatbot-trading").mkdir(parents=True, exist_ok=True)
    (home / "Library/Caches/chatbot-trading/docling-serve").mkdir(
        parents=True, exist_ok=True
    )
    agent_dir = home / "Library/LaunchAgents"
    agent_dir.mkdir(parents=True, exist_ok=True)
    destination = agent_dir / f"{LABEL}.plist"
    destination.write_bytes(plistlib.dumps(launch_agent(repo_root, home)))
    destination.chmod(0o600)
    return destination


def verify_model_assets(repo_root: Path) -> str:
    manifest_path = repo_root / MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["model_repository"] != MODEL_REPOSITORY:
        raise RuntimeError(
            "Le manifeste ne désigne pas l’export Granite MLX attendu"
        )

    assets_root = repo_root / "data/docling_assets"
    model_root = assets_root / MODEL_DIRECTORY
    expected = {
        Path(asset["relative_path"]): asset["sha256"]
        for asset in manifest["assets"]
    }
    actual = {
        path.relative_to(assets_root)
        for path in model_root.rglob("*")
        if path.is_file() and ".cache" not in path.relative_to(model_root).parts
    }
    if actual != set(expected):
        missing = sorted(str(path) for path in set(expected) - actual)
        added = sorted(str(path) for path in actual - set(expected))
        raise RuntimeError(
            f"Actifs Granite MLX différents : absents={missing}, ajoutés={added}"
        )

    for relative_path, expected_digest in expected.items():
        hasher = hashlib.sha256()
        with (assets_root / relative_path).open("rb") as asset:
            while chunk := asset.read(1024 * 1024):
                hasher.update(chunk)
        digest = hasher.hexdigest()
        if digest != expected_digest:
            raise RuntimeError(f"Empreinte Granite MLX invalide : {relative_path}")
    return manifest["model_revision"]


def verify_runtime(repo_root: Path) -> dict[str, str]:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise RuntimeError("Docling Serve MPS exige macOS sur Apple Silicon")
    if os.environ.get("DOCLING_DEVICE") != "mps":
        raise RuntimeError("DOCLING_DEVICE doit valoir mps")
    if os.environ.get("PYTORCH_ENABLE_MPS_FALLBACK") == "1":
        raise RuntimeError("Le fallback PyTorch MPS vers le CPU est interdit")

    import mlx.core as mx
    import torch
    from docling.datamodel.pipeline_options import VlmConvertOptions
    from docling.models.inference_engines.vlm.base import VlmEngineType

    if not torch.backends.mps.is_built() or not torch.backends.mps.is_available():
        raise RuntimeError("Le backend PyTorch MPS n’est pas disponible")
    torch_total = (torch.arange(4, device="mps") ** 2).sum().item()
    if torch_total != 14:
        raise RuntimeError("Le calcul de contrôle PyTorch MPS a échoué")

    mlx_total = mx.sum(mx.arange(4) ** 2)
    mx.eval(mlx_total)
    if mlx_total.item() != 14 or "gpu" not in str(mx.default_device()).lower():
        raise RuntimeError("Le calcul de contrôle MLX/Metal a échoué")

    options = VlmConvertOptions.from_preset("granite_docling")
    if options.engine_options.engine_type != VlmEngineType.AUTO_INLINE:
        raise RuntimeError("Le preset Granite n’utilise plus auto_inline")
    if not options.model_spec.has_explicit_engine_export(VlmEngineType.MLX):
        raise RuntimeError("Le preset Granite ne déclare plus d’export MLX")
    if options.model_spec.get_repo_id(VlmEngineType.MLX) != MODEL_REPOSITORY:
        raise RuntimeError(
            "Le preset Granite MLX ne désigne plus le modèle épinglé"
        )

    return {
        "torch": torch.__version__,
        "torch_device": "mps:0",
        "mlx_device": str(mx.default_device()),
        "vlm_engine": "mlx",
        "model_revision": verify_model_assets(repo_root),
    }


def run(repo_root: Path) -> None:
    os.environ.pop("DOCLING_SERVE_API_KEY", None)
    report = verify_runtime(repo_root.resolve())
    print(
        f"Docling Serve Metal prêt : {json.dumps(report, sort_keys=True)}",
        flush=True,
    )
    executable = Path(sys.executable).with_name("docling-serve")
    os.execv(executable, [str(executable), "run"])


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "install"):
        command = commands.add_parser(name)
        command.add_argument("--repo-root", required=True, type=Path)
    args = parser.parse_args()

    if args.command == "run":
        run(args.repo_root)
    else:
        print(install_launch_agent(args.repo_root, Path.home()))


if __name__ == "__main__":
    main()
