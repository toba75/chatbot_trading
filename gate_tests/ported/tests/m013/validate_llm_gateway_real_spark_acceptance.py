from __future__ import annotations

from pathlib import Path
from subprocess import DEVNULL, Popen, TimeoutExpired
import sys


def test_validate_llm_gateway_real_spark_acceptance() -> None:
    original_argv = sys.argv[:]
    repository_root = next(parent for parent in Path(__file__).resolve().parents if (parent / 'pyproject.toml').is_file())
    gateway_process = Popen(
        [
            sys.executable,
            "-m",
            "app.platform.local_runtime",
            "serve-http",
            "llm-gateway",
            "8090",
            "--config",
            str(repository_root / "config" / "application.yaml"),
        ],
        cwd=repository_root,
        stdout=DEVNULL,
        stderr=DEVNULL,
    )
    try:
        sys.argv = [str(Path(__file__)), str(repository_root), str(repository_root / 'config' / 'application.yaml')]
        source = '\nimport json\nimport sys\nimport time\nimport urllib.error\nimport urllib.request\n\n\nrepo_root = sys.argv[1]\nconfig_path = sys.argv[2]\nif repo_root not in sys.path:\n    sys.path.insert(0, repo_root)\n\nfrom app.platform.configuration import load_application_configuration  # noqa: E402\n\n\nconfiguration = load_application_configuration(config_path=config_path, environment_snapshot={})\nbase_url = configuration.services.llm_gateway.spark_endpoint_url.rstrip("/")\nserved_model = configuration.models.llm.served_model_name\nmodel_revision = configuration.models.llm.model_revision\nruntime_version = configuration.models.llm.runtime_version\nif configuration.services.llm_gateway.auth_mode != "none":\n    raise AssertionError("auth_mode doit valoir none pour le conteneur Spark actuel.")\nif configuration.services.llm_gateway.tls_mode != "disabled":\n    raise AssertionError("tls_mode doit valoir disabled pour le conteneur Spark actuel.")\ngateway_url = "http://127.0.0.1:8090"\n\n\ndef get_json(path: str) -> dict:\n    with urllib.request.urlopen(f"{base_url}{path}", timeout=30) as response:\n        payload = json.loads(response.read().decode("utf-8"))\n    if not isinstance(payload, dict):\n        raise AssertionError(f"Payload Spark non objet pour {path}: {payload!r}")\n    return payload\n\n\ndef wait_for_gateway() -> None:\n    deadline = time.monotonic() + 20\n    last_error: Exception | None = None\n    while time.monotonic() < deadline:\n        try:\n            with urllib.request.urlopen(f"{gateway_url}/health", timeout=2) as response:\n                if response.status == 200:\n                    return\n        except Exception as exc:  # noqa: BLE001 - le message final conserve l\'erreur exacte.\n            last_error = exc\n        time.sleep(0.5)\n    raise AssertionError(f"Service llm-gateway local indisponible: {last_error!r}")\n\n\nmodels_payload = get_json("/models")\nmodel_items = models_payload.get("data")\nif not isinstance(model_items, list):\n    raise AssertionError(f"Catalogue modèles Spark invalide: {models_payload!r}")\nserved_model_ids = tuple(\n    item["id"]\n    for item in model_items\n    if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip() == item["id"]\n)\nif served_model not in served_model_ids:\n    raise AssertionError(\n        f"Modèle GEMMA_MODEL absent du Spark réel: {served_model!r}; modèles exposés: {served_model_ids!r}"\n    )\n\nmetadata_payload = get_json("/metadata")\nselected_profile_id = metadata_payload.get("selectedModelProfileId")\nif not isinstance(selected_profile_id, str) or selected_profile_id.strip() == "":\n    raise AssertionError(f"Profil modèle Spark absent de /metadata: {metadata_payload!r}")\nexpected_model_revision = f"{served_model}@{selected_profile_id}"\nif model_revision != expected_model_revision:\n    raise AssertionError(\n        f"GEMMA_MODEL_REVISION incohérent: attendu {expected_model_revision!r}, obtenu {model_revision!r}"\n    )\n\nversion_payload = get_json("/version")\nrelease = version_payload.get("release")\napi_version = version_payload.get("api")\nif not isinstance(release, str) or not isinstance(api_version, str):\n    raise AssertionError(f"Version runtime Spark invalide: {version_payload!r}")\nexpected_runtime_version = f"nim-{release}-api-{api_version}"\nif runtime_version != expected_runtime_version:\n    raise AssertionError(\n        f"GEMMA_RUNTIME_VERSION incohérent: attendu {expected_runtime_version!r}, obtenu {runtime_version!r}"\n    )\n\nrequest_body = {\n    "messages": [\n        {\n            "role": "user",\n            "content": \'Réponds uniquement avec ce JSON: {"answer":"OK"}.\',\n        }\n    ],\n    "output_schema": {\n        "type": "object",\n        "properties": {"answer": {"type": "string"}},\n        "required": ["answer"],\n        "additionalProperties": False,\n    },\n    "schema_name": "m13_reality_gateway_smoke",\n    "schema_version": "1.0",\n    "trace_id": "TRACE-M013-REALITY-GATEWAY-0001",\n    "request_id": "REQ-M013-REALITY-GATEWAY-0001",\n    "idempotency_key": "IDEMP-M013-REALITY-GATEWAY-0001",\n    "prompt_id": "PROMPT-M013-REALITY-GATEWAY-SMOKE",\n    "prompt_version": "1.0",\n    "sampling_parameters": {"max_tokens": 64, "temperature": 0},\n}\n\nwait_for_gateway()\nrequest = urllib.request.Request(\n    f"{gateway_url}/v1/infer",\n    data=json.dumps(request_body).encode("utf-8"),\n    headers={"Content-Type": "application/json; charset=utf-8"},\n    method="POST",\n)\ntry:\n    with urllib.request.urlopen(request, timeout=180) as response:\n        status_code = response.status\n        response_body = json.loads(response.read().decode("utf-8"))\nexcept urllib.error.HTTPError as exc:\n    error_body = exc.read().decode("utf-8", errors="replace")\n    raise AssertionError(f"Réponse llm-gateway réelle inattendue: {exc.code}, {error_body}") from exc\n\nif status_code != 200 or not isinstance(response_body, dict):\n    raise AssertionError(f"Réponse llm-gateway réelle inattendue: {status_code}, {response_body!r}")\n\nif response_body.get("structured_output") != {"answer": "OK"}:\n    raise AssertionError(f"Sortie structurée réelle inattendue: {response_body!r}")\n\nprovenance = response_body.get("provenance")\nif not isinstance(provenance, dict):\n    raise AssertionError(f"Provenance gateway absente: {response_body!r}")\nif provenance.get("model_id") != served_model:\n    raise AssertionError(f"Modèle servi absent de la provenance: {provenance!r}")\nif provenance.get("model_revision") != model_revision:\n    raise AssertionError(f"Révision modèle déclarée absente: {provenance!r}")\nif provenance.get("runtime_version") != runtime_version:\n    raise AssertionError(f"Runtime déclaré absent: {provenance!r}")\nif provenance.get("prompt_id") != "PROMPT-M013-REALITY-GATEWAY-SMOKE":\n    raise AssertionError(f"Prompt id absent de la provenance: {provenance!r}")\nif not isinstance(response_body.get("raw_response_id"), str) or response_body["raw_response_id"].strip() == "":\n    raise AssertionError(f"Identifiant brut Spark absent: {response_body!r}")\n\nprint("Test d\'acceptation M13-reality gateway LLM réel: OK")'
        namespace = {'__name__': __name__, '__file__': str(Path(__file__))}
        exec(compile(source, str(Path(__file__)), 'exec'), namespace)
    finally:
        sys.argv = original_argv
        gateway_process.terminate()
        try:
            gateway_process.wait(timeout=10)
        except TimeoutExpired:
            gateway_process.kill()
            gateway_process.wait(timeout=10)
