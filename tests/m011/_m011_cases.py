from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping


REPO_ROOT = Path(sys.argv[1])
CASE_NAME = sys.argv[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def expect_raises(expected_fragment: str, action: Callable[[], object]) -> Exception:
    try:
        action()
    except Exception as exc:  # noqa: BLE001 - les tests valident le message public.
        if expected_fragment not in str(exc):
            raise AssertionError(
                f"Erreur inattendue. Fragment attendu: {expected_fragment}. Erreur: {exc}"
            ) from exc
        return exc
    raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def sha256_payload(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def run_powershell(script_path: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            *arguments,
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def assert_success(result: subprocess.CompletedProcess[str], expected_fragment: str) -> None:
    output = result.stdout + result.stderr
    if result.returncode != 0:
        raise AssertionError(f"Commande attendue GREEN. Code: {result.returncode}. Sortie: {output}")
    if expected_fragment not in output:
        raise AssertionError(f"Fragment attendu absent: {expected_fragment}. Sortie: {output}")


def assert_failure(
    result: subprocess.CompletedProcess[str],
    expected_fragment: str,
    message: str,
) -> None:
    output = result.stdout + result.stderr
    if result.returncode == 0:
        raise AssertionError(message)
    if expected_fragment not in output:
        raise AssertionError(f"{message}. Fragment attendu: {expected_fragment}. Sortie: {output}")


def build_strategy_snapshot(suffix: str = "OK"):
    from app.contracts.strategy_experiments import StrategySnapshot

    return StrategySnapshot.from_payload(
        {
            "schema_version": "1.0",
            "strategy_id": f"STRAT-M011-{suffix}",
            "strategy_version_id": f"SVER-M011-{suffix}-V000001",
            "spec_hash": "a" * 64,
            "status": "COMPILABLE",
            "rules": [
                {
                    "rule_id": f"RULE-M011-{suffix}-ENTRY",
                    "kind": "ENTRY",
                    "expression": "trend_60d > 0",
                    "origin": "SOURCE",
                    "deterministic": True,
                    "evidence_refs": [f"CLM-M011-{suffix}@1"],
                }
            ],
            "parameters": [
                {
                    "name": "lookback_days",
                    "origin": "PARAMETER_TO_CALIBRATE",
                    "blocking": True,
                    "resolution_status": "RESOLVED",
                    "value": 60,
                }
            ],
            "constraints": [
                {
                    "name": "max_drawdown",
                    "origin": "USER_CONSTRAINT",
                    "value": "10pct",
                }
            ],
            "data_requirements": [
                {
                    "name": "daily_adjusted_close",
                    "frequency": "daily",
                    "point_in_time": True,
                }
            ],
            "validation_plan": {
                "compiled_representation_hash": "b" * 64,
                "protocol": "walk_forward_v1",
            },
            "evidence_refs": [f"CLM-M011-{suffix}@1"],
            "created_at": "2026-07-04T12:00:00Z",
        }
    )


def build_data_snapshot(suffix: str = "OK"):
    from app.experimentation.domain.experiment import DataSnapshotRef

    return DataSnapshotRef(
        data_snapshot_id=f"DATA-M011-{suffix}",
        data_snapshot_hash="c" * 64,
        universe=("SPY", "TLT"),
        period_start="2020-01-01",
        period_end="2024-12-31",
        frequency="daily",
        point_in_time=True,
        validation_slice_declared_at="2026-07-04T12:05:00Z",
    )


def build_cost_model(suffix: str = "OK"):
    from app.experimentation.domain.experiment import CostModelSnapshot

    return CostModelSnapshot(
        cost_model_id=f"COST-M011-{suffix}",
        cost_model_hash="d" * 64,
        commission_bps=1.5,
        slippage_bps=2.5,
        currency="USD",
        assumptions={"venue": "paper", "borrow_fee_bps": 0.0},
    )


def build_environment(suffix: str = "OK"):
    from app.experimentation.domain.experiment import ExecutionEnvironment

    return ExecutionEnvironment(
        environment_id=f"ENV-M011-{suffix}",
        execution_environment_hash="e" * 64,
        code_version="m011-test-code",
        engine_version="deterministic-engine-v1",
        seed=42,
        created_at="2026-07-04T12:06:00Z",
    )


def planned_experiment(suffix: str = "OK"):
    from app.experimentation.domain.experiment import Experiment

    return Experiment.plan(
        experiment_id=f"EXP-M011-{suffix}",
        strategy_snapshot=build_strategy_snapshot(suffix),
        mandate={
            "objective": "Evaluer une hypothese de tendance sans promesse de rentabilite.",
            "risk_limit": "drawdown_10pct",
        },
        created_at="2026-07-04T12:01:00Z",
    )


def ready_experiment(suffix: str = "OK"):
    experiment = planned_experiment(suffix)
    experiment = experiment.attach_data_snapshot(
        data_snapshot=build_data_snapshot(suffix),
        expected_version=experiment.version,
    )
    return experiment.attach_cost_environment(
        cost_model=build_cost_model(suffix),
        execution_environment=build_environment(suffix),
        frozen_at="2026-07-04T12:07:00Z",
        expected_version=experiment.version,
    )


def running_experiment(suffix: str = "OK"):
    experiment = ready_experiment(suffix)
    experiment = experiment.schedule(
        scheduled_at="2026-07-04T12:08:00Z",
        expected_version=experiment.version,
    )
    return experiment.start(
        started_at="2026-07-04T12:09:00Z",
        expected_version=experiment.version,
    )


def completed_experiment(suffix: str = "OK"):
    from app.experimentation.adapters.deterministic_backtest_engine import (
        DeterministicBacktestEngineAdapter,
    )
    from app.experimentation.adapters.in_memory_experiment_repository import (
        InMemoryExperimentResultRepository,
    )

    experiment = running_experiment(suffix)
    engine_result = DeterministicBacktestEngineAdapter().run(experiment)
    completed = experiment.complete(
        engine_result=engine_result,
        completed_at="2026-07-04T12:10:00Z",
        expected_version=experiment.version,
    )
    result_repository = InMemoryExperimentResultRepository.empty()
    result_repository.append(completed.result)
    return completed, result_repository


def precondition_acceptance() -> None:
    validator = REPO_ROOT / "scripts" / "validate_m011_precondition.ps1"
    result = run_powershell(validator)
    assert_success(result, "Precondition M-011 valide")
    print("Test d'acceptation de precondition GREEN M-011: OK")


def precondition_unit() -> None:
    validator = REPO_ROOT / "scripts" / "validate_m011_precondition.ps1"
    temporary_parent = REPO_ROOT / "docs" / "governance"
    with tempfile.TemporaryDirectory(prefix=".tmp_m011_precondition_", dir=temporary_parent) as temporary:
        report_path = Path(temporary) / "m011_precondition_green.md"
        result = run_powershell(validator, "-Path", str(report_path))
        assert_failure(result, "Rapport de precondition M-011 absent", "Un rapport absent doit etre refuse.")
    print("Tests unitaires de precondition M-011: OK")


def specification_acceptance() -> None:
    validator = REPO_ROOT / "scripts" / "validate_m011_specification.ps1"
    spec = REPO_ROOT / "docs" / "specs" / "m011_experience_reproductible.md"
    result = run_powershell(validator, "-Path", str(spec))
    assert_success(result, "Specification M-011 valide")
    print("Test d'acceptation de specification M-011: OK")


def specification_unit() -> None:
    validator = REPO_ROOT / "scripts" / "validate_m011_specification.ps1"
    spec = REPO_ROOT / "docs" / "specs" / "m011_experience_reproductible.md"
    temporary_parent = REPO_ROOT / "docs" / "specs"
    with tempfile.TemporaryDirectory(prefix=".tmp_m011_spec_", dir=temporary_parent) as temporary:
        temp_spec = Path(temporary) / "m011_spec.md"
        shutil.copyfile(spec, temp_spec)
        valid = run_powershell(validator, "-Path", str(temp_spec))
        assert_success(valid, "Specification M-011 valide")
        content = temp_spec.read_text(encoding="utf-8").replace("CompareExperiments", "CompareMissing")
        temp_spec.write_text(content, encoding="utf-8")
        invalid = run_powershell(validator, "-Path", str(temp_spec))
        assert_failure(invalid, "Terme M-011 absent: CompareExperiments", "CompareExperiments doit etre obligatoire.")
    print("Tests unitaires de specification M-011: OK")


def experiment_planning_acceptance() -> None:
    from app.experimentation.adapters.in_memory_experiment_repository import (
        InMemoryExperimentRepository,
    )

    experiment = planned_experiment("PLAN")
    repository = InMemoryExperimentRepository.empty()
    repository.save(experiment)

    assert experiment.status == "PLANNED"
    assert experiment.strategy_version_id == "SVER-M011-PLAN-V000001"
    assert experiment.spec_hash == "a" * 64
    assert experiment.strategy_parameter_hash == sha256_payload(
        {"parameters": build_strategy_snapshot("PLAN").to_payload()["parameters"]}
    )
    assert repository.get("EXP-M011-PLAN") == experiment
    expect_raises("registre append-only", lambda: repository.delete("EXP-M011-PLAN"))
    expect_raises(
        "reference mutable interdite",
        lambda: planned_experiment("PLAN").with_mutable_strategy_reference("strategy_candidate:current"),
    )
    print("Test d'acceptation de planification d'experience M-011: OK")


def experiment_planning_unit() -> None:
    from app.contracts.strategy_experiments import StrategySnapshot
    from app.experimentation.domain.experiment import Experiment

    payload = build_strategy_snapshot("BAD").to_payload()
    payload["status"] = "DRAFT"
    expect_raises("status non autorise", lambda: StrategySnapshot.from_payload(payload))
    expect_raises(
        "expected_version incoherent",
        lambda: planned_experiment("UNIT").attach_data_snapshot(
            data_snapshot=build_data_snapshot("UNIT"),
            expected_version=999,
        ),
    )
    expect_raises(
        "experiment_id invalide",
        lambda: Experiment.plan(
            experiment_id="BAD",
            strategy_snapshot=build_strategy_snapshot("UNIT"),
            mandate={"objective": "test"},
            created_at="2026-07-04T12:01:00Z",
        ),
    )
    print("Tests unitaires de planification d'experience M-011: OK")


def data_snapshot_freeze_acceptance() -> None:
    experiment = planned_experiment("DATA")
    frozen = experiment.attach_data_snapshot(
        data_snapshot=build_data_snapshot("DATA"),
        expected_version=experiment.version,
    )
    assert frozen.data_snapshot_ref is not None
    assert frozen.data_snapshot_ref.data_snapshot_id == "DATA-M011-DATA"
    assert frozen.data_snapshot_ref.point_in_time is True
    expect_raises(
        "reference mutable interdite",
        lambda: build_data_snapshot("LATEST").with_reference("market/latest"),
    )
    expect_raises(
        "snapshot donnees deja fige",
        lambda: frozen.attach_data_snapshot(
            data_snapshot=build_data_snapshot("DATA2"),
            expected_version=frozen.version,
        ),
    )
    print("Test d'acceptation de gel du snapshot de donnees M-011: OK")


def data_snapshot_freeze_unit() -> None:
    from app.experimentation.domain.experiment import DataSnapshotRef

    expect_raises(
        "periode snapshot incoherente",
        lambda: DataSnapshotRef(
            data_snapshot_id="DATA-M011-BAD",
            data_snapshot_hash="c" * 64,
            universe=("SPY",),
            period_start="2024-12-31",
            period_end="2020-01-01",
            frequency="daily",
            point_in_time=True,
            validation_slice_declared_at="2026-07-04T12:05:00Z",
        ),
    )
    expect_raises(
        "snapshot point-in-time requis",
        lambda: DataSnapshotRef(
            data_snapshot_id="DATA-M011-BAD2",
            data_snapshot_hash="c" * 64,
            universe=("SPY",),
            period_start="2020-01-01",
            period_end="2024-12-31",
            frequency="daily",
            point_in_time=False,
            validation_slice_declared_at="2026-07-04T12:05:00Z",
        ),
    )
    print("Tests unitaires de gel du snapshot de donnees M-011: OK")


def cost_environment_freeze_acceptance() -> None:
    experiment = ready_experiment("COST")
    assert experiment.frozen_inputs is not None
    frozen_payload = experiment.frozen_inputs.to_payload()
    assert frozen_payload["cost_model_hash"] == "d" * 64
    assert frozen_payload["execution_environment_hash"] == "e" * 64
    assert frozen_payload["strategy_parameter_hash"] == experiment.strategy_parameter_hash
    expect_raises(
        "entrees deja verrouillees",
        lambda: experiment.attach_cost_environment(
            cost_model=build_cost_model("NEXT"),
            execution_environment=build_environment("NEXT"),
            frozen_at="2026-07-04T12:07:00Z",
            expected_version=experiment.version,
        ),
    )
    print("Test d'acceptation de gel couts environnement M-011: OK")


def cost_environment_freeze_unit() -> None:
    from app.experimentation.domain.experiment import CostModelSnapshot, ExecutionEnvironment

    expect_raises(
        "commission_bps invalide",
        lambda: CostModelSnapshot(
            cost_model_id="COST-M011-BAD",
            cost_model_hash="d" * 64,
            commission_bps=-1.0,
            slippage_bps=2.5,
            currency="USD",
            assumptions={"venue": "paper"},
        ),
    )
    expect_raises(
        "seed invalide",
        lambda: ExecutionEnvironment(
            environment_id="ENV-M011-BAD",
            execution_environment_hash="e" * 64,
            code_version="m011-test-code",
            engine_version="deterministic-engine-v1",
            seed=-1,
            created_at="2026-07-04T12:06:00Z",
        ),
    )
    print("Tests unitaires de gel couts environnement M-011: OK")


def experiment_start_lock_acceptance() -> None:
    experiment = ready_experiment("START")
    scheduled = experiment.schedule(
        scheduled_at="2026-07-04T12:08:00Z",
        expected_version=experiment.version,
    )
    cancelled = scheduled.cancel(
        cancelled_at="2026-07-04T12:08:30Z",
        reason="Demande utilisateur explicite.",
        expected_version=scheduled.version,
    )
    assert cancelled.status == "CANCELLED"
    assert "ExperimentCancelled" in cancelled.event_types()
    running = scheduled.start(
        started_at="2026-07-04T12:09:00Z",
        expected_version=scheduled.version,
    )
    assert running.status == "RUNNING"
    expect_raises(
        "entrees verrouillees requises",
        lambda: planned_experiment("NOTREADY").schedule(
            scheduled_at="2026-07-04T12:08:00Z",
            expected_version=1,
        ),
    )
    print("Test d'acceptation de demarrage verrouille M-011: OK")


def experiment_start_lock_unit() -> None:
    experiment = ready_experiment("STARTUNIT")
    expect_raises(
        "transition interdite",
        lambda: planned_experiment("CANCELPLANNED").cancel(
            cancelled_at="2026-07-04T12:08:30Z",
            reason="Annulation avant planification verrouillee.",
            expected_version=1,
        ),
    )
    expect_raises(
        "transition interdite",
        lambda: experiment.start(
            started_at="2026-07-04T12:09:00Z",
            expected_version=experiment.version,
        ),
    )
    scheduled = experiment.schedule(
        scheduled_at="2026-07-04T12:08:00Z",
        expected_version=experiment.version,
    )
    expect_raises(
        "expected_version incoherent",
        lambda: scheduled.start(
            started_at="2026-07-04T12:09:00Z",
            expected_version=999,
        ),
    )
    print("Tests unitaires de demarrage verrouille M-011: OK")


def deterministic_backtest_acceptance() -> None:
    from app.experimentation.adapters.deterministic_backtest_engine import (
        DeterministicBacktestEngineAdapter,
    )

    experiment = running_experiment("BT")
    engine = DeterministicBacktestEngineAdapter()
    first = engine.run(experiment)
    second = engine.run(experiment)
    assert first.result_hash == second.result_hash
    assert first.metrics == second.metrics
    assert first.controls["lookahead_bias_control"] == "PASS"
    assert first.controls["minimum_backtest_control_count"] >= 6
    assert {artifact["artifact_type"] for artifact in first.artifacts} >= {
        "equity_curve",
        "positions",
        "transactions",
        "warnings",
        "run_log",
    }
    print("Test d'acceptation de backtest deterministe M-011: OK")


def deterministic_backtest_unit() -> None:
    from app.experimentation.adapters.deterministic_backtest_engine import (
        DeterministicBacktestEngineAdapter,
    )

    expect_raises(
        "experience RUNNING requise",
        lambda: DeterministicBacktestEngineAdapter().run(ready_experiment("BTUNIT")),
    )
    print("Tests unitaires de backtest deterministe M-011: OK")


def experiment_result_acceptance() -> None:
    from app.experimentation.adapters.in_memory_experiment_repository import (
        InMemoryExperimentResultRepository,
    )

    completed, repository = completed_experiment("RESULT")
    assert completed.result is not None
    assert completed.result.status == "COMPLETED"
    stored = repository.get("EXP-M011-RESULT")
    assert stored.result_hash == completed.result.result_hash
    expect_raises("resultat append-only viole", lambda: repository.append(completed.result.with_hash("f" * 64)))
    print("Test d'acceptation d'enregistrement de resultat M-011: OK")


def experiment_result_unit() -> None:
    from app.contracts.strategy_experiments import ExperimentResult

    completed, _ = completed_experiment("RESULTUNIT")
    payload = completed.result.to_payload()
    payload["frozen_inputs"] = dict(payload["frozen_inputs"])
    payload["frozen_inputs"]["data_snapshot_id"] = "DATA-M011-OTHER"
    expect_raises("data_snapshot_id incoherent", lambda: ExperimentResult.from_payload(payload))
    print("Tests unitaires d'enregistrement de resultat M-011: OK")


def experiment_retention_acceptance() -> None:
    from app.experimentation.adapters.in_memory_experiment_repository import (
        InMemoryExperimentResultRepository,
    )

    experiment = running_experiment("FAIL")
    failed = experiment.fail(
        failure_reason="DONNEES_INSUFFISANTES",
        completed_at="2026-07-04T12:10:00Z",
        expected_version=experiment.version,
    )
    repository = InMemoryExperimentResultRepository.empty()
    repository.append(failed.result)
    assert repository.get("EXP-M011-FAIL").status == "FAILED"
    expect_raises("suppression resultat interdite", lambda: repository.delete("EXP-M011-FAIL"))
    corrected = failed.invalidate(
        invalidated_by_experiment_id="EXP-M011-FAIL-CORRECTION",
        reason="Audit explicite.",
        invalidated_at="2026-07-04T12:15:00Z",
        expected_version=failed.version,
    )
    assert corrected.invalidated_by_experiment_id == "EXP-M011-FAIL-CORRECTION"
    assert corrected.result == failed.result
    print("Test d'acceptation de conservation resultats negatifs M-011: OK")


def experiment_retention_unit() -> None:
    experiment = running_experiment("RETUNIT")
    expect_raises(
        "failure_reason requis",
        lambda: experiment.fail(
            failure_reason="",
            completed_at="2026-07-04T12:10:00Z",
            expected_version=experiment.version,
        ),
    )
    print("Tests unitaires de conservation resultats negatifs M-011: OK")


def experiment_reproducibility_acceptance() -> None:
    from app.experimentation.adapters.deterministic_backtest_engine import (
        DeterministicBacktestEngineAdapter,
    )
    from app.experimentation.application.experiment_workflow import (
        CompareExperimentsCommand,
        CompareExperimentsHandler,
        RepeatExperimentCommand,
        RepeatExperimentHandler,
    )
    from app.experimentation.adapters.in_memory_experiment_repository import (
        InMemoryExperimentRepository,
        InMemoryExperimentResultRepository,
    )

    original, result_repository = completed_experiment("REPEAT")
    experiment_repository = InMemoryExperimentRepository.empty()
    experiment_repository.save(original)
    repeated = RepeatExperimentHandler(repository=experiment_repository).handle(
        RepeatExperimentCommand(
            source_experiment_id=original.experiment_id,
            new_experiment_id="EXP-M011-REPEAT-RERUN",
            created_at="2026-07-04T12:20:00Z",
        )
    )
    assert repeated.experiment_id != original.experiment_id
    assert repeated.repeats_experiment_id == original.experiment_id
    assert repeated.frozen_inputs.to_payload() == original.frozen_inputs.to_payload()

    running_repeat = repeated.start(
        started_at="2026-07-04T12:21:00Z",
        expected_version=repeated.version,
    )
    engine_result = DeterministicBacktestEngineAdapter().run(running_repeat)
    completed_repeat = running_repeat.complete(
        engine_result=engine_result,
        completed_at="2026-07-04T12:22:00Z",
        expected_version=running_repeat.version,
    )
    experiment_repository.save(completed_repeat)
    result_repository.append(completed_repeat.result)

    comparison = CompareExperimentsHandler(
        experiment_repository=experiment_repository,
        result_repository=result_repository,
    ).handle(
        CompareExperimentsCommand(
            left_experiment_id=original.experiment_id,
            right_experiment_id=completed_repeat.experiment_id,
            comparison_id="CMP-M011-REPEAT",
        )
    )
    assert comparison.event_type == "ExperimentComparisonCompleted"
    assert comparison.inputs_match is True
    assert comparison.metrics_match is True
    assert experiment_repository.get(original.experiment_id) == original
    print("Test d'acceptation de reproductibilite M-011: OK")


def experiment_reproducibility_unit() -> None:
    from app.experimentation.application.experiment_workflow import (
        CompareExperimentsCommand,
        CompareExperimentsHandler,
        RepeatExperimentCommand,
        RepeatExperimentHandler,
    )
    from app.experimentation.adapters.in_memory_experiment_repository import (
        InMemoryExperimentRepository,
        InMemoryExperimentResultRepository,
    )

    original, result_repository = completed_experiment("REPEATUNIT")
    experiment_repository = InMemoryExperimentRepository.empty()
    experiment_repository.save(original)
    expect_raises(
        "nouvel experiment_id requis",
        lambda: RepeatExperimentHandler(repository=experiment_repository).handle(
            RepeatExperimentCommand(
                source_experiment_id=original.experiment_id,
                new_experiment_id=original.experiment_id,
                created_at="2026-07-04T12:20:00Z",
            )
        ),
    )
    other = planned_experiment("OTHER")
    experiment_repository.save(other)
    expect_raises(
        "resultat absent",
        lambda: CompareExperimentsHandler(
            experiment_repository=experiment_repository,
            result_repository=result_repository,
        ).handle(
            CompareExperimentsCommand(
                left_experiment_id=original.experiment_id,
                right_experiment_id=other.experiment_id,
                comparison_id="CMP-M011-UNIT",
            )
        ),
    )
    print("Tests unitaires de reproductibilite M-011: OK")


def experiment_http_contract_acceptance() -> None:
    from app.experimentation.adapters.experiment_http import ExperimentHttpAdapter, HttpRequest
    from app.experimentation.adapters.in_memory_experiment_repository import (
        InMemoryExperimentRepository,
        InMemoryStrategySnapshotReader,
    )
    from app.experimentation.application.experiment_workflow import (
        AttachCostEnvironmentHandler,
        AttachDataSnapshotHandler,
        PlanExperimentHandler,
        ScheduleExperimentHandler,
    )

    repository = InMemoryExperimentRepository.empty()
    snapshot_reader = InMemoryStrategySnapshotReader.from_snapshots((build_strategy_snapshot("HTTP"),))
    adapter = ExperimentHttpAdapter(
        plan_handler=PlanExperimentHandler(snapshot_reader=snapshot_reader, repository=repository),
        attach_data_snapshot_handler=AttachDataSnapshotHandler(repository=repository),
        attach_cost_environment_handler=AttachCostEnvironmentHandler(repository=repository),
        schedule_handler=ScheduleExperimentHandler(repository=repository),
        repository=repository,
    )

    response = adapter.handle(
        HttpRequest(
            method="POST",
            path="/v1/strategies/STRAT-M011-HTTP/backtest",
            body={
                "experiment_id": "EXP-M011-HTTP",
                "strategy_snapshot_id": "SVER-M011-HTTP-V000001",
                "mandate": {"objective": "Backtest reproductible."},
                "data_snapshot": build_data_snapshot("HTTP").to_payload(),
                "cost_model": build_cost_model("HTTP").to_payload(),
                "execution_environment": build_environment("HTTP").to_payload(),
                "frozen_at": "2026-07-04T12:07:00Z",
                "scheduled_at": "2026-07-04T12:08:00Z",
            },
        )
    )
    assert response.status_code == 202
    assert response.body["status"] == "SCHEDULED"
    assert "experiment_registry_table" not in str(response.body)
    read_response = adapter.handle(HttpRequest(method="GET", path="/v1/experiments/EXP-M011-HTTP", body={}))
    assert read_response.status_code == 200
    assert read_response.body["experiment_id"] == "EXP-M011-HTTP"
    assert len(repository.all()) == 1
    forbidden = adapter.handle(
        HttpRequest(
            method="POST",
            path="/v1/strategies/STRAT-M011-HTTP/backtest",
            body={
                "experiment_registry_table": "internal",
            },
        )
    )
    assert forbidden.status_code == 400
    assert forbidden.body["error_code"] == "PUBLIC_STORAGE_FIELD_FORBIDDEN"
    missing = adapter.handle(HttpRequest(method="GET", path="/v1/experiments/EXP-M011-ABSENT", body={}))
    assert missing.status_code == 404
    assert len(repository.all()) == 1
    print("Test d'acceptation de contrat HTTP experiences M-011: OK")


def experiment_http_contract_unit() -> None:
    from app.experimentation.adapters.experiment_http import ExperimentHttpAdapter, HttpRequest
    from app.experimentation.adapters.in_memory_experiment_repository import (
        InMemoryExperimentRepository,
        InMemoryStrategySnapshotReader,
    )
    from app.experimentation.application.experiment_workflow import (
        AttachCostEnvironmentHandler,
        AttachDataSnapshotHandler,
        PlanExperimentHandler,
        ScheduleExperimentHandler,
    )

    repository = InMemoryExperimentRepository.empty()
    snapshot_reader = InMemoryStrategySnapshotReader.from_snapshots((build_strategy_snapshot("HTTPUNIT"),))
    adapter = ExperimentHttpAdapter(
        plan_handler=PlanExperimentHandler(snapshot_reader=snapshot_reader, repository=repository),
        attach_data_snapshot_handler=AttachDataSnapshotHandler(repository=repository),
        attach_cost_environment_handler=AttachCostEnvironmentHandler(repository=repository),
        schedule_handler=ScheduleExperimentHandler(repository=repository),
        repository=repository,
    )
    invalid = adapter.handle(HttpRequest(method="POST", path="/v1/strategies/STRAT-M011-HTTPUNIT/backtest", body={}))
    assert invalid.status_code == 400
    assert invalid.body["error_code"] == "HTTP_REQUEST_INVALID"
    not_found = adapter.handle(
        HttpRequest(
            method="POST",
            path="/v1/strategies/STRAT-M011-HTTPUNIT/backtest",
            body={
                "experiment_id": "EXP-M011-HTTPUNIT",
                "strategy_snapshot_id": "SVER-M011-ABSENT-V000001",
                "mandate": {"objective": "Backtest reproductible."},
                "data_snapshot": build_data_snapshot("HTTPUNIT").to_payload(),
                "cost_model": build_cost_model("HTTPUNIT").to_payload(),
                "execution_environment": build_environment("HTTPUNIT").to_payload(),
                "frozen_at": "2026-07-04T12:07:00Z",
                "scheduled_at": "2026-07-04T12:08:00Z",
            },
        )
    )
    assert not_found.status_code == 404
    assert not_found.body["error_code"] == "STRATEGY_SNAPSHOT_NOT_FOUND"
    print("Tests unitaires de contrat HTTP experiences M-011: OK")


def traceability_acceptance() -> None:
    validator = REPO_ROOT / "scripts" / "validate_m011_traceability.ps1"
    result = run_powershell(validator)
    assert_success(result, "Tracabilite M-011 valide")
    print("Test d'acceptation de tracabilite M-011: OK")


def traceability_unit() -> None:
    from app.experimentation.application.traceability_metrics import ExperimentMetricSnapshot

    unordered_metrics = {
        "invalidated_result_ratio": 0.0,
        "coherent_repeat_count": 1,
        "experiment_without_complete_cost_model_total": 0,
        "negative_experiment_retention_ratio": 1.0,
        "experiment_failure_rate_by_cause": {},
        "experiment_reproducible_rate": 1.0,
    }
    snapshot = ExperimentMetricSnapshot(
        fixture_id="m011-traceability-unit",
        fixture_path="docs/traceability/matrix.md",
        measured_at="2026-07-04T12:30:00Z",
        observation_count=1,
        normative_metrics=unordered_metrics,
    )
    assert snapshot.normative_metrics["experiment_reproducible_rate"] == 1.0
    with_extra_key = dict(unordered_metrics)
    with_extra_key["unexpected_metric"] = 1.0
    expect_raises(
        "normative_metrics incompletes",
        lambda: ExperimentMetricSnapshot(
            fixture_id="m011-traceability-extra",
            fixture_path="docs/traceability/matrix.md",
            measured_at="2026-07-04T12:30:00Z",
            observation_count=1,
            normative_metrics=with_extra_key,
        ),
    )

    validator = REPO_ROOT / "scripts" / "validate_m011_traceability.ps1"
    matrix = REPO_ROOT / "docs" / "traceability" / "matrix.md"
    spec = REPO_ROOT / "docs" / "specs" / "m011_experience_reproductible.md"
    test_gate = REPO_ROOT / "scripts" / "test.ps1"
    lint_gate = REPO_ROOT / "scripts" / "lint.ps1"
    metrics_module = REPO_ROOT / "app" / "experimentation" / "application" / "traceability_metrics.py"
    temporary_parent = REPO_ROOT / "docs" / "traceability"
    with tempfile.TemporaryDirectory(prefix=".tmp_m011_trace_", dir=temporary_parent) as temporary:
        temp = Path(temporary)
        copied_matrix = temp / "matrix.md"
        shutil.copyfile(matrix, copied_matrix)
        valid = run_powershell(
            validator,
            "-MatrixPath",
            str(copied_matrix),
            "-SpecificationPath",
            str(spec),
            "-TestGatePath",
            str(test_gate),
            "-LintGatePath",
            str(lint_gate),
            "-MetricsModulePath",
            str(metrics_module),
        )
        assert_success(valid, "Tracabilite M-011 valide")
        copied_matrix.write_text(
            copied_matrix.read_text(encoding="utf-8").replace("REQ-M011-012", "REQ-M011-ABSENT"),
            encoding="utf-8",
        )
        invalid = run_powershell(
            validator,
            "-MatrixPath",
            str(copied_matrix),
            "-SpecificationPath",
            str(spec),
            "-TestGatePath",
            str(test_gate),
            "-LintGatePath",
            str(lint_gate),
            "-MetricsModulePath",
            str(metrics_module),
        )
        assert_failure(invalid, "Exigence M-011 absente: REQ-M011-012", "La ligne de tracabilite finale doit etre obligatoire.")
    print("Tests unitaires de tracabilite M-011: OK")


CASES: dict[str, Callable[[], None]] = {
    "precondition_acceptance": precondition_acceptance,
    "precondition_unit": precondition_unit,
    "specification_acceptance": specification_acceptance,
    "specification_unit": specification_unit,
    "experiment_planning_acceptance": experiment_planning_acceptance,
    "experiment_planning_unit": experiment_planning_unit,
    "data_snapshot_freeze_acceptance": data_snapshot_freeze_acceptance,
    "data_snapshot_freeze_unit": data_snapshot_freeze_unit,
    "cost_environment_freeze_acceptance": cost_environment_freeze_acceptance,
    "cost_environment_freeze_unit": cost_environment_freeze_unit,
    "experiment_start_lock_acceptance": experiment_start_lock_acceptance,
    "experiment_start_lock_unit": experiment_start_lock_unit,
    "deterministic_backtest_acceptance": deterministic_backtest_acceptance,
    "deterministic_backtest_unit": deterministic_backtest_unit,
    "experiment_result_acceptance": experiment_result_acceptance,
    "experiment_result_unit": experiment_result_unit,
    "experiment_retention_acceptance": experiment_retention_acceptance,
    "experiment_retention_unit": experiment_retention_unit,
    "experiment_reproducibility_acceptance": experiment_reproducibility_acceptance,
    "experiment_reproducibility_unit": experiment_reproducibility_unit,
    "experiment_http_contract_acceptance": experiment_http_contract_acceptance,
    "experiment_http_contract_unit": experiment_http_contract_unit,
    "traceability_acceptance": traceability_acceptance,
    "traceability_unit": traceability_unit,
}


if CASE_NAME not in CASES:
    raise SystemExit(f"Cas M-011 inconnu: {CASE_NAME}")

CASES[CASE_NAME]()
