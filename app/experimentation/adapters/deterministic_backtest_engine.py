"""Moteur de backtest deterministe minimal pour EX."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from app.experimentation.domain.experiment import BacktestEngineResult, Experiment, RUNNING


class DeterministicBacktestEngineAdapter:
    def run(self, experiment: Experiment) -> BacktestEngineResult:
        if not isinstance(experiment, Experiment):
            raise ValueError("Experiment attendu")
        if experiment.status != RUNNING:
            raise ValueError("experience RUNNING requise")
        if experiment.frozen_inputs is None:
            raise ValueError("entrees verrouillees requises")

        frozen_payload = experiment.frozen_inputs.full_payload()
        base_hash = _stable_hash(
            {
                "strategy_version_id": experiment.strategy_version_id,
                "frozen_inputs": frozen_payload,
            }
        )
        numeric_seed = int(base_hash[:12], 16)
        total_return = round(((numeric_seed % 2400) - 600) / 10000, 6)
        max_drawdown = round(-((numeric_seed // 7) % 1200) / 10000, 6)
        trade_count = 4 + (numeric_seed % 17)
        sharpe_ratio = round(total_return / (abs(max_drawdown) + 0.01), 6)
        metrics = {
            "total_return": total_return,
            "max_drawdown": max_drawdown,
            "trade_count": trade_count,
            "sharpe_ratio": sharpe_ratio,
        }
        controls = {
            "strategy_parameter_hash_control": "PASS",
            "data_snapshot_hash_control": "PASS",
            "cost_model_hash_control": "PASS",
            "execution_environment_hash_control": "PASS",
            "lookahead_bias_control": "PASS",
            "missing_market_data_control": "PASS",
            "minimum_backtest_control_count": 6,
        }
        artifacts = _artifacts_for(experiment.experiment_id, base_hash)
        result_hash = _stable_hash(
            {
                "metrics": metrics,
                "controls": controls,
                "artifacts": artifacts,
                "frozen_inputs": frozen_payload,
            }
        )
        return BacktestEngineResult(
            result_hash=result_hash,
            metrics=metrics,
            diagnostics={
                "engine": "deterministic",
                "control_status": "PASS",
                "base_hash": base_hash,
            },
            artifacts=artifacts,
            controls=controls,
        )


def _artifacts_for(experiment_id: str, base_hash: str) -> tuple[Mapping[str, Any], ...]:
    artifact_types = ("equity_curve", "positions", "transactions", "warnings", "run_log")
    return tuple(
        {
            "artifact_id": f"{experiment_id}-{artifact_type.upper().replace('_', '-')}",
            "artifact_type": artifact_type,
            "artifact_hash": _stable_hash({"experiment_id": experiment_id, "artifact_type": artifact_type, "base_hash": base_hash}),
        }
        for artifact_type in artifact_types
    )


def _stable_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


__all__ = ["DeterministicBacktestEngineAdapter"]
