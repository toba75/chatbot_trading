from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
import subprocess


def _run(command: list[str]) -> str:
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Commande échouée : {command}\n{result.stdout}\n{result.stderr}"
        )
    return result.stdout.strip()


def runtime_proof(
    endpoint: str,
    compose_file: Path,
    env_file: Path,
    service: str,
    model_manifest_path: Path,
) -> dict[str, object]:
    compose = [
        "docker",
        "compose",
        "--env-file",
        str(env_file),
        "-f",
        str(compose_file),
    ]
    container_id = _run([*compose, "ps", "-q", service])
    if not container_id:
        raise RuntimeError(f"Conteneur Compose absent : {service}")

    container = json.loads(_run(["docker", "inspect", container_id]))[0]
    environment = dict(
        entry.split("=", maxsplit=1) for entry in container["Config"]["Env"]
    )
    expected_environment = {
        "DOCLING_DEVICE": "cuda:0",
        "DOCLING_SERVE_ARTIFACTS_PATH": "/models",
        "DOCLING_SERVE_DEFAULT_VLM_PRESET": "granite_docling",
        "DOCLING_SERVE_ALLOWED_VLM_PRESETS": "granite_docling",
        "DOCLING_SERVE_ALLOWED_VLM_ENGINES": "auto_inline",
        "DOCLING_SERVE_ENABLE_REMOTE_SERVICES": "false",
        "DOCLING_SERVE_ALLOW_EXTERNAL_PLUGINS": "false",
        "DOCLING_SERVE_ALLOW_CUSTOM_VLM_CONFIG": "false",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
    }
    if not expected_environment.items() <= environment.items():
        raise RuntimeError("Configuration CUDA/Granite inattendue")

    published = _run([*compose, "port", service, "5001"])
    if f"http://{published}" != endpoint.rstrip("/"):
        raise RuntimeError(f"Endpoint inattendu : {published} != {endpoint}")

    cuda_available = _run(
        [
            *compose,
            "exec",
            "-T",
            service,
            "python",
            "-c",
            "import torch; print(torch.cuda.is_available())",
        ]
    )
    if cuda_available != "True":
        raise RuntimeError(f"CUDA indisponible : {cuda_available}")

    model_manifest = json.loads(model_manifest_path.read_text(encoding="utf-8"))
    if (
        model_manifest["tool"] != "granite_docling"
        or model_manifest["model_repository"]
        != "ibm-granite/granite-docling-258M"
    ):
        raise RuntimeError("Manifeste Granite inattendu")
    device_requests = container["HostConfig"]["DeviceRequests"]
    if (
        len(device_requests) != 1
        or device_requests[0]["Driver"] != "nvidia"
        or ["gpu"] not in device_requests[0]["Capabilities"]
    ):
        raise RuntimeError("Réservation GPU Docker inattendue")
    model_mounts = [
        mount for mount in container["Mounts"] if mount["Destination"] == "/models"
    ]
    if (
        len(model_mounts) != 1
        or model_mounts[0]["Type"] != "bind"
        or model_mounts[0]["RW"] is not False
    ):
        raise RuntimeError("Montage des modèles inattendu")
    _require_model_assets(Path(model_mounts[0]["Source"]), model_manifest)

    return {
        "verified_at": datetime.now(UTC).isoformat(),
        "container_id": container_id,
        "container_started_at": container["State"]["StartedAt"],
        "image_digest": container["Image"],
        "image_reference": container["Config"]["Image"],
        "cuda_available": True,
        "device": environment["DOCLING_DEVICE"],
        "vlm_preset": environment["DOCLING_SERVE_DEFAULT_VLM_PRESET"],
        "model_repository": model_manifest["model_repository"],
        "model_revision": model_manifest["model_revision"],
        "model_assets_verified": len(model_manifest["assets"]),
        "model_manifest_sha256": hashlib.sha256(
            model_manifest_path.read_bytes()
        ).hexdigest(),
    }


def _require_model_assets(root: Path, manifest: dict[str, object]) -> None:
    assets = manifest["assets"]
    expected_paths = {Path(asset["relative_path"]) for asset in assets}
    model_root = root / "ibm-granite--granite-docling-258M"
    actual_paths = {
        path.relative_to(root)
        for path in model_root.rglob("*")
        if path.is_file() and ".cache" not in path.relative_to(model_root).parts
    }
    if actual_paths != expected_paths:
        raise RuntimeError("Contenu du montage Granite inattendu")
    for asset in assets:
        path = root / asset["relative_path"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != asset["sha256"]:
            raise RuntimeError(f"Empreinte Granite inattendue : {path}")
