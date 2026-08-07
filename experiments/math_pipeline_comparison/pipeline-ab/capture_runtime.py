from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import subprocess
import tarfile
from typing import Any


_CONTAINER = re.compile(r"^[A-Za-z0-9_.-]+$")
_FALLBACK_MAX = re.compile(
    r"(?ms)^mm_processor_kwargs:\s*\n(?:^[ \t]+.*\n)*?^[ \t]+max_soft_tokens:\s*(\d+)\s*$"
)


def _ssh(identity: Path, host: str, command: str) -> bytes:
    result = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "IdentitiesOnly=yes",
            "-i",
            str(identity),
            host,
            command,
        ],
        check=False,
        capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace"))
    return result.stdout


def _container_file(
    identity: Path, host: str, container: str, path: str, depth: int = 0
) -> bytes:
    if depth > 4:
        raise RuntimeError(f"Trop de liens Docker pour : {path}")
    archive = _ssh(identity, host, f"docker cp {container}:{path} -")
    link: str | None = None
    with tarfile.open(fileobj=BytesIO(archive), mode="r|") as stream:
        for member in stream:
            if member.isfile():
                extracted = stream.extractfile(member)
                if extracted is None:
                    raise RuntimeError(f"Fichier Docker illisible : {path}")
                return extracted.read()
            if member.issym() or member.islnk():
                link = member.linkname
    if link:
        return _container_file(identity, host, container, link, depth + 1)
    raise RuntimeError(f"Fichier Docker absent : {path}")


def _max_soft_tokens(value: Any, path: str = "$") -> dict[str, int]:
    matches: dict[str, int] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key == "max_soft_tokens" and isinstance(child, int):
                matches[child_path] = child
            matches.update(_max_soft_tokens(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            matches.update(_max_soft_tokens(child, f"{path}[{index}]"))
    return matches


def capture(args: argparse.Namespace) -> dict[str, object]:
    if not _CONTAINER.fullmatch(args.container):
        raise ValueError("Nom de conteneur invalide")
    inspected = json.loads(
        _ssh(args.identity, args.host, f"docker inspect {args.container}")
    )[0]
    fallback = _container_file(
        args.identity, args.host, args.container, "/opt/nim/fallback.yaml"
    )
    processor = _container_file(
        args.identity,
        args.host,
        args.container,
        "/opt/nim/workspace/processor_config.json",
    )
    model_config = _container_file(
        args.identity, args.host, args.container, "/opt/nim/workspace/config.json"
    )
    fallback_text = fallback.decode("utf-8")
    fallback_match = _FALLBACK_MAX.search(fallback_text)
    config = json.loads(model_config)
    effective = (
        int(fallback_match.group(1))
        if fallback_match
        else int(config["vision_soft_tokens_per_image"])
    )
    if effective != args.expected_max_soft_tokens:
        raise RuntimeError(
            f"max_soft_tokens inattendu : {effective} != {args.expected_max_soft_tokens}"
        )
    state = inspected["State"]
    proof = {
        "schema_version": 1,
        "captured_at": datetime.now(UTC).isoformat(),
        "host": args.host,
        "container": inspected["Name"].lstrip("/"),
        "image_reference": inspected["Config"]["Image"],
        "image_id": inspected["Image"],
        "network_mode": inspected["HostConfig"]["NetworkMode"],
        "restart_policy": inspected["HostConfig"]["RestartPolicy"]["Name"],
        "state": {
            "status": state["Status"],
            "started_at": state["StartedAt"],
            "finished_at": state["FinishedAt"],
        },
        "effective_max_soft_tokens": effective,
        "configuration": {
            "fallback": {
                "path": "/opt/nim/fallback.yaml",
                "sha256": hashlib.sha256(fallback).hexdigest(),
                "override": int(fallback_match.group(1)) if fallback_match else None,
            },
            "processor": {
                "path": "/opt/nim/workspace/processor_config.json",
                "sha256": hashlib.sha256(processor).hexdigest(),
                "max_soft_tokens": _max_soft_tokens(json.loads(processor)),
            },
            "model": {
                "path": "/opt/nim/workspace/config.json",
                "sha256": hashlib.sha256(model_config).hexdigest(),
                "vision_soft_tokens_per_image": config[
                    "vision_soft_tokens_per_image"
                ],
            },
        },
    }
    args.output.write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return proof


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--container", required=True)
    parser.add_argument("--expected-max-soft-tokens", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Preuve déjà présente : {args.output}")
    print(json.dumps(capture(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
