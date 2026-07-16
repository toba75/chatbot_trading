from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from app.source_processing.application.concurrency_limited_page_converter import (
    SharedPageConversionCapacity,
)


def test_docling_standard_and_granite_share_the_same_bounded_capacity() -> None:
    # Given huit pages sont orchestrées entre Docling standard et Granite.
    probe = _SharedCapacityProbe()
    capacity = SharedPageConversionCapacity(max_concurrency=2)
    native_converter = capacity.limit(page_converter=_ProbeConverter(probe, "native"))
    granite_converter = capacity.limit(page_converter=_ProbeConverter(probe, "granite"))

    # When les huit conversions tentent de démarrer simultanément.
    converters = tuple(
        native_converter if index % 2 == 0 else granite_converter
        for index in range(8)
    )
    with ThreadPoolExecutor(max_workers=8) as executor:
        outputs = tuple(
            executor.map(
                lambda pair: pair[1].convert_page(pair[0]),
                enumerate(converters),
            )
        )

    # Then huit pages terminent, mais jamais plus de deux processus Docling,
    # toutes variantes confondues, ne se chevauchent.
    assert outputs == tuple(range(8))
    assert probe.call_count_by_kind == {"native": 4, "granite": 4}
    assert probe.max_active == 2


class _SharedCapacityProbe:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.active = 0
        self.max_active = 0
        self.call_count_by_kind = {"native": 0, "granite": 0}


class _ProbeConverter:
    def __init__(self, probe: _SharedCapacityProbe, kind: str) -> None:
        self._probe = probe
        self._kind = kind

    def convert_page(self, request: int) -> int:
        with self._probe.lock:
            self._probe.call_count_by_kind[self._kind] += 1
            self._probe.active += 1
            self._probe.max_active = max(self._probe.max_active, self._probe.active)
        try:
            time.sleep(0.03)
            return request
        finally:
            with self._probe.lock:
                self._probe.active -= 1
