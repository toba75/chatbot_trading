from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import tempfile
import threading
import zipfile
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

from pdf_math_audit.contract import CAPABILITY_PROFILE, CONTRACT_VERSION
from pdf_math_audit.service_config import ServiceConfig
from pdf_math_audit.service_protocol import (
    artifact_events,
    artifact_metadata,
    ndjson_line,
)


ProcessFactory = Callable[..., Any]


class AnalysisSession:
    def __init__(
        self,
        *,
        directory: tempfile.TemporaryDirectory[str],
        semaphore: threading.BoundedSemaphore,
        process: Any,
        shutdown_seconds: int,
    ) -> None:
        self.directory = directory
        self.semaphore = semaphore
        self.process = process
        self.shutdown_seconds = shutdown_seconds
        self.closed = False

    async def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            if self.process.poll() is None:
                self.process.kill()
                await asyncio.to_thread(
                    self.process.wait, timeout=self.shutdown_seconds
                )
        finally:
            self.directory.cleanup()
            self.semaphore.release()


def _command(
    source: Path,
    document: Path,
    report: Path,
    evidence: Path,
    source_sha256: str,
    document_sha256: str,
    config: ServiceConfig,
) -> list[str]:
    return [
        sys.executable,
        "-m",
        "pdf_math_audit.cli",
        str(source),
        "--docling-document",
        str(document),
        "--source-sha256",
        source_sha256,
        "--docling-document-sha256",
        document_sha256,
        "--contract-version",
        CONTRACT_VERSION,
        "--capability-profile",
        CAPABILITY_PROFILE,
        "--report",
        str(report),
        "--evidence",
        str(evidence),
        "--correction-endpoint",
        config.correction_endpoint,
        "--correction-model",
        config.correction_model,
        "--correction-dpi",
        str(config.correction_dpi),
        "--correction-padding-points",
        str(config.correction_padding_points),
        "--correction-timeout-seconds",
        str(config.correction_timeout_seconds),
        "--correction-max-response-bytes",
        str(config.correction_max_response_bytes),
        "--correction-records",
        str(report.parent / "corrections.json"),
        "--correction-evidence",
        str(report.parent / "correction-evidence.zip"),
        "--derived-docling-document",
        str(report.parent / "derived-document.json"),
        "--derived-html",
        str(report.parent / "derived.html"),
        "--derived-markdown",
        str(report.parent / "derived.md"),
        "--native-page-html",
        str(report.parent / "native-page.html"),
        "--correction-checkpoint-records",
        str(report.parent / "corrections.partial.ndjson"),
        "--correction-checkpoint-evidence",
        str(report.parent / "correction-checkpoints"),
    ]


def _partial_artifacts(root: Path) -> tuple[tuple[str, Path], ...]:
    available: list[tuple[str, Path]] = []
    evidence = root / "evidence.ndjson.gz"
    if evidence.exists():
        available.append(("evidence", evidence))

    records_path = root / "corrections.partial.ndjson"
    if records_path.exists():
        records = []
        for line in records_path.read_bytes().splitlines():
            try:
                records.append(json.loads(line))
            except (UnicodeDecodeError, json.JSONDecodeError):
                records.append(
                    {"status": "checkpoint_unreadable", "raw_hex": line.hex()}
                )
        correction_path = root / "corrections.partial.json"
        correction_path.write_text(
            json.dumps(
                {"status": "interrupted", "records": records},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        available.append(("corrections", correction_path))

    checkpoint_root = root / "correction-checkpoints"
    if checkpoint_root.exists():
        archive_path = root / "correction-evidence.partial.zip"
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in checkpoint_root.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(checkpoint_root))
        available.append(("correction_evidence", archive_path))
    return tuple(available)


async def _stream_partial(root: Path, chunk_bytes: int) -> AsyncIterator[bytes]:
    for name, path in _partial_artifacts(root):
        for event in artifact_events(name, path, chunk_bytes):
            yield ndjson_line(event)


def start_analysis(
    *,
    directory: tempfile.TemporaryDirectory[str],
    process_factory: ProcessFactory,
    source_sha256: str,
    document_sha256: str,
    config: ServiceConfig,
) -> Any:
    root = Path(directory.name)
    return process_factory(
        _command(
            root / "source.pdf",
            root / "document.json",
            root / "report.json",
            root / "evidence.ndjson.gz",
            source_sha256,
            document_sha256,
            config,
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
    )


async def stream_analysis(
    session: AnalysisSession,
    *,
    config: ServiceConfig,
) -> AsyncIterator[bytes]:
    root = Path(session.directory.name)
    report = root / "report.json"
    evidence = root / "evidence.ndjson.gz"
    process = session.process
    terminal_seen = False
    diagnostics: list[str] = []
    return_code: int | None = None
    timed_out = False
    try:
        try:
            async with asyncio.timeout(config.timeout_seconds):
                while raw_line := await asyncio.to_thread(process.stdout.readline):
                    try:
                        event = json.loads(raw_line)
                    except json.JSONDecodeError:
                        diagnostics.append(raw_line)
                        continue
                    if event.get("type") == "progress":
                        yield ndjson_line(event)
                    elif event.get("type") == "result":
                        terminal_seen = True
                    else:
                        raise ValueError("Événement CLI inattendu")
                return_code = await asyncio.to_thread(
                    process.wait, timeout=config.process_shutdown_seconds
                )
        except TimeoutError:
            if process.poll() is None:
                timed_out = True
                process.kill()
                await asyncio.to_thread(
                    process.wait, timeout=config.process_shutdown_seconds
                )
            else:
                return_code = process.poll()

        if timed_out:
            async for event in _stream_partial(root, config.artifact_chunk_bytes):
                yield event
            yield ndjson_line(
                {
                    "type": "error",
                    "code": "analysis_timeout",
                    "message": "La durée maximale de l’analyse est dépassée.",
                }
            )
            return
        if return_code != 0 or not terminal_seen:
            async for event in _stream_partial(root, config.artifact_chunk_bytes):
                yield event
            message = "".join(diagnostics).strip() or "L’analyse a échoué."
            yield ndjson_line(
                {"type": "error", "code": "analysis_failed", "message": message}
            )
            return

        available = (
            ("evidence", evidence),
            ("corrections", root / "corrections.json"),
            ("correction_evidence", root / "correction-evidence.zip"),
            ("derived_docling_document", root / "derived-document.json"),
            ("derived_html", root / "derived.html"),
            ("derived_markdown", root / "derived.md"),
            ("native_page_html", root / "native-page.html"),
            ("report", report),
        )
        artifacts = {}
        for name, path in available:
            if not path.exists():
                continue
            chunks = 0
            for event in artifact_events(name, path, config.artifact_chunk_bytes):
                chunks += 1
                yield ndjson_line(event)
            artifacts[name] = artifact_metadata(path, chunks)
        yield ndjson_line({"type": "result", "artifacts": artifacts})
    finally:
        await session.close()
