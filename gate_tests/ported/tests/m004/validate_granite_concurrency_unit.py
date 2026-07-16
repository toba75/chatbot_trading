from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from app.source_processing.application.concurrency_limited_page_converter import (
    ConcurrencyLimitedPageConverter,
)


def test_granite_capacity_is_shared_and_bounded_inside_pagewise_parallelism() -> None:
    # Given huit pages sont orchestrées mais Granite a une capacité calibrée à deux.
    probe = _CapacityProbeConverter()
    converter = ConcurrencyLimitedPageConverter(
        page_converter=probe,
        max_concurrency=2,
    )

    # When huit appels de pages concurrentes partagent le même convertisseur borné.
    with ThreadPoolExecutor(max_workers=8) as executor:
        outputs = tuple(executor.map(converter.convert_page, range(8)))

    # Then toutes les pages terminent mais jamais plus de deux appels Granite
    # ne se chevauchent.
    assert outputs == tuple(range(8))
    assert probe.call_count == 8
    assert probe.max_active == 2


class _CapacityProbeConverter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.call_count = 0
        self.active = 0
        self.max_active = 0

    def convert_page(self, request: int) -> int:
        with self._lock:
            self.call_count += 1
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            time.sleep(0.03)
            return request
        finally:
            with self._lock:
                self.active -= 1
