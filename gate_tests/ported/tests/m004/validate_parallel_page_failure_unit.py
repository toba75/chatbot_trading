from __future__ import annotations

import threading
import time

from app.source_processing.application.convert_routed_pages import (
    ConvertRoutedPagesCommand,
    ConvertRoutedPagesHandler,
)
from app.source_processing.domain.page_conversion import PageConversionArtifact
from validate_parallel_page_conversion_unit import (
    _UnusedConverter,
    _UnusedPreprocessor,
    _page_output,
    _planned_native_run,
    _registered_source,
)


def test_parallel_page_conversion_does_not_start_the_rest_of_document_after_failure() -> None:
    # Given douze pages natives et une capacité pagewise de quatre, dont la
    # troisième conversion échoue immédiatement.
    source_document = _registered_source()
    processing_run = _planned_native_run(source_document, page_count=12)
    native_converter = _FailingBoundedConverter()
    handler = ConvertRoutedPagesHandler(
        native_converter=native_converter,
        granite_converter=_UnusedConverter(),
        ocrmypdf_preprocessor=_UnusedPreprocessor(),
        max_parallel_pages=4,
    )

    # When l’erreur de la page 3 est observée.
    try:
        handler.handle(
            ConvertRoutedPagesCommand(
                source_document=source_document,
                processing_run=processing_run,
                canonical_version_id="CVER-M004-PARALLEL-FAILURE",
            )
        )
    except RuntimeError as error:
        assert str(error) == "DOCLING_STANDARD_UNAVAILABLE"
    else:
        raise AssertionError("L’échec parallèle attendu est absent.")

    # Then seules les quatre futures initiales ont pu démarrer ; les huit pages
    # suivantes n’ont pas été lancées après une erreur déjà connue.
    assert sorted(native_converter.started_pages) == [1, 2, 3, 4]


class _FailingBoundedConverter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.started_pages: list[int] = []

    def convert_page(self, request) -> PageConversionArtifact:
        with self._lock:
            self.started_pages.append(request.page_number.value)
        if request.page_number.value == 3:
            raise RuntimeError("DOCLING_STANDARD_UNAVAILABLE")
        time.sleep(0.08)
        return _page_output(request)
