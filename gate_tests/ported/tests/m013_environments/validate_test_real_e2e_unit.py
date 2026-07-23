"""Décisions unitaires du superviseur de parcours réel test."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest


def test_test_real_e2e_unit(monkeypatch, tmp_path: Path, capsys) -> None:
    import app.platform.test_e2e as test_e2e

    from app.platform.test_e2e import (
        TestEnvironmentCycle,
        _exclusive_test_qualification,
        _require_persistent_lifecycle_owner,
        _run_test_cycles,
        _verify_test_cleanup_target,
    )

    # Given une qualification fonctionnelle à un cycle et une qualification
    # d'isolation à deux cycles, choisies explicitement par leur commande.
    calls: list[int] = []

    def cycle_runner(*, run_number: int, **_kwargs):
        calls.append(run_number)
        return SimpleNamespace(run_number=run_number)

    # When le superviseur exécute la qualification fonctionnelle.
    functional_results = _run_test_cycles(
        cycle_count=1,
        repository_root=tmp_path,
        pdf_path=tmp_path / "fixture.pdf",
        cycle_runner=cycle_runner,
    )

    # Then un seul cycle complet est lancé.
    assert calls == [1]
    assert tuple(result.run_number for result in functional_results) == (1,)

    calls.clear()
    isolation_results = _run_test_cycles(
        cycle_count=2,
        repository_root=tmp_path,
        pdf_path=tmp_path / "fixture.pdf",
        cycle_runner=cycle_runner,
    )

    # Et la qualification d'isolation conserve deux cycles ordonnés, sans
    # valeur par défaut ni troisième mode implicite.
    assert calls == [1, 2]
    assert tuple(result.run_number for result in isolation_results) == (1, 2)
    for invalid_cycle_count in (0, 3, True, None):
        with pytest.raises(ValueError, match="TEST_E2E_CYCLE_COUNT_INVALID"):
            _run_test_cycles(
                cycle_count=invalid_cycle_count,
                repository_root=tmp_path,
                pdf_path=tmp_path / "fixture.pdf",
                cycle_runner=cycle_runner,
            )

    # Et une cible de teardown étrangère est refusée avant tout effet.
    valid = TestEnvironmentCycle(
        environment="test",
        deployment_id="ostrading-test-ci",
        lifecycle_id="11111111-1111-4111-8111-111111111111",
    )
    assert _verify_test_cleanup_target(valid) is valid
    with pytest.raises(ValueError, match="ADMINISTRATIVE_OPERATION_FORBIDDEN"):
        _verify_test_cleanup_target(
            TestEnvironmentCycle(
                environment="production",
                deployment_id="ostrading-production-primary",
                lifecycle_id="22222222-2222-4222-8222-222222222222",
            )
        )

    assert _require_persistent_lifecycle_owner(valid, valid.lifecycle_id) == valid.lifecycle_id
    with pytest.raises(ValueError, match="TEST_LIFECYCLE_OWNERSHIP_MISMATCH"):
        _require_persistent_lifecycle_owner(valid, "33333333-3333-4333-8333-333333333333")

    lock_path = tmp_path / "test-e2e.lock"
    with _exclusive_test_qualification(lock_path):
        with pytest.raises(test_e2e.TestE2EError, match="TEST_E2E_ALREADY_RUNNING"):
            with _exclusive_test_qualification(lock_path):
                pass

    from app.platform.environment_command import _run_test_qualification

    published: list[object] = []
    expected_report = SimpleNamespace(environment="test")

    assert (
        _run_test_qualification(
            command_name="test",
            argv=(),
            repository_root=tmp_path,
            pdf_path=tmp_path / "fixture.pdf",
            runner=lambda **_kwargs: expected_report,
            publish_report=published.append,
        )
        == 0
    )
    assert published == [expected_report]
    with pytest.raises(ValueError, match="UV_ENVIRONMENT_ARGUMENTS_FORBIDDEN"):
        _run_test_qualification(
            command_name="test",
            argv=("--config",),
            repository_root=tmp_path,
            pdf_path=tmp_path / "fixture.pdf",
            runner=lambda **_kwargs: expected_report,
            publish_report=published.append,
        )

    teardown_events: list[str] = []

    @contextmanager
    def supervised_stack(_launch_configuration):
        teardown_events.append("enter")
        try:
            yield
        finally:
            teardown_events.append("exit")

    @contextmanager
    def public_client(**_kwargs):
        yield object()

    monkeypatch.setattr(test_e2e, "start_environment_compose_stack", supervised_stack)
    monkeypatch.setattr(
        test_e2e,
        "_prepare_test_reemitted_pdf",
        lambda **_: tmp_path / "test-e2e.pdf",
    )
    monkeypatch.setattr(test_e2e, "_sha256_file", lambda _: "a" * 64)
    monkeypatch.setattr(test_e2e, "_read_secret", lambda _: "s" * 32)
    monkeypatch.setattr(test_e2e, "_technical_environment_from_repository", lambda _: {})
    monkeypatch.setattr(test_e2e, "export_environment_caddy_ca", lambda **_: tmp_path / "ca.crt")
    monkeypatch.setattr(test_e2e, "_verify_runtime_excludes_non_test_credentials", lambda **_: None)
    monkeypatch.setattr(test_e2e, "_public_client", public_client)
    monkeypatch.setattr(test_e2e, "_verify_public_readiness", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(test_e2e, "_verify_public_ui", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(test_e2e, "_all_public_document_ids", lambda _: ())
    monkeypatch.setattr(
        test_e2e,
        "_exercise_product",
        lambda **_: (_ for _ in ()).throw(httpx.ConnectError("network red")),
    )
    monkeypatch.setattr(
        test_e2e,
        "_write_secret_free_payload",
        lambda **arguments: teardown_events.append(
            f"report:{arguments['payload']['status']}"
        ),
    )
    configuration = SimpleNamespace(
        application=SimpleNamespace(
            environment="test",
            deployment_id="ostrading-test-ci",
        ),
        configuration_hash="a" * 64,
        security=SimpleNamespace(
            secrets=SimpleNamespace(local_api_token_path="config/secrets/test/token")
        )
    )

    with pytest.raises(test_e2e.TestE2EError, match="TEST_E2E_NETWORK_FAILED"):
        test_e2e._run_single_test_cycle(
            run_number=1,
            repository_root=tmp_path,
            pdf_path=tmp_path / "fixture.pdf",
            configuration=configuration,
            report_root=tmp_path / "reports",
        )
    assert teardown_events == ["enter", "report:RED", "exit"]

    monkeypatch.setattr(
        test_e2e,
        "_exercise_product",
        lambda **_: (_ for _ in ()).throw(
            test_e2e.DevelopmentE2EError(
                "DEVELOPMENT_E2E_ACTION_FAILED: CONVERT_DOCUMENT: 'PAGE_FAILED'"
            )
        ),
    )
    with pytest.raises(
        test_e2e.TestE2EError,
        match=(
            "TEST_E2E_PRODUCT_FAILED: DEVELOPMENT_E2E_ACTION_FAILED: "
            "CONVERT_DOCUMENT: 'PAGE_FAILED'"
        ),
    ):
        test_e2e._run_single_test_cycle(
            run_number=1,
            repository_root=tmp_path,
            pdf_path=tmp_path / "fixture.pdf",
            configuration=configuration,
            report_root=tmp_path / "reports",
        )
    assert teardown_events == [
        "enter",
        "report:RED",
        "exit",
        "enter",
        "report:RED",
        "exit",
    ]

    import app.platform.environment_command as command

    monkeypatch.setattr(
        command,
        "run_test_environment_e2e",
        lambda **_: (_ for _ in ()).throw(test_e2e.TestE2EError("QUALIFICATION_RED")),
    )
    monkeypatch.setattr(command.sys, "argv", ["test"])
    assert command.test() == 1
    assert "QUALIFICATION_RED" in capsys.readouterr().err

    monkeypatch.setattr(
        command,
        "run_test_environment_isolation_e2e",
        lambda **_: (_ for _ in ()).throw(test_e2e.TestE2EError("ISOLATION_RED")),
    )
    monkeypatch.setattr(command.sys, "argv", ["test-isolation"])
    assert command.test_isolation() == 1
    assert "ISOLATION_RED" in capsys.readouterr().err
