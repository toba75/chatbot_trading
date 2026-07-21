"""Décisions unitaires découvertes pendant la preuve development réelle."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace


def test_environment_command_waits_for_every_compose_service(monkeypatch, tmp_path: Path) -> None:
    import app.platform.environment_compose as compose

    configuration_path = tmp_path / "config" / "environments" / "development.yaml"
    configuration_path.parent.mkdir(parents=True)
    configuration_path.write_text("application:\n  environment: development\n", encoding="utf-8")
    definition = SimpleNamespace(configuration_path=configuration_path.resolve())
    calls: list[tuple[str, ...]] = []

    monkeypatch.setattr(compose, "_repository_root_from_configuration", lambda _: tmp_path)
    monkeypatch.setattr(
        compose,
        "load_application_configuration",
        lambda **_: SimpleNamespace(application=SimpleNamespace(environment="development")),
    )
    monkeypatch.setattr(compose, "environment_stack_definition", lambda *_, **__: definition)
    monkeypatch.setattr(compose, "_technical_environment_from_repository", lambda _: {})

    def record_run(_definition, arguments, **_kwargs):
        calls.append(tuple(arguments))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(compose, "_run_compose", record_run)

    compose.wait_environment_compose_stack(
        service_id="ui",
        port=8081,
        config_path=str(configuration_path),
    )

    assert calls == [("wait", *compose.REQUIRED_SERVICE_IDS)]


def test_development_proof_reemits_every_real_pdf_page_with_unique_metadata(
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
