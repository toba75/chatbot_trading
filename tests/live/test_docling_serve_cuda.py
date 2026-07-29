from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pytest
from docling_core.types.doc import DoclingDocument


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "compose.docling-serve.yaml"
ENV_FILE = ROOT / ".env.docling-serve"
MANIFEST = ROOT / "config" / "granite-docling-258M.manifest.json"
PDF_PATH = ROOT / "reference" / "ostrading-environment-qualification-5-pages.pdf"
PDF_SHA256 = "8b67cc7428a569f15bc256247a5b8aa04b32311e7ad05da82cf6e4c75e64cb7b"
IMAGE_DIGEST = "sha256:9a031c7d36088865a128e7c4419fee4ab03b2ac9a1e8eb207902a54fede68119"
IMAGE_REFERENCE = "quay.io/docling-project/docling-serve-cu130:v1.28.0@" + IMAGE_DIGEST
LIVE = os.environ.get("DOCLING_SERVE_LIVE") == "1"


def test_reference_pdf_is_immutable() -> None:
    assert hashlib.sha256(PDF_PATH.read_bytes()).hexdigest() == PDF_SHA256


def test_model_manifest_is_immutable_contract() -> None:
    manifest = _model_manifest()
    _assert_manifest_identity(manifest)
    assets = manifest["assets"]
    assert len(assets) == 17
    paths = [Path(asset["relative_path"]) for asset in assets]
    assert len(set(paths)) == len(paths)
    assert all(
        path.parts[0] == "ibm-granite--granite-docling-258M" and ".." not in path.parts
        for path in paths
    )
    assert all(
        len(asset["sha256"]) == 64 and set(asset["sha256"]) <= set("0123456789abcdef")
        for asset in assets
    )


@pytest.mark.live
@pytest.mark.skipif(
    not LIVE,
    reason="DOCLING_SERVE_LIVE=1 requis",
)
def test_docling_serve_converts_the_whole_pdf_with_granite() -> None:
    endpoint, assets_path = _running_service()
    pdf_content = PDF_PATH.read_bytes()
    assert hashlib.sha256(pdf_content).hexdigest() == PDF_SHA256
    _assert_model_assets(assets_path)
    _assert_cuda()

    with urlopen(f"{endpoint}/health", timeout=10) as response:
        assert json.load(response) == {"status": "ok"}

    with urlopen(f"{endpoint}/version", timeout=10) as response:
        versions = json.load(response)
    assert versions["docling-serve"] == "1.28.0"
    assert versions["docling"] == "2.115.0"
    assert versions["docling-core"] == "2.87.1"

    body = json.dumps(
        {
            "sources": [
                {
                    "kind": "file",
                    "filename": PDF_PATH.name,
                    "base64_string": base64.b64encode(pdf_content).decode("ascii"),
                }
            ],
            "options": {
                "from_formats": ["pdf"],
                "to_formats": ["json", "doctags"],
                "pipeline": "vlm",
                "vlm_pipeline_preset": "default",
                "document_timeout": 86400,
                "abort_on_error": True,
                "include_images": False,
                "include_page_images": True,
                "images_scale": 2.0,
                "image_export_mode": "placeholder",
            },
            "target": {"kind": "inbody"},
        }
    ).encode("utf-8")
    request = Request(
        f"{endpoint}/v1/convert/source",
        data=body,
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=330) as response:
            payload = json.load(response)
    except HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        pytest.fail(f"HTTP {error.code}: {error_body}\n{_server_logs()}")
    except (TimeoutError, URLError) as error:
        pytest.fail(f"Appel Docling impossible : {error}\n{_server_logs()}")

    if payload["status"] != "success" or payload["errors"]:
        pytest.fail(
            f"Conversion {payload['status']}: {payload['errors']}\n{_server_logs()}"
        )
    document_payload = payload["document"]["json_content"]
    document = DoclingDocument.model_validate(document_payload)
    assert list(document.pages) == [1, 2, 3, 4, 5]
    assert [page.page_no for page in document.pages.values()] == [1, 2, 3, 4, 5]
    assert all(page.image is not None for page in document.pages.values())
    assert document.validate_tree(document.body, raise_on_error=True)
    assert len(document.texts) == 7
    assert len(document.tables) == 1
    assert len(document.pictures) == 2
    for picture in document.pictures:
        assert picture.image is not None
        provenance = picture.prov[0]
        assert abs(picture.image.size.width - provenance.bbox.width) <= 1
        assert abs(picture.image.size.height - provenance.bbox.height) <= 1
    content_pages = {
        provenance.page_no
        for items in (document.texts, document.tables, document.pictures)
        for item in items
        for provenance in item.prov
    }
    assert content_pages == {1, 2, 3, 4}
    assert payload["document"]["doctags_content"].strip() not in (
        "",
        "<doctag>\n</doctag>",
    )

    print(
        json.dumps(
            {
                "processing_time": payload["processing_time"],
                "pages": list(document.pages),
                "texts": len(document.texts),
                "tables": len(document.tables),
                "pictures": len(document.pictures),
            }
        )
    )


def _assert_model_assets(assets_path: Path) -> None:
    manifest = _model_manifest()
    _assert_manifest_identity(manifest)
    expected_paths = {Path(asset["relative_path"]) for asset in manifest["assets"]}
    model_root = assets_path / "ibm-granite--granite-docling-258M"
    actual_paths = {
        path.relative_to(assets_path)
        for path in model_root.rglob("*")
        if path.is_file() and ".cache" not in path.relative_to(model_root).parts
    }
    assert actual_paths == expected_paths
    for asset in manifest["assets"]:
        content = (assets_path / asset["relative_path"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == asset["sha256"]


def _model_manifest() -> dict[str, object]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _assert_manifest_identity(manifest: dict[str, object]) -> None:
    assert manifest["tool"] == "granite_docling"
    assert manifest["tool_version"] == "2.115.0"
    assert manifest["model_repository"] == "ibm-granite/granite-docling-258M"
    assert manifest["model_revision"] == "982fe3b40f2fa73c365bdb1bcacf6c81b7184bfe"


def _running_service() -> tuple[str, Path]:
    container_id = _compose("ps", "-q", "docling-serve").stdout.strip()
    assert container_id != ""
    inspection = json.loads(_docker("inspect", container_id).stdout)
    assert len(inspection) == 1
    container = inspection[0]
    assert container["Image"] == IMAGE_DIGEST
    assert container["Config"]["Image"] == IMAGE_REFERENCE
    environment = dict(
        entry.split("=", maxsplit=1) for entry in container["Config"]["Env"]
    )
    assert {
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
        "UVICORN_WORKERS": "1",
        "DOCLING_SERVE_MAX_DOCUMENT_TIMEOUT": "86400",
        "DOCLING_SERVE_MAX_SYNC_WAIT": "86700",
    }.items() <= environment.items()
    device_requests = container["HostConfig"]["DeviceRequests"]
    assert len(device_requests) == 1
    assert device_requests[0]["Driver"] == "nvidia"
    assert device_requests[0]["DeviceIDs"] == [environment["NVIDIA_VISIBLE_DEVICES"]]
    assert ["gpu"] in device_requests[0]["Capabilities"]
    model_mounts = [
        mount for mount in container["Mounts"] if mount["Destination"] == "/models"
    ]
    assert len(model_mounts) == 1
    assert model_mounts[0]["Type"] == "bind"
    assert model_mounts[0]["RW"] is False

    published = _compose("port", "docling-serve", "5001").stdout.strip()
    assert "\n" not in published
    host, port = published.rsplit(":", maxsplit=1)
    assert host == "127.0.0.1" and port.isdigit()
    return f"http://{host}:{port}", Path(model_mounts[0]["Source"])


def _assert_cuda() -> None:
    result = _compose(
        "exec",
        "-T",
        "docling-serve",
        "python",
        "-c",
        "import torch; print(torch.cuda.is_available()); "
        "assert torch.cuda.is_available()",
        check=False,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    assert result.stdout.strip() == "True"


def _server_logs() -> str:
    logs = _compose("logs", "--tail", "200", "docling-serve", check=False)
    return f"{logs.stdout}\n{logs.stderr}"


def _compose(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return _run(
        [
            "docker",
            "compose",
            "--env-file",
            str(ENV_FILE),
            "-f",
            str(COMPOSE),
            *arguments,
        ],
        check=check,
    )


def _docker(*arguments: str) -> subprocess.CompletedProcess[str]:
    return _run(["docker", *arguments])


def _run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
    )
    if check and result.returncode != 0:
        pytest.fail(f"Commande échouée : {command}\n{result.stdout}\n{result.stderr}")
    return result
