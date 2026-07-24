"""Régressions M-014 : lectures uniques et ressources bornées."""

from __future__ import annotations

import hashlib
import threading
import time
from pathlib import Path

from app.source_processing.adapters import distributed_page_conversion
from app.source_processing.adapters import local_page_artifacts
from app.source_processing.adapters.docling_native_conversion import (
    NativeDoclingConversionResponse,
    NativeDoclingPage,
    NativeDoclingPageItem,
)
from app.source_processing.adapters.local_page_artifacts import LocalPageArtifactStore
from app.source_processing.application.convert_routed_pages import PageConversionRequest
from app.source_processing.application.routed_document_conversion_worker import (
    NativePageConverter,
)
from app.source_processing.domain.distribution_contracts import (
    LocalArtifactDescriptor,
    LocalArtifactIdentity,
    PageGpuMetrics,
)
from app.source_processing.domain.document_processing_run import (
    PageNumber,
    PageRouteName,
    ProcessingRunId,
    RoutingPolicyVersion,
)
from app.source_processing.domain.source_document import DocumentId


def test_lecture_artefact_retourne_le_contenu_verifie_sans_second_parcours(
    tmp_path: Path,
    monkeypatch,
) -> None:
    content = b"artefact de page verifie une seule fois"
    identity = LocalArtifactIdentity(
        environment="test",
        artifact_ref="artifact:source_processing.local/test/pages/page-001.json",
        relative_path="pages/page-001.json",
    )
    path = identity.resolve_under(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(content)
    descriptor = LocalArtifactDescriptor(
        identity=identity,
        sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
    )
    monkeypatch.setattr(
        local_page_artifacts,
        "_hash_file",
        lambda _path: (_ for _ in ()).throw(AssertionError("second parcours interdit")),
    )

    assert LocalPageArtifactStore(profile_root=tmp_path).read(descriptor) == content


class _NativeConverterSpy:
    def __init__(self) -> None:
        self.source_sha256: str | None = None

    def convert(self, request):
        self.source_sha256 = request.source_sha256
        return NativeDoclingConversionResponse(
            tool_version="docling-m014-bounds-v1",
            pages=(
                NativeDoclingPage(
                    page_number=1,
                    items=(
                        NativeDoclingPageItem(
                            text="Page bornée.",
                            bbox=(0.1, 0.1, 0.9, 0.2),
                            provenance={"page": 1},
                        ),
                    ),
                ),
            ),
        )


def test_conversion_page_reutilise_le_hash_deja_verifie(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7\npage bornee\n%%EOF\n")
    source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    request = PageConversionRequest(
        processing_run_id=ProcessingRunId.from_value("RUN-M014-BOUNDS"),
        document_id=DocumentId.from_value("DOC-M014-BOUNDS"),
        page_number=PageNumber.from_value(1),
        route_name=PageRouteName.NATIVE_STANDARD,
        routing_policy_version=RoutingPolicyVersion.from_value("routing-m014-bounds-v1"),
        source_artifact_ref="artifact:source_processing.originals/source.pdf",
        source_sha256=source_sha256,
        expected_output_artifact_ref=(
            "artifact:source_processing.page_conversion/"
            "RUN-M014-BOUNDS/page-001.json"
        ),
    )
    converter = _NativeConverterSpy()

    NativePageConverter(
        converter=converter,
        resolve_source_path=lambda _artifact_ref: source,
    ).convert_page(request)

    assert converter.source_sha256 == source_sha256


def test_echantillonneur_conserve_le_pic_transitoire_et_termine_son_thread() -> None:
    sampler_type = getattr(distributed_page_conversion, "_ResourcePeakSampler")
    samples = iter((100, 400, 150, 150, 150))
    lock = threading.Lock()

    def ram_sample() -> int:
        with lock:
            return next(samples, 150)

    sampler = sampler_type(
        ram_sampler=ram_sample,
        gpu_sampler=None,
        sample_interval_seconds=0.001,
    )
    started = time.perf_counter()
    sampler.start()
    time.sleep(0.01)
    metrics = sampler.stop(started=started)

    assert metrics.peak_ram_bytes == 400
    assert metrics.peak_ram_bytes > ram_sample()
    assert sampler.is_running is False


def test_echantillonneur_propage_erreur_gpu_et_nettoie_son_thread() -> None:
    sampler_type = getattr(distributed_page_conversion, "_ResourcePeakSampler")
    gpu_calls = 0

    def gpu_sample() -> PageGpuMetrics:
        nonlocal gpu_calls
        gpu_calls += 1
        if gpu_calls > 1:
            raise RuntimeError("GRANITE_CUDA_UNAVAILABLE")
        return PageGpuMetrics(
            peak_vram_bytes=1024,
            peak_utilization_percent=25.0,
            peak_power_watts=35.0,
        )

    sampler = sampler_type(
        ram_sampler=lambda: 256,
        gpu_sampler=gpu_sample,
        sample_interval_seconds=0.001,
    )
    sampler.start()
    deadline = time.monotonic() + 1
    while sampler.is_running and time.monotonic() < deadline:
        time.sleep(0.001)

    try:
        sampler.stop(started=time.perf_counter() - 0.01)
    except RuntimeError as error:
        assert str(error) == "GRANITE_CUDA_UNAVAILABLE"
    else:
        raise AssertionError("erreur GPU explicite attendue")
    assert sampler.is_running is False


def test_ram_agrege_processus_worker_et_enfants(monkeypatch) -> None:
    class Process:
        def __init__(self, rss: int, children=()) -> None:
            self._rss = rss
            self._children = tuple(children)

        def memory_info(self):
            return type("Memory", (), {"rss": self._rss})()

        def children(self, *, recursive: bool):
            assert recursive is True
            return self._children

    root = Process(100, children=(Process(200), Process(300)))
    monkeypatch.setattr(distributed_page_conversion.psutil, "Process", lambda: root)

    assert distributed_page_conversion._process_tree_rss() == 600
