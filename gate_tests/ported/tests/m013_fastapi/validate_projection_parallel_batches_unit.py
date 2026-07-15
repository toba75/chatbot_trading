from __future__ import annotations

import threading
import time

from app.knowledge_access.adapters.qdrant_vector_index import QdrantVectorIndex
from app.knowledge_access.domain.knowledge_projection import BuildFingerprint
from app.knowledge_access.domain.projection_index import (
    VectorIndexPoint,
    VectorIndexPublishRequest,
    VectorIndexSchema,
)


def test_qdrant_generation_is_published_by_parallel_batches_with_monotone_progress() -> None:
    # Given une génération de projection composée de quatre points.
    client = _BlockingQdrantClient()
    index = QdrantVectorIndex(client=client)
    progress: list[int] = []
    request = VectorIndexPublishRequest(
        collection_name="ka_parallel_projection",
        index_generation="IDX-M013-PARALLEL-BATCHES",
        schema=VectorIndexSchema(
            schema_version="qdrant-parallel-v1",
            collection_name="ka_parallel_projection",
            dense_dimensions=2,
            distance="cosine",
            payload_schema_version="payload-v1",
        ),
        build_fingerprint=BuildFingerprint("a" * 64),
        points=tuple(_point(number) for number in range(1, 5)),
        expected_point_count=4,
    )

    result_holder: dict[str, object] = {}

    def publish() -> None:
        try:
            result_holder["publication"] = index.publish_generation(
                request,
                max_parallel_batches=4,
                batch_size=1,
                on_batch_published=lambda completed: progress.append(completed),
            )
        except BaseException as exc:  # pragma: no cover - relayed to the test thread
            result_holder["error"] = exc

    worker_thread = threading.Thread(target=publish)
    worker_thread.start()
    started_count = client.wait_until_started(expected=4, timeout_seconds=1.5)
    client.release()
    worker_thread.join(timeout=5)

    if worker_thread.is_alive():
        raise AssertionError("La publication Qdrant parallèle ne s'est pas terminée.")
    if "error" in result_holder:
        raise result_holder["error"]  # type: ignore[misc]

    # When les lots sont publiés.
    # Then les upserts se chevauchent et la progression publique reste monotone.
    assert started_count == 4
    assert client.max_active >= 4
    assert progress == [1, 2, 3, 4]
    assert result_holder["publication"].published_point_count == 4  # type: ignore[attr-defined]


class _BlockingQdrantClient:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._release = threading.Event()
        self.active = 0
        self.max_active = 0
        self.started_batches = 0
        self.points: list[dict] = []

    def upsert(self, *, collection_name: str, points):
        del collection_name
        with self._lock:
            self.started_batches += 1
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            if not self._release.wait(timeout=3):
                raise RuntimeError("QDRANT_PARALLEL_RELEASE_TIMEOUT")
            with self._lock:
                self.points.extend(dict(point) for point in points)
            return object()
        finally:
            with self._lock:
                self.active -= 1

    def delete(self, *, collection_name: str, points_selector):
        del collection_name, points_selector
        return object()

    def count(self, *, collection_name: str, count_filter, exact: bool) -> int:
        del collection_name, exact
        generation = count_filter["must"][0]["match"]["value"]
        with self._lock:
            return sum(
                1
                for point in self.points
                if point["payload"]["index_generation"] == generation
            )

    def wait_until_started(self, *, expected: int, timeout_seconds: float) -> int:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            with self._lock:
                count = self.started_batches
            if count >= expected:
                return count
            time.sleep(0.01)
        with self._lock:
            return self.started_batches

    def release(self) -> None:
        self._release.set()


def _point(number: int) -> VectorIndexPoint:
    chunk_id = f"KCHK-M013-PARALLEL-{number:03d}"
    content_hash = f"{number}" * 64
    return VectorIndexPoint(
        point_id=chunk_id,
        chunk_id=chunk_id,
        content_hash=content_hash,
        dense_vector=(1.0, 0.0),
        sparse_weights=((f"token-{number}", 1.0),),
        payload={
            "chunk_id": chunk_id,
            "content_hash": content_hash,
            "projection_id": "PROJ-M013-PARALLEL",
            "document_id": "DOC-M013-PARALLEL",
        },
    )
