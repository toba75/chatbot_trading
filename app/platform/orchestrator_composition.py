from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

from fastapi import APIRouter

from app.platform.configuration import ApplicationConfiguration


ReadinessStatus = Literal["ready", "not_wired", "unavailable"]
_READINESS_STATUSES = frozenset(("ready", "not_wired", "unavailable"))


@dataclass(frozen=True, slots=True)
class DependencyReadiness:
    name: str
    status: ReadinessStatus
    error_code: str | None = None

    def __post_init__(self) -> None:
        if self.status not in _READINESS_STATUSES:
            raise ValueError(f"Statut de readiness invalide: {self.status}")
        if self.status == "ready" and self.error_code is not None:
            raise ValueError("cause de readiness interdite pour une dépendance prête")
        if self.error_code is not None and (
            not isinstance(self.error_code, str)
            or self.error_code.strip() == ""
            or self.error_code != self.error_code.strip()
        ):
            raise ValueError("error_code de readiness invalide")


class OrchestratorDependency(Protocol):
    async def open(self) -> None: ...

    async def close(self) -> None: ...

    def readiness(self) -> DependencyReadiness: ...


@dataclass(slots=True)
class OrchestratorCompositionRoot:
    configuration: ApplicationConfiguration
    dependencies: tuple[OrchestratorDependency, ...]
    document_command_router: APIRouter
    _opened: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        if not isinstance(self.configuration, ApplicationConfiguration):
            raise TypeError("configuration applicative validée obligatoire")
        if len(self.dependencies) == 0:
            raise ValueError("au moins une dépendance orchestratrice obligatoire")
        if not isinstance(self.document_command_router, APIRouter):
            raise ValueError("document_command_router invalide")

    async def open(self) -> None:
        if self._opened:
            raise RuntimeError("composition root orchestratrice déjà ouverte")
        opened_dependencies: list[OrchestratorDependency] = []
        try:
            for dependency in self.dependencies:
                await dependency.open()
                opened_dependencies.append(dependency)
        except Exception as primary_error:
            for dependency in reversed(opened_dependencies):
                try:
                    await dependency.close()
                except Exception as rollback_error:
                    primary_error.add_note(
                        "ROLLBACK_CLOSE_ERROR:"
                        f"{type(rollback_error).__name__}:{rollback_error}"
                    )
            raise
        self._opened = True

    async def close(self) -> None:
        if not self._opened:
            raise RuntimeError("composition root orchestratrice non ouverte")
        primary_error: Exception | None = None
        for dependency in reversed(self.dependencies):
            try:
                await dependency.close()
            except Exception as close_error:
                if primary_error is None:
                    primary_error = close_error
                else:
                    primary_error.add_note(
                        "ADDITIONAL_CLOSE_ERROR:"
                        f"{type(close_error).__name__}:{close_error}"
                    )
        self._opened = False
        if primary_error is not None:
            raise primary_error

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
