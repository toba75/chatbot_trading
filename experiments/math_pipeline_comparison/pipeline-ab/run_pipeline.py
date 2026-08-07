from __future__ import annotations

import argparse
import base64
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen
import uuid
import zipfile

from pdf_math_audit.contract import CAPABILITY_PROFILE, CONTRACT_VERSION


ARTIFACT_FILES = {
    "evidence": "evidence.ndjson.gz",
    "corrections": "corrections.json",
    "correction_evidence": "correction-evidence.zip",
    "derived_docling_document": "derived-document.json",
    "derived_html": "derived.html",
    "derived_markdown": "derived.md",
    "native_page_html": "native-page.html",
    "report": "report.json",
}


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _load_runtime_proof(
    path: Path, expected_max_soft_tokens: int
) -> tuple[bytes, dict[str, object]]:
    content = path.read_bytes()
    proof = json.loads(content)
    if proof.get("schema_version") != 1:
        raise ValueError("Version de preuve runtime invalide")
    if proof.get("effective_max_soft_tokens") != expected_max_soft_tokens:
        raise ValueError("La preuve runtime ne correspond pas au bras demandé")
    return content, proof


def _multipart(pdf: bytes, document: bytes) -> tuple[bytes, str]:
    boundary = f"pipeline-ab-{uuid.uuid4().hex}"
    parts: list[bytes] = []

    def field(
        name: str,
        value: bytes,
        *,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> None:
        disposition = f'form-data; name="{name}"'
        if filename:
            disposition += f'; filename="{filename}"'
        headers = [f"Content-Disposition: {disposition}"]
        if content_type:
            headers.append(f"Content-Type: {content_type}")
        parts.append(
            f"--{boundary}\r\n".encode()
            + "\r\n".join(headers).encode()
            + b"\r\n\r\n"
            + value
            + b"\r\n"
        )

    field("source_pdf", pdf, filename="source.pdf", content_type="application/pdf")
    field(
        "docling_document",
        document,
        filename="document.json",
        content_type="application/json",
    )
    field("source_sha256", _sha256(pdf).encode())
    field("docling_document_sha256", _sha256(document).encode())
    field("contract_version", CONTRACT_VERSION.encode())
    field("capability_profile", CAPABILITY_PROFILE.encode())
    return b"".join(parts) + f"--{boundary}--\r\n".encode(), boundary


def _usage(evidence_path: Path) -> dict[str, object]:
    calls = []
    with zipfile.ZipFile(evidence_path) as archive:
        for name in sorted(archive.namelist()):
            if not name.endswith("/response.json"):
                continue
            response = json.loads(archive.read(name))
            usage = response.get("usage", {})
            calls.append(
                {
                    "target": name.removesuffix("/response.json"),
                    "response_id": response.get("id"),
                    "model": response.get("model"),
                    "finish_reason": response["choices"][0].get("finish_reason"),
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                }
            )
    return {
        "calls": calls,
        "prompt_tokens": sum(call["prompt_tokens"] or 0 for call in calls),
        "completion_tokens": sum(call["completion_tokens"] or 0 for call in calls),
        "total_tokens": sum(call["total_tokens"] or 0 for call in calls),
    }


def run(args: argparse.Namespace) -> dict[str, object]:
    runtime_proof_bytes, runtime_proof = _load_runtime_proof(
        args.runtime_proof, args.max_soft_tokens
    )
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"Répertoire de sortie déjà présent : {output}")
    output.mkdir(parents=True)
    artifacts = output / "artifacts"
    artifacts.mkdir()

    pdf = args.pdf.read_bytes()
    document = args.docling_document.read_bytes()
    body, boundary = _multipart(pdf, document)
    request = Request(
        f"{args.endpoint.rstrip('/')}/v1/qualifications",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    started_at = datetime.now(UTC).isoformat()
    started = time.perf_counter()
    sequences: dict[str, int] = {}
    terminal: dict[str, object] | None = None
    events_path = output / "events-metadata.ndjson"
    with urlopen(request, timeout=args.timeout_seconds) as response, events_path.open(
        "w", encoding="utf-8", newline="\n"
    ) as event_log:
        for raw_line in response:
            event = json.loads(raw_line)
            if event["type"] == "artifact":
                name = event["name"]
                if name not in ARTIFACT_FILES:
                    raise ValueError(f"Artefact inattendu : {name}")
                expected = sequences.get(name, 0)
                if event["sequence"] != expected:
                    raise ValueError(f"Séquence invalide pour {name}")
                sequences[name] = expected + 1
                content = base64.b64decode(event["content_base64"])
                with (artifacts / ARTIFACT_FILES[name]).open("ab") as stream:
                    stream.write(content)
                event = {
                    "type": "artifact",
                    "name": name,
                    "sequence": expected,
                    "decoded_bytes": len(content),
                }
            elif event["type"] in {"result", "error"}:
                terminal = event
            event_log.write(json.dumps(event, ensure_ascii=False) + "\n")
    elapsed = time.perf_counter() - started

    if terminal is None or terminal["type"] != "result":
        raise RuntimeError(f"Résultat terminal invalide : {terminal}")
    metadata = terminal["artifacts"]
    for name, details in metadata.items():
        path = artifacts / ARTIFACT_FILES[name]
        content = path.read_bytes()
        if len(content) != details["bytes"] or _sha256(content) != details["sha256"]:
            raise RuntimeError(f"Intégrité invalide pour {name}")

    report = json.loads((artifacts / "report.json").read_text(encoding="utf-8"))
    corrections = json.loads(
        (artifacts / "corrections.json").read_text(encoding="utf-8")
    )
    usage = _usage(artifacts / "correction-evidence.zip")
    summary = {
        "schema_version": 1,
        "arm": args.arm,
        "repeat": args.repeat,
        "max_soft_tokens": args.max_soft_tokens,
        "started_at": started_at,
        "elapsed_seconds": round(elapsed, 3),
        "endpoint": args.endpoint,
        "inputs": {
            "pdf": str(args.pdf.resolve()),
            "pdf_sha256": _sha256(pdf),
            "docling_document": str(args.docling_document.resolve()),
            "docling_document_sha256": _sha256(document),
        },
        "gemma_runtime": {
            "proof": str(args.runtime_proof.resolve()),
            "proof_sha256": _sha256(runtime_proof_bytes),
            "image_reference": runtime_proof["image_reference"],
            "image_id": runtime_proof["image_id"],
            "effective_max_soft_tokens": runtime_proof[
                "effective_max_soft_tokens"
            ],
        },
        "correction": report["correction"],
        "record_statuses": {
            status: sum(record["status"] == status for record in corrections["records"])
            for status in ("accepted", "rejected", "failed")
        },
        "usage": usage,
        "artifacts": metadata,
    }
    (output / "run.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--docling-document", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--repeat", type=int, required=True)
    parser.add_argument("--max-soft-tokens", type=int, required=True)
    parser.add_argument("--runtime-proof", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    args = parser.parse_args()
    print(json.dumps(run(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
