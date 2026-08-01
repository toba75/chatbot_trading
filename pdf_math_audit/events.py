from typing import Any, Callable


ProgressCallback = Callable[[dict[str, Any]], None]


def progress_event(phase: str, completed: int, total: int) -> dict[str, Any]:
    return {
        "type": "progress",
        "phase": phase,
        "completed_units": completed,
        "total_units": total,
    }
