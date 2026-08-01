from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import tempfile
import threading
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
    ]


def start_analysis(
    *,
    directory: tempfile.TemporaryDirectory[str],
    process_factory: ProcessFactory,
    source_sha256: str,
    document_sha256: str,
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
            yield ndjson_line(
                {
                    "type": "error",
                    "code": "analysis_timeout",
                    "message": "La durée maximale de l’analyse est dépassée.",
                }
            )
            return
        if return_code != 0 or not terminal_seen:
            message = "".join(diagnostics).strip() or "L’analyse a échoué."
            yield ndjson_line(
                {"type": "error", "code": "analysis_failed", "message": message}
            )
            return

        artifacts = {}
        for name, path in (("evidence", evidence), ("report", report)):
            chunks = 0
            for event in artifact_events(name, path, config.artifact_chunk_bytes):
                chunks += 1
                yield ndjson_line(event)
            artifacts[name] = artifact_metadata(path, chunks)
        yield ndjson_line({"type": "result", "artifacts": artifacts})
    finally:
        await session.close()
