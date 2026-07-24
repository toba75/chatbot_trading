"""Tests unitaires du protocole de bascule et rollback M14-core."""

from __future__ import annotations

from collections import deque

import pytest

from app.platform.distribution_operations import (
    DistributionCoreController,
    DistributionDrainInventory,
    DistributionReleaseIdentity,
    DistributionRollbackInventory,
)


class _Operations:
    def __init__(self) -> None:
        self.calls: list[object] = []
        self.drain_inventories = deque(
            (
                DistributionDrainInventory(
                    technical_jobs=0,
                    source_processing_outbox=1,
                    knowledge_access_outbox=0,
                ),
                DistributionDrainInventory(
                    technical_jobs=0,
                    source_processing_outbox=0,
                    knowledge_access_outbox=0,
                ),
            )
        )
        self.ready_counts = deque((2, 1, 2))
        self.rollback_inventories = deque(
            (
                DistributionRollbackInventory(active_jobs=1, active_slots=1),
                DistributionRollbackInventory(active_jobs=0, active_slots=0),
            )
        )

    def close_public(self) -> None:
        self.calls.append("close_public")

    def read_drain_inventory(self, configuration_hash: str) -> DistributionDrainInventory:
        self.calls.append(("read_drain_inventory", configuration_hash))
        return self.drain_inventories.popleft()

    def start_internal(self, release: DistributionReleaseIdentity) -> None:
        self.calls.append(("start_internal", release))

    def live_ready_worker_count(self, configuration_hash: str) -> int:
        self.calls.append(("live_ready_worker_count", configuration_hash))
        return self.ready_counts.popleft()

    def activate_public(self, release: DistributionReleaseIdentity) -> None:
        self.calls.append(("activate_public", release))

    def begin_draining(self, configuration_hash: str, deadline_seconds: int) -> None:
        self.calls.append(("begin_draining", configuration_hash, deadline_seconds))

    def read_rollback_inventory(self, configuration_hash: str) -> DistributionRollbackInventory:
        self.calls.append(("read_rollback_inventory", configuration_hash))
        return self.rollback_inventories.popleft()

    def verify_schema_022_retained(self) -> None:
        self.calls.append("verify_schema_022_retained")

    def stop_internal(self) -> None:
        self.calls.append("stop_internal")

    def verify_release(self, release: DistributionReleaseIdentity) -> None:
        self.calls.append(("verify_release", release))


def test_bascule_deux_phases_et_rollback_restent_fermes_en_cas_dechec() -> None:
    # Given une release courante, une précédente et une outbox SP sans job relayé.
    current = DistributionReleaseIdentity(
        revision="a" * 40,
        schema_version="022",
        configuration_hash="b" * 64,
    )
    previous = DistributionReleaseIdentity(
        revision="c" * 40,
        schema_version="022",
        configuration_hash="d" * 64,
    )
    operations = _Operations()
    controller = DistributionCoreController(
        operations=operations,
        sleep=lambda _: operations.calls.append("wait"),
    )

    # When la préparation est demandée, l'inventaire complet atteint zéro avant
    # le démarrage interne et aucune admission publique n'est ouverte.
    controller.prepare(
        current=current,
        previous_configuration_hash="e" * 64,
        timeout_seconds=30,
        poll_seconds=1,
    )
    assert operations.calls[:5] == [
        "close_public",
        ("read_drain_inventory", "e" * 64),
        "wait",
        ("read_drain_inventory", "e" * 64),
        ("start_internal", current),
    ]
    assert ("activate_public", current) not in operations.calls

    # Then l'activation exige exactement deux présences READY vivantes ; tout
    # échec referme explicitement le port public.
    with pytest.raises(ValueError, match="DISTRIBUTION_READY_WORKERS_INVALID"):
        controller.activate(current=current)
    assert operations.calls[-1] == "close_public"

    controller.rollback(
        current=current,
        previous=previous,
        drain_deadline_seconds=30,
        timeout_seconds=30,
        poll_seconds=1,
    )
    rollback_tail = operations.calls[-11:]
    assert rollback_tail == [
        "close_public",
        ("begin_draining", current.configuration_hash, 30),
        ("read_rollback_inventory", current.configuration_hash),
        "wait",
        ("read_rollback_inventory", current.configuration_hash),
        "verify_schema_022_retained",
        "stop_internal",
        ("start_internal", previous),
        ("live_ready_worker_count", previous.configuration_hash),
        ("verify_release", previous),
        ("activate_public", previous),
    ]
