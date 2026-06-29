"""Collecteur mémoire explicite des métriques runtime KA."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeMetricRecord:
    """Mesure runtime KA enregistrée par les doubles de tests."""

    metric_name: str
    value: float
    labels: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "metric_name", _ensure_text(self.metric_name, "metric_name"))
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise ValueError("metric_value invalide")
        object.__setattr__(self, "value", float(self.value))
        object.__setattr__(self, "labels", _ensure_labels(self.labels))


class InMemoryKnowledgeAccessMetrics:
    """Collecteur mémoire strict pour vérifier les métriques runtime KA."""

    def __init__(self) -> None:
        self._records: list[RuntimeMetricRecord] = []

    def increment(self, metric_name: str, *, labels: dict[str, str]) -> None:
        self._records.append(
            RuntimeMetricRecord(metric_name=metric_name, value=1.0, labels=labels)
        )

    def observe(self, metric_name: str, value: float, *, labels: dict[str, str]) -> None:
        self._records.append(
            RuntimeMetricRecord(metric_name=metric_name, value=value, labels=labels)
        )

    def records(self) -> tuple[RuntimeMetricRecord, ...]:
        return tuple(self._records)

    def values_for(self, metric_name: str) -> tuple[RuntimeMetricRecord, ...]:
        parsed_metric_name = _ensure_text(metric_name, "metric_name")
        return tuple(record for record in self._records if record.metric_name == parsed_metric_name)


def _ensure_labels(value: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError("labels non objet")
    labels = {}
    for key, item in value.items():
        labels[_ensure_text(key, "label_key")] = _ensure_text(item, "label_value")
    return labels


def _ensure_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


__all__ = ["InMemoryKnowledgeAccessMetrics", "RuntimeMetricRecord"]
