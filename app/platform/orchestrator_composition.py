from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

from app.platform.configuration import ApplicationConfiguration


ReadinessStatus = Literal["ready", "not_wired", "unavailable"]
_READINESS_STATUSES = frozenset(("ready", "not_wired", "unavailable"))


@dataclass(frozen=True, slots=True)
class DependencyReadiness:
    name: str
    status: ReadinessStatus

    def __post_init__(self) -> None:
        if self.status not in _READINESS_STATUSES:
            raise ValueError(f"Statut de readiness invalide: {self.status}")


class OrchestratorDependency(Protocol):
    async def open(self) -> None: ...

    async def close(self) -> None: ...

    def readiness(self) -> DependencyReadiness: ...


@dataclass(slots=True)
class OrchestratorCompositionRoot:
    configuration: ApplicationConfiguration
    dependencies: tuple[OrchestratorDependency, ...]
    _opened: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        if not isinstance(self.configuration, ApplicationConfiguration):
            raise TypeError("configuration applicative validée obligatoire")
        if len(self.dependencies) == 0:
            raise ValueError("au moins une dépendance orchestratrice obligatoire")

    async def open(self) -> None:
        if self._opened:
            raise RuntimeError("composition root orchestratrice déjà ouverte")
        for dependency in self.dependencies:
            await dependency.open()
        self._opened = True

    async def close(self) -> None:
        if not self._opened:
            raise RuntimeError("composition root orchestratrice non ouverte")
        for dependency in reversed(self.dependencies):
            await dependency.close()
        self._opened = False

    def readiness_snapshot(self) -> tuple[DependencyReadiness, ...]:
        if not self._opened:
            raise RuntimeError("readiness demandée hors lifespan")
        return tuple(dependency.readiness() for dependency in self.dependencies)


__all__ = [
    "DependencyReadiness",
    "OrchestratorCompositionRoot",
    "OrchestratorDependency",
    "ReadinessStatus",
]
