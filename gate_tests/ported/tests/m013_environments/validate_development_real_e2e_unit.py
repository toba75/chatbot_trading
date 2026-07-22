"""Décisions unitaires découvertes pendant la preuve development réelle."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import signal
import subprocess
from types import SimpleNamespace

import pytest


def _validate_environment_command_waits_for_every_compose_service(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import app.platform.environment_compose as compose

    configuration_path = tmp_path / "config" / "environments" / "development.yaml"
    configuration_path.parent.mkdir(parents=True)
    configuration_path.write_text("application:\n  environment: development\n", encoding="utf-8")
    definition = SimpleNamespace(configuration_path=configuration_path.resolve())
    calls: list[tuple[object, dict[str, str]]] = []

    monkeypatch.setattr(compose, "_repository_root_from_configuration", lambda _: tmp_path)
    monkeypatch.setattr(
        compose,
        "load_application_configuration",
        lambda **_: SimpleNamespace(application=SimpleNamespace(environment="development")),
    )
    monkeypatch.setattr(compose, "environment_stack_definition", lambda *_, **__: definition)
    monkeypatch.setattr(compose, "_technical_environment_from_repository", lambda _: {})

    monkeypatch.setattr(
        compose,
        "_wait_for_first_environment_service_exit",
        lambda observed_definition, *, technical_environment: calls.append(
            (observed_definition, dict(technical_environment))
        ),
    )

    compose.wait_environment_compose_stack(
        service_id="ui",
        port=8081,
        config_path=str(configuration_path),
    )

    assert calls == [(definition, {})]


def _validate_development_proof_reemits_five_qualification_pages_with_unique_metadata(
    tmp_path: Path,
) -> None:
    from pypdf import PdfReader

    from app.platform.development_e2e import (
        _EXPECTED_QUALIFICATION_ROUTES,
        _prepare_reemitted_real_pdf,
        _public_qualification_route_names,
        _qualification_route_names,
    )

    repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    source_pdf = (
        repository_root
        / "data"
        / "corpus"
        / "ostrading-environment-qualification-5-pages.pdf"
    )
    derived_pdf = _prepare_reemitted_real_pdf(
        source_pdf=source_pdf,
        temporary_report_root=tmp_path / "reports" / "temp",
        proof_id="A" * 32,
    )

    source_bytes = source_pdf.read_bytes()
    derived_bytes = derived_pdf.read_bytes()
    source_reader = PdfReader(str(source_pdf), strict=True)
    assert len(source_reader.pages) == 5
    bibliographic_evidence = " ".join(
        " ".join((page.extract_text() or "").split())
        for page in source_reader.pages
    )
    assert "The Original Turtle Trading Rules" in bibliographic_evidence
    assert "Curtis Faith, an Original Turtle" in bibliographic_evidence
    assert _qualification_route_names(source_pdf) == _EXPECTED_QUALIFICATION_ROUTES
    manifest = json.loads(
        (
            repository_root
            / "docs"
            / "governance"
            / "m013_environment_qualification_fixture.json"
        ).read_text(encoding="utf-8")
    )
    assert manifest["fixture_sha256"] == hashlib.sha256(source_bytes).hexdigest()
    assert [page["fixture_page_number"] for page in manifest["pages"]] == [1, 2, 3, 4, 5]
    assert [page["expected_route_name"] for page in manifest["pages"]] == list(
        _EXPECTED_QUALIFICATION_ROUTES
    )
    assert [page["expected_conversion_tool_name"] for page in manifest["pages"]] == [
        "DOCLING_STANDARD",
        "GRANITE_DOCLING",
        "GEMMA_VISION",
        "DOCLING_STANDARD",
        None,
    ]
    assert manifest["pages"][2]["expected_fallback_triggering_error_code"] == (
        "DOCLING_PROVENANCE_MISSING"
    )
    public_diagnostic = {
        "source_page_count": 5,
        "pages": [
            {"page_number": page_number, "route": {"route_name": route_name}}
            for page_number, route_name in enumerate(
                _EXPECTED_QUALIFICATION_ROUTES,
                start=1,
            )
        ],
    }
    assert (
        _public_qualification_route_names(public_diagnostic)
        == _EXPECTED_QUALIFICATION_ROUTES
    )
    public_diagnostic["pages"][1]["route"]["route_name"] = "SCAN_GRANITE"
    with pytest.raises(
        RuntimeError,
        match="DEVELOPMENT_E2E_QUALIFICATION_ROUTES_INVALID",
    ):
        _public_qualification_route_names(public_diagnostic)
    derived_reader = PdfReader(str(derived_pdf), strict=True)
    assert len(derived_reader.pages) == 5
    assert derived_bytes.startswith(b"%PDF-")
    assert derived_bytes.rstrip().endswith(b"%%EOF")
    assert derived_bytes != source_bytes
    assert derived_reader.metadata["/OSTradingProofId"] == "A" * 32


def _validate_development_readiness_ignores_previous_lifecycle_event(
    tmp_path: Path,
) -> None:
    from app.platform.development_e2e import _environment_lifecycle_state_since

    log_path = tmp_path / "development.log"
    log_path.write_bytes(
        b'{"event_type":"environment_lifecycle","environment":"development",'
        b'"state":"ready","error_code":null}\n'
    )
    current_run_offset = log_path.stat().st_size
    with log_path.open("ab") as stream:
        stream.write(
            b'{"event_type":"environment_lifecycle","environment":"development",'
            b'"state":"starting","error_code":null}\n'
        )

    assert _environment_lifecycle_state_since(
        log_path=log_path,
        start_offset=current_run_offset,
    ) == "starting"

    with log_path.open("ab") as stream:
        stream.write(
            b'{"event_type":"environment_lifecycle","environment":"development",'
            b'"state":"ready","error_code":null}\n'
        )
    assert _environment_lifecycle_state_since(
        log_path=log_path,
        start_offset=current_run_offset,
    ) == "ready"


def _validate_development_process_owns_a_windows_console_group(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import app.platform.development_e2e as development_e2e

    popen_calls: list[dict[str, object]] = []
    stop_calls: list[object] = []
    process = SimpleNamespace()

    def record_popen(*_args, **kwargs):
        popen_calls.append(kwargs)
        return process

    configuration = SimpleNamespace(
        application=SimpleNamespace(
            environment="development",
            deployment_id="ostrading-development-local",
        ),
        configuration_hash="a" * 64,
    )

    with monkeypatch.context() as isolated:
        isolated.setattr(development_e2e.shutil, "which", lambda _: "uv.exe")
        isolated.setattr(development_e2e.subprocess, "Popen", record_popen)
        isolated.setattr(development_e2e, "_wait_public_readiness", lambda **_: None)
        isolated.setattr(
            development_e2e,
            "_stop_development_command",
            lambda **kwargs: stop_calls.append(kwargs["process"]),
        )
        with development_e2e._running_development_command(
            repository_root=tmp_path,
            token="token-development",
            log_path=tmp_path / "development.log",
            configuration=configuration,
            ca_bundle_path=tmp_path / "caddy-ca.pem",
        ):
            pass

    assert len(popen_calls) == 1
    assert popen_calls[0]["creationflags"] == subprocess.CREATE_NEW_PROCESS_GROUP
    assert stop_calls == [process]


def _validate_development_controlled_stop_interrupts_the_console_group(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import app.platform.development_e2e as development_e2e

    signals: list[object] = []
    wait_timeouts: list[int] = []

    class Process:
        returncode = None

        @staticmethod
        def poll():
            return None

        def send_signal(self, event) -> None:
            signals.append(event)

        @staticmethod
        def wait(*, timeout: int) -> int:
            wait_timeouts.append(timeout)
            return 0

    monkeypatch.setattr(
        development_e2e,
        "_run_compose",
        lambda *_args, **_kwargs: pytest.fail("Compose ne doit pas servir de signal d'arrêt."),
    )

    development_e2e._stop_development_command(
        repository_root=tmp_path,
        process=Process(),
    )

    assert signals == [signal.CTRL_BREAK_EVENT]
    assert wait_timeouts == [180]


def _validate_development_controlled_stop_accepts_only_its_windows_break_exit(
    tmp_path: Path,
) -> None:
    import app.platform.development_e2e as development_e2e

    windows_control_c_exit = 0xC000013A
    signals: list[object] = []

    class Process:
        returncode = None

        def __init__(self, return_code: int) -> None:
            self._return_code = return_code

        @staticmethod
        def poll():
            return None

        def send_signal(self, event) -> None:
            signals.append(event)

        def wait(self, *, timeout: int) -> int:
            assert timeout == 180
            return self._return_code

    with pytest.raises(
        development_e2e.DevelopmentE2EError,
        match="DEVELOPMENT_E2E_COMMAND_STOP_FAILED: code=1",
    ):
        development_e2e._stop_development_command(
            repository_root=tmp_path,
            process=Process(return_code=1),
        )

    development_e2e._stop_development_command(
        repository_root=tmp_path,
        process=Process(return_code=windows_control_c_exit),
    )

    assert signals == [signal.CTRL_BREAK_EVENT, signal.CTRL_BREAK_EVENT]


def _validate_development_entrypoint_maps_console_break_to_keyboard_interrupt(
    monkeypatch,
) -> None:
    import app.platform.environment_command as environment_command

    previous_handler = object()
    registrations: list[tuple[object, object]] = []

    def record_signal(signum, handler):
        registrations.append((signum, handler))
        return previous_handler

    monkeypatch.setattr(environment_command.signal, "signal", record_signal)
    monkeypatch.setattr(environment_command, "_run_entrypoint", lambda _: 0)

    assert environment_command.development() == 0
    assert registrations == [
        (signal.SIGBREAK, signal.default_int_handler),
        (signal.SIGBREAK, previous_handler),
    ]


def _validate_development_resume_reuses_explicit_existing_proof_without_reemission(
    tmp_path: Path,
) -> None:
    from app.platform.development_e2e import (
        _prepare_reemitted_real_pdf,
        _select_development_e2e_proof,
    )

    repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    source_pdf = (
        repository_root
        / "data"
        / "corpus"
        / "ostrading-environment-qualification-5-pages.pdf"
    )
    report_root = tmp_path / "reports"
    proof_id = "B" * 32
    derived_pdf = _prepare_reemitted_real_pdf(
        source_pdf=source_pdf,
        temporary_report_root=report_root / "temp",
        proof_id=proof_id,
    )
    before = derived_pdf.read_bytes()

    selected = _select_development_e2e_proof(
        source_pdf=source_pdf,
        report_root=report_root,
        resume_proof_id=proof_id,
        resume_document_id="DOC-BA58A26E6A853C3C",
    )

    assert selected == (proof_id, derived_pdf, "DOC-BA58A26E6A853C3C")
    assert derived_pdf.read_bytes() == before
    with pytest.raises(ValueError, match="DEVELOPMENT_E2E_RESUME_PAIR_REQUIRED"):
        _select_development_e2e_proof(
            source_pdf=source_pdf,
            report_root=report_root,
            resume_proof_id=proof_id,
            resume_document_id=None,
        )


def _validate_development_product_checkpoint_preserves_public_proof_before_stop() -> None:
    from app.platform.development_e2e import (
        _ProductProof,
        _product_checkpoint_payload,
    )

    product = _ProductProof(
        document_id="DOC-BA58A26E6A853C3C",
        canonical_version_id="CVER-M004-ROUTED-BA58A26E6A853C3CC891E53C",
        projection_id="PROJ-FF2E986C45A492B10A4DD70C1CC3863F",
        answer_id="ANS-DEVELOPMENT-CHECKPOINT-001",
        citation_url=(
            "https://localhost:18443/api/v1/documents/"
            "DOC-BA58A26E6A853C3C/original#page=1"
        ),
        support_status="SUPPORTED",
        spark_raw_response_id="RAW-DEVELOPMENT-CHECKPOINT-001",
        qualification_routes=(
            "NATIVE_STANDARD",
            "MIXED_PAGEWISE",
            "PREPROCESS_GRANITE",
            "TARGETED_ENRICHMENT",
            "SKIP_EMPTY",
        ),
        progress_phases=("SUCCEEDED", "SUCCEEDED", "SUCCEEDED"),
        worker_identity_count=4,
        container_count=14,
        environment_job_count=3,
    )

    payload = _product_checkpoint_payload(
        product=product,
        proof_id="B" * 32,
        pdf_sha256="a" * 64,
        created_at="2026-07-21T22:30:00Z",
    )

    assert payload["event_type"] == "development_e2e_product_checkpoint"
    assert payload["proof_id"] == "B" * 32
    assert payload["pdf_sha256"] == "a" * 64
    assert payload["document_id"] == product.document_id
    assert payload["answer_id"] == product.answer_id
    assert payload["spark_raw_response_id"] == product.spark_raw_response_id


def test_development_real_e2e_unit(monkeypatch, tmp_path: Path) -> None:
    """Agrège les décisions unitaires dans l'unique nœud déclaré au gate."""

    _validate_environment_command_waits_for_every_compose_service(monkeypatch, tmp_path)
    _validate_development_proof_reemits_five_qualification_pages_with_unique_metadata(
        tmp_path,
    )
    _validate_development_readiness_ignores_previous_lifecycle_event(tmp_path)
    _validate_development_process_owns_a_windows_console_group(monkeypatch, tmp_path)
    _validate_development_controlled_stop_interrupts_the_console_group(
        monkeypatch,
        tmp_path,
    )
    _validate_development_controlled_stop_accepts_only_its_windows_break_exit(
        tmp_path,
    )
    _validate_development_entrypoint_maps_console_break_to_keyboard_interrupt(monkeypatch)
    _validate_development_resume_reuses_explicit_existing_proof_without_reemission(
        tmp_path,
    )
    _validate_development_product_checkpoint_preserves_public_proof_before_stop()

    import app.platform.development_e2e as development_e2e

    monkeypatch.setattr(
        development_e2e.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=" M tracked.py\n",
        ),
    )
    with pytest.raises(ValueError, match="DEVELOPMENT_E2E_WORKTREE_DIRTY"):
        development_e2e._git_revision(tmp_path)
