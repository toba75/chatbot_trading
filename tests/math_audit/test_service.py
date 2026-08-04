from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from pdf_math_audit.service import ServiceConfig, create_app


PDF = b"%PDF-test"
DOCUMENT = b'{"schema_name":"DoclingDocument"}'


class CompletedProcess:
    def __init__(self, command: list[str], **_options: Any) -> None:
        report_path = Path(command[command.index("--report") + 1])
        evidence_path = Path(command[command.index("--evidence") + 1])
        corrections_path = Path(command[command.index("--correction-records") + 1])
        correction_evidence_path = Path(
            command[command.index("--correction-evidence") + 1]
        )
        native_page_html_path = Path(command[command.index("--native-page-html") + 1])
        report_path.write_bytes(b'{"status":"completed"}\n')
        evidence_path.write_bytes(b"proof")
        corrections_path.write_bytes(b'{"records":[]}\n')
        correction_evidence_path.write_bytes(b"PK")
        native_page_html_path.write_bytes(b"<div id='page-1'></div>")
        self.stdout = io.StringIO(
            "".join(
                [
                '{"type":"progress","phase":"source_analysis",'
                '"completed_units":1,"total_units":1}\n',
                '{"type":"result","report_path":"ignored",'
                '"report_sha256":"ignored"}\n',
                ]
            )
        )
        self.returncode = 0

    def wait(self, timeout: float) -> int:
        assert timeout == 5
        return self.returncode

    def poll(self) -> int:
        return self.returncode

    def kill(self) -> None:
        raise AssertionError("Le processus terminé ne doit pas être tué")


class FailedProcess:
    def __init__(self, _command: list[str], **_options: Any) -> None:
        self.stdout = io.StringIO("contrat invalide\n")
        self.returncode = 2

    def wait(self, timeout: float) -> int:
        return self.returncode

    def poll(self) -> int:
        return self.returncode

    def kill(self) -> None:
        raise AssertionError("Le processus terminé ne doit pas être tué")


class FailedProcessWithCheckpoints(FailedProcess):
    def __init__(self, command: list[str], **_options: Any) -> None:
        root = Path(command[command.index("--report") + 1]).parent
        (root / "evidence.ndjson.gz").write_bytes(b"source-proof")
        records = Path(command[command.index("--correction-checkpoint-records") + 1])
        records.write_text(
            '{"region_id":"r1","status":"accepted"}\n', encoding="utf-8"
        )
        evidence = Path(command[command.index("--correction-checkpoint-evidence") + 1])
        (evidence / "r1").mkdir(parents=True)
        (evidence / "r1" / "response.json").write_text("{}", encoding="utf-8")
        super().__init__(command)


class StartFailureThenSuccess:
    calls = 0

    def __new__(cls, command: list[str], **options: Any) -> Any:
        cls.calls += 1
        if cls.calls == 1:
            raise OSError("processus indisponible")
        return CompletedProcess(command, **options)


def _config(*, max_pdf_bytes: int = 100) -> ServiceConfig:
    return ServiceConfig(
        max_pdf_bytes=max_pdf_bytes,
        max_docling_bytes=100,
        timeout_seconds=30,
        upload_timeout_seconds=30,
        process_shutdown_seconds=5,
        concurrency=1,
        upload_chunk_bytes=8,
        artifact_chunk_bytes=4,
        max_form_field_bytes=128,
        multipart_spool_bytes=16,
        correction_endpoint="http://gemma/v1",
        correction_model="gemma",
        correction_dpi=600,
        correction_padding_points=4.0,
        correction_timeout_seconds=30,
        correction_max_response_bytes=10_000,
    )


def _request(client: TestClient) -> Any:
    return client.post(
        "/v1/qualifications",
        files={
            "source_pdf": ("source.pdf", PDF, "application/pdf"),
            "docling_document": (
                "document.json",
                DOCUMENT,
                "application/json",
            ),
        },
        data={
            "source_sha256": hashlib.sha256(PDF).hexdigest(),
            "docling_document_sha256": hashlib.sha256(DOCUMENT).hexdigest(),
            "contract_version": "2.0",
            "capability_profile": "pdf-docling-semantic-correction-v2",
        },
    )


def _events(response: Any) -> list[dict[str, Any]]:
    return [json.loads(line) for line in response.text.splitlines()]


def test_diffuse_progression_artefacts_et_resultat_terminal() -> None:
    client = TestClient(create_app(_config(), process_factory=CompletedProcess))

    response = _request(client)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    events = _events(response)
    assert events[0] == {
        "type": "progress",
        "phase": "source_analysis",
        "completed_units": 1,
        "total_units": 1,
    }
    chunks = [event for event in events if event["type"] == "artifact"]
    assert b"".join(
        base64.b64decode(event["content_base64"])
        for event in chunks
        if event["name"] == "evidence"
    ) == b"proof"
    assert b"".join(
        base64.b64decode(event["content_base64"])
        for event in chunks
        if event["name"] == "report"
    ) == b'{"status":"completed"}\n'
    assert events[-1]["type"] == "result"
    assert set(events[-1]["artifacts"]) == {
        "evidence",
        "corrections",
        "correction_evidence",
        "native_page_html",
        "report",
    }


def test_refuse_un_pdf_trop_volumineux_avant_de_lancer_l_analyse() -> None:
    client = TestClient(
        create_app(_config(max_pdf_bytes=4), process_factory=CompletedProcess)
    )

    response = _request(client)

    assert response.status_code == 413
    assert response.json()["detail"] == "Le PDF source dépasse la taille autorisée."


def test_une_erreur_cli_devient_un_evenement_terminal_sans_artefact() -> None:
    client = TestClient(create_app(_config(), process_factory=FailedProcess))

    response = _request(client)

    events = _events(response)
    assert events == [
        {
            "type": "error",
            "code": "analysis_failed",
            "message": "contrat invalide",
        }
    ]


def test_diffuse_les_preuves_deja_produites_avant_une_erreur_cli() -> None:
    client = TestClient(
        create_app(_config(), process_factory=FailedProcessWithCheckpoints)
    )

    events = _events(_request(client))

    artifacts = [event for event in events if event["type"] == "artifact"]
    contents = {
        name: b"".join(
            base64.b64decode(event["content_base64"])
            for event in artifacts
            if event["name"] == name
        )
        for name in {event["name"] for event in artifacts}
    }
    assert contents["evidence"] == b"source-proof"
    assert json.loads(contents["corrections"])["records"] == [
        {"region_id": "r1", "status": "accepted"}
    ]
    assert contents["correction_evidence"].startswith(b"PK")
    assert events[-1]["type"] == "error"


def test_valide_strictement_les_parametres_de_configuration() -> None:
    invalid = _config()
    object.__setattr__(invalid, "concurrency", 0)

    try:
        create_app(invalid, process_factory=subprocess.Popen)
    except ValueError as error:
        assert str(error) == "concurrency doit être strictement positif"
    else:
        raise AssertionError("Une concurrence nulle a été acceptée")


def test_expose_un_endpoint_de_sante_sans_lancer_d_analyse() -> None:
    client = TestClient(create_app(_config(), process_factory=FailedProcess))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_libere_la_capacite_si_le_processus_ne_demarre_pas() -> None:
    StartFailureThenSuccess.calls = 0
    client = TestClient(
        create_app(_config(), process_factory=StartFailureThenSuccess),
        raise_server_exceptions=False,
    )

    first = _request(client)
    second = _request(client)

    assert _events(first) == [
        {
            "type": "error",
            "code": "analysis_start_failed",
            "message": "Le processus d’analyse n’a pas pu démarrer.",
        }
    ]
    assert second.status_code == 200
    assert _events(second)[-1]["type"] == "result"


def test_libere_la_capacite_si_l_upload_est_annule(monkeypatch: Any) -> None:
    import tempfile

    from pdf_math_audit.bounded_multipart import BoundedMultiPartParser

    original = BoundedMultiPartParser.parse
    calls = 0
    opened_files = []

    async def cancelled_once(parser: BoundedMultiPartParser) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            temporary = tempfile.SpooledTemporaryFile()
            parser._files_to_close_on_error.append(temporary)
            opened_files.append(temporary)
            raise asyncio.CancelledError
        return await original(parser)

    monkeypatch.setattr(BoundedMultiPartParser, "parse", cancelled_once)
    client = TestClient(create_app(_config(), process_factory=CompletedProcess))

    try:
        _request(client)
    except BaseException:
        pass
    else:
        raise AssertionError("L’annulation attendue n’a pas été propagée")

    assert opened_files[0].closed
    assert _request(client).status_code == 200


def test_borne_independamment_la_reception_multipart(monkeypatch: Any) -> None:
    from pdf_math_audit.bounded_multipart import BoundedMultiPartParser

    async def too_slow(_parser: BoundedMultiPartParser) -> Any:
        await asyncio.sleep(0.05)

    monkeypatch.setattr(BoundedMultiPartParser, "parse_exact", too_slow)
    config = _config()
    object.__setattr__(config, "upload_timeout_seconds", 0.01)
    client = TestClient(create_app(config, process_factory=CompletedProcess))

    response = _request(client)

    assert response.status_code == 408
    assert response.json()["detail"] == "La durée maximale de réception est dépassée."


class BlockingProcess:
    instances: list["BlockingProcess"] = []

    def __init__(self, _command: list[str], **_options: Any) -> None:
        self.released = threading.Event()
        self.killed = False
        self.returncode = None
        self.stdout = self
        self.__class__.instances.append(self)

    def readline(self) -> str:
        self.released.wait()
        return ""

    def wait(self, timeout: float) -> int:
        self.released.wait(timeout)
        if not self.released.is_set():
            raise subprocess.TimeoutExpired("fake", timeout)
        return self.returncode or -9

    def poll(self) -> int | None:
        return self.returncode

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9
        self.released.set()


def test_annulation_du_flux_tue_immediatement_le_processus_et_libere_la_capacite() -> None:
    BlockingProcess.instances.clear()

    async def scenario() -> None:
        import tempfile

        from pdf_math_audit.service_process import AnalysisSession, stream_analysis

        semaphore = threading.BoundedSemaphore(1)
        assert semaphore.acquire(blocking=False)
        directory = tempfile.TemporaryDirectory()
        process = BlockingProcess([])
        session = AnalysisSession(
            directory=directory,
            semaphore=semaphore,
            process=process,
            shutdown_seconds=5,
        )
        stream = stream_analysis(session, config=_config())
        task = asyncio.create_task(anext(stream))
        await asyncio.sleep(0.01)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert process.killed
        assert semaphore.acquire(blocking=False)

    asyncio.run(scenario())


def _request_arguments() -> dict[str, Any]:
    return {
        "files": {
            "source_pdf": ("source.pdf", PDF, "application/pdf"),
            "docling_document": ("document.json", DOCUMENT, "application/json"),
        },
        "data": {
            "source_sha256": hashlib.sha256(PDF).hexdigest(),
            "docling_document_sha256": hashlib.sha256(DOCUMENT).hexdigest(),
            "contract_version": "2.0",
            "capability_profile": "pdf-docling-semantic-correction-v2",
        },
    }


class TimeoutRaceProcess(CompletedProcess):
    def wait(self, timeout: float) -> int:
        self.returncode = 0
        time.sleep(0.2)
        return 0


def test_ne_declasse_pas_en_timeout_un_process_deja_termine() -> None:
    config = _config()
    object.__setattr__(config, "timeout_seconds", 0.1)
    client = TestClient(create_app(config, process_factory=TimeoutRaceProcess))

    events = _events(_request(client))

    assert events[-1]["type"] == "result"
    assert all(event.get("code") != "analysis_timeout" for event in events)
