"""Décisions unitaires découvertes pendant la preuve development réelle."""

from __future__ import annotations

from pathlib import Path
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


def _validate_development_proof_reemits_every_real_pdf_page_with_unique_metadata(
    tmp_path: Path,
) -> None:
    from pypdf import PdfReader

    from app.platform.development_e2e import _prepare_reemitted_real_pdf

    repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    source_pdf = (
        repository_root
        / "data"
        / "corpus"
        / "the-original-turtle-trading-rules.pdf"
    )
    derived_pdf = _prepare_reemitted_real_pdf(
        source_pdf=source_pdf,
        temporary_report_root=tmp_path / "reports" / "temp",
        proof_id="A" * 32,
    )

    source_bytes = source_pdf.read_bytes()
    derived_bytes = derived_pdf.read_bytes()
    assert len(PdfReader(str(source_pdf), strict=True).pages) == 38
    derived_reader = PdfReader(str(derived_pdf), strict=True)
    assert len(derived_reader.pages) == 38
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


def _validate_development_controlled_stop_releases_wait_via_edge_gateway(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import app.platform.development_e2e as development_e2e

    calls: list[tuple[str, ...]] = []
    process = SimpleNamespace(poll=lambda: None, wait=lambda **_: 0)
    monkeypatch.setattr(
        development_e2e,
        "environment_stack_definition",
        lambda *_, **__: SimpleNamespace(),
    )
    monkeypatch.setattr(
        development_e2e,
        "_technical_environment_from_repository",
        lambda _: {},
    )

    def record_run(_definition, arguments, **_kwargs):
        calls.append(tuple(arguments))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(development_e2e, "_run_compose", record_run)

    development_e2e._stop_development_command(
        repository_root=tmp_path,
        process=process,
    )

    assert calls == [("stop", "--timeout", "30", "edge-gateway")]


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
        / "the-original-turtle-trading-rules.pdf"
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
        progress_phases=("SUCCEEDED", "SUCCEEDED", "SUCCEEDED"),
        worker_identity_count=6,
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
    _validate_development_proof_reemits_every_real_pdf_page_with_unique_metadata(
        tmp_path,
    )
    _validate_development_readiness_ignores_previous_lifecycle_event(tmp_path)
    _validate_development_controlled_stop_releases_wait_via_edge_gateway(
        monkeypatch,
        tmp_path,
    )
    _validate_development_resume_reuses_explicit_existing_proof_without_reemission(
        tmp_path,
    )
    _validate_development_product_checkpoint_preserves_public_proof_before_stop()

    import app.platform.development_e2e as development_e2e

    source_deploy = tmp_path / "deploy" / "environments" / "development.compose.yaml"
    source_config = tmp_path / "config" / "environments" / "development.yaml"
    source_deploy.parent.mkdir(parents=True, exist_ok=True)
    source_config.parent.mkdir(parents=True, exist_ok=True)
    source_deploy.write_text("name: ostrading-development\n", encoding="utf-8")
    source_config.write_text("application:\n  environment: development\n", encoding="utf-8")
    assert development_e2e._probe_foreign_environment(
        repository_root=tmp_path,
        source_environment="development",
        environment="production",
        forbidden_document_id="DOC-NON-MUTATING-PROBE",
    ) == "production:ABSENT"
    source_deploy.write_text(
        "name: ostrading-development\nvolume: data/environments/production\n",
        encoding="utf-8",
    )
    with pytest.raises(
        development_e2e.DevelopmentE2EError,
        match="DEVELOPMENT_E2E_FOREIGN_RESOURCE_VISIBLE",
    ):
        development_e2e._probe_foreign_environment(
            repository_root=tmp_path,
            source_environment="development",
            environment="production",
            forbidden_document_id="DOC-NON-MUTATING-PROBE",
        )

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
