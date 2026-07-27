"""Récupération KA réelle pour les réponses conversationnelles documentaires."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.contracts.documentary_evidence import DocumentaryEvidence
from app.knowledge_access.adapters.postgres_projection_read import PostgresProjectionReadRepository
from app.knowledge_access.adapters.projection_runtime import ProjectionRuntimeService
from app.knowledge_access.application.chunk_canonical_source import (
    ProjectCanonicalChunksCommand,
    ProjectCanonicalChunksHandler,
)
from app.knowledge_access.domain.chunking import ChunkingProfile
from app.knowledge_access.domain.knowledge_projection import ProjectionStatus


_TOKEN_PATTERN = re.compile(r"[\w'-]+", re.UNICODE)
_CHUNK_CANDIDATE_MULTIPLIER = 8


@dataclass(frozen=True, slots=True)
class SearchableProjection:
    document_id: str
    projection_id: str
    canonical_version_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "document_id", _identifier(self.document_id, "DOC", "document_id"))
        object.__setattr__(self, "projection_id", _identifier(self.projection_id, "PROJ", "projection_id"))
        object.__setattr__(self, "canonical_version_id", _identifier(self.canonical_version_id, "CVER", "canonical_version_id"))


@dataclass(frozen=True, slots=True)
class DocumentaryChunk:
    chunk_id: str
    chunk_level: str
    text: str
    source_locators: tuple[Mapping[str, Any], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "chunk_id", _identifier(self.chunk_id, "KCHK", "chunk_id"))
        if self.chunk_level not in {"PARENT", "CHILD"}:
            raise ValueError("chunk_level invalide")
        object.__setattr__(self, "text", _text(self.text, "chunk_text"))
        object.__setattr__(self, "source_locators", _source_locators(self.source_locators))


class ProjectionReader(Protocol):
    def find_searchable_projection(self, document_id: str) -> SearchableProjection: ...


class CanonicalChunkReader(Protocol):
    def chunks_for_canonical_version(self, canonical_version_id: str) -> tuple[DocumentaryChunk, ...]: ...


class ProjectionChunkSelector(Protocol):
    def select_chunk_ids(self, *, projection_id: str, question: str, limit: int) -> tuple[str, ...]: ...


class LiveDocumentaryRetrievalError(ValueError):
    def __init__(self, error_code: str) -> None:
        self.error_code = _error_code(error_code)
        super().__init__(self.error_code)


class DocumentaryProjectionRetriever:
    """Joint explicitement index KA et artefact canonique, sans source alternative."""

    def __init__(
        self,
        *,
        projection_reader: ProjectionReader,
        canonical_reader: CanonicalChunkReader,
        chunk_selector: ProjectionChunkSelector,
        result_limit: int,
    ) -> None:
        if not callable(getattr(projection_reader, "find_searchable_projection", None)):
            raise ValueError("projection_reader invalide")
        if not callable(getattr(canonical_reader, "chunks_for_canonical_version", None)):
            raise ValueError("canonical_reader invalide")
        if not callable(getattr(chunk_selector, "select_chunk_ids", None)):
            raise ValueError("chunk_selector invalide")
        if isinstance(result_limit, bool) or not isinstance(result_limit, int) or result_limit < 1:
            raise ValueError("result_limit invalide")
        self._projection_reader = projection_reader
        self._canonical_reader = canonical_reader
        self._chunk_selector = chunk_selector
        self._result_limit = result_limit

    def retrieve(
        self,
        *,
        question: str,
        selected_document_ids: tuple[str, ...],
    ) -> tuple[DocumentaryEvidence, ...]:
        parsed_question = _text(question, "question")
        documents = tuple(_identifier(value, "DOC", "selected_document_ids") for value in selected_document_ids)
        if len(documents) == 0 or len(documents) != len(set(documents)):
            raise ValueError("selected_document_ids invalides")
        evidence: list[DocumentaryEvidence] = []
        for document_id in documents:
            projection = self._projection_reader.find_searchable_projection(document_id)
            if not isinstance(projection, SearchableProjection) or projection.document_id != document_id:
                raise ValueError("projection searchable invalide")
            chunks = self._canonical_reader.chunks_for_canonical_version(projection.canonical_version_id)
            if not isinstance(chunks, tuple) or any(not isinstance(chunk, DocumentaryChunk) for chunk in chunks):
                raise ValueError("chunks canoniques invalides")
            chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}
            selected_chunk_ids = self._chunk_selector.select_chunk_ids(
                projection_id=projection.projection_id,
                question=parsed_question,
                limit=self._result_limit * _CHUNK_CANDIDATE_MULTIPLIER,
            )
            if isinstance(selected_chunk_ids, (str, bytes)) or not isinstance(selected_chunk_ids, Sequence):
                raise ValueError("résultats index invalides")
            selected_child_count = 0
            for chunk_id in selected_chunk_ids:
                parsed_chunk_id = _identifier(chunk_id, "KCHK", "chunk_id")
                chunk = chunks_by_id.get(parsed_chunk_id)
                if chunk is None:
                    raise LiveDocumentaryRetrievalError("INDEX_CHUNK_UNRESOLVABLE")
                if chunk.chunk_level == "PARENT":
                    continue
                if any(
                    locator["document_id"] != document_id
                    or locator["canonical_version_id"] != projection.canonical_version_id
                    for locator in chunk.source_locators
                ):
                    raise LiveDocumentaryRetrievalError("INDEX_SOURCE_LOCATOR_INCOHERENT")
                evidence.append(
                    DocumentaryEvidence(
                        excerpt=chunk.text,
                        source_locators=chunk.source_locators,
                    )
                )
                selected_child_count += 1
                if selected_child_count == self._result_limit:
                    break
            if selected_child_count == 0:
                raise LiveDocumentaryRetrievalError("DOCUMENTARY_CHILD_EVIDENCE_NOT_FOUND")
        return tuple(evidence)


class PostgresSearchableProjectionReader:
    """Lit le statut KA durable : le navigateur ne décide jamais SEARCHABLE."""

    def __init__(self, *, projection_read_repository: PostgresProjectionReadRepository) -> None:
        if not callable(getattr(projection_read_repository, "current_projection_for_document_id", None)):
            raise ValueError("projection_read_repository invalide")
        self._projection_read_repository = projection_read_repository

    def find_searchable_projection(self, document_id: str) -> SearchableProjection:
        parsed_document_id = _identifier(document_id, "DOC", "document_id")
        record = self._projection_read_repository.current_projection_for_document_id(
            parsed_document_id,
            sample_limit=1,
        )
        if record is None or record.projection.status is not ProjectionStatus.SEARCHABLE:
            raise LiveDocumentaryRetrievalError("DOCUMENT_NOT_SEARCHABLE")
        projection = record.projection
        return SearchableProjection(
            document_id=projection.document_id,
            projection_id=projection.projection_id,
            canonical_version_id=projection.canonical_version_id,
        )


class CanonicalProjectionChunkReader:
    """Reconstruit les chunks exacts depuis l'artefact canonique publié."""

    def __init__(self, *, projection_runtime: ProjectionRuntimeService) -> None:
        if not callable(getattr(projection_runtime, "find_chunking_source_by_version_id", None)):
            raise ValueError("projection_runtime invalide")
        self._projection_runtime = projection_runtime

    def chunks_for_canonical_version(self, canonical_version_id: str) -> tuple[DocumentaryChunk, ...]:
        parsed_version_id = _identifier(canonical_version_id, "CVER", "canonical_version_id")
        projection = ProjectCanonicalChunksHandler(
            canonical_source_reader=self._projection_runtime,
        ).project_from_canonical_version(
            ProjectCanonicalChunksCommand(
                canonical_version_id=parsed_version_id,
                chunking_profile=ChunkingProfile(
                    profile_id="hierarchical-pagewise-v1",
                    profile_version="hierarchical-v1",
                    max_parent_items=64,
                    max_child_items=16,
                    max_child_characters=4000,
                ),
            )
        )
        chunks: list[DocumentaryChunk] = []
        for chunk in projection.chunks:
            chunks.append(
                DocumentaryChunk(
                    chunk_id=chunk.chunk_id,
                    chunk_level=chunk.chunk_level,
                    text=chunk.text,
                    source_locators=tuple(
                        locator.to_payload() for locator in chunk.source_locators
                    ),
                )
            )
        return tuple(chunks)


class QdrantSparseChunkSelector:
    """Interroge la projection Qdrant réelle avec le profil sparse publié."""

    def __init__(
        self,
        *,
        qdrant_url: str,
        collection_name: str,
        timeout_seconds: int,
        api_key: str,
    ) -> None:
        if not isinstance(qdrant_url, str) or qdrant_url.strip() == "" or qdrant_url != qdrant_url.strip():
            raise ValueError("qdrant_url invalide")
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or timeout_seconds < 1:
            raise ValueError("qdrant_timeout invalide")
        if not isinstance(collection_name, str) or re.fullmatch(r"[a-z0-9]+(?:[-_][a-z0-9]+)*", collection_name) is None:
            raise ValueError("qdrant_collection_name invalide")
        if not isinstance(api_key, str) or len(api_key.encode("utf-8")) < 32:
            raise ValueError("qdrant_api_key invalide")
        self._qdrant_url = qdrant_url.rstrip("/")
        self._collection_name = collection_name
        self._timeout_seconds = timeout_seconds
        self._api_key = api_key

    def select_chunk_ids(self, *, projection_id: str, question: str, limit: int) -> tuple[str, ...]:
        parsed_projection_id = _identifier(projection_id, "PROJ", "projection_id")
        parsed_question = _text(question, "question")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit invalide")
        weights = _sparse_query(parsed_question)
        payload = {
            "query": {
                "indices": list(weights.keys()),
                "values": list(weights.values()),
            },
            "using": "sparse",
            "limit": limit,
            "with_payload": True,
            "filter": {
                "must": [
                    {"key": "projection_id", "match": {"value": parsed_projection_id}},
                ]
            },
        }
        request = Request(
            f"{self._qdrant_url}/collections/{self._collection_name}/points/query",
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={"api-key": self._api_key, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, OSError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LiveDocumentaryRetrievalError("QDRANT_QUERY_FAILED") from exc
        try:
            points = response_payload["result"]["points"]
        except (KeyError, TypeError) as exc:
            raise LiveDocumentaryRetrievalError("QDRANT_RESPONSE_INVALID") from exc
        if not isinstance(points, list):
            raise LiveDocumentaryRetrievalError("QDRANT_RESPONSE_INVALID")
        chunk_ids: list[str] = []
        for point in points:
            if not isinstance(point, Mapping) or not isinstance(point.get("payload"), Mapping):
                raise LiveDocumentaryRetrievalError("QDRANT_RESPONSE_INVALID")
            chunk_ids.append(_identifier(point["payload"].get("chunk_id"), "KCHK", "chunk_id"))
        if len(chunk_ids) != len(set(chunk_ids)):
            raise LiveDocumentaryRetrievalError("QDRANT_RESPONSE_INVALID")
        return tuple(chunk_ids)


def _sparse_query(question: str) -> dict[int, float]:
    counts = Counter(token.casefold() for token in _TOKEN_PATTERN.findall(question))
    if len(counts) == 0:
        raise ValueError("question sans token")
    weights: dict[int, float] = {}
    for token, count in sorted(counts.items()):
        index = int.from_bytes(hashlib.sha256(token.encode("utf-8")).digest()[:4], "big")
        weights[index] = weights.get(index, 0.0) + float(count)
    return weights


def _source_locator(value: object) -> Mapping[str, Any]:
    locator = dict(_mapping(value, "source_locator"))
    if set(locator) != {
        "schema_version", "canonical_version_id", "document_id", "page_pdf", "item_id", "bbox", "content_hash"
    }:
        raise ValueError("source_locator invalide")
    _text(locator["schema_version"], "schema_version")
    _identifier(locator["canonical_version_id"], "CVER", "canonical_version_id")
    _identifier(locator["document_id"], "DOC", "document_id")
    if isinstance(locator["page_pdf"], bool) or not isinstance(locator["page_pdf"], int) or locator["page_pdf"] < 1:
        raise ValueError("page_pdf invalide")
    _text(locator["item_id"], "item_id")
    bbox = locator["bbox"]
    if isinstance(bbox, (str, bytes)) or not isinstance(bbox, Sequence) or len(bbox) != 4:
        raise ValueError("bbox invalide")
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in bbox):
        raise ValueError("bbox invalide")
    _hash(locator["content_hash"], "content_hash")
    locator["bbox"] = tuple(bbox)
    return locator


def _source_locators(value: object) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError("source_locators invalides")
    locators = tuple(_source_locator(locator) for locator in value)
    if len(locators) == 0:
        raise ValueError("source_locators absents")
    identities = tuple(
        (locator["canonical_version_id"], locator["document_id"], locator["item_id"])
        for locator in locators
    )
    if len(identities) != len(set(identities)):
        raise ValueError("source_locators dupliqués")
    return locators


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} non objet")
    return value


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(f"{name} invalide")
    return value


def _identifier(value: object, prefix: str, name: str) -> str:
    text = _text(value, name)
    if not text.startswith(f"{prefix}-"):
        raise ValueError(f"{name} invalide")
    return text


def _hash(value: object, name: str) -> str:
    text = _text(value, name)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{name} invalide")
    return text


def _error_code(value: object) -> str:
    text = _text(value, "error_code")
    if any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for character in text):
        raise ValueError("error_code invalide")
    return text


__all__ = [
    "CanonicalProjectionChunkReader",
    "DocumentaryChunk",
    "DocumentaryProjectionRetriever",
    "LiveDocumentaryRetrievalError",
    "PostgresSearchableProjectionReader",
    "QdrantSparseChunkSelector",
    "SearchableProjection",
]
