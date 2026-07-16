from __future__ import annotations

from contextlib import nullcontext

class _Cursor:
    def __init__(self) -> None:
        self._rows: tuple[tuple[object, ...], ...] = ()

    def __enter__(self) -> "_Cursor":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False

    def execute(self, query: str, parameters: tuple[object, ...]) -> None:
        if "FROM source_processing.source_documents AS source" not in query:
            return
        compact_query = "".join(query.split())
        availability_is_boolean = (
            "COALESCE((conversion.document_idISNULLANDrun.status='ROUTE_PLANNED'" in compact_query
        )
        self._rows = (
            (
                "DOC-0000000000000001",
                "Document sans diagnostic",
                ("Auteur historique",),
                2026,
                "1",
                "LEGACY_DECLARED",
                "REGISTERED",
                "DIAGNOSTIC_NOT_REQUESTED",
                "CONVERSION_NOT_REQUESTED",
                None,
                None,
                None,
                False if availability_is_boolean else None,
            ),
        )

    def fetchall(self) -> tuple[tuple[object, ...], ...]:
        return self._rows


class _Connection:
    def __init__(self, cursor: _Cursor) -> None:
        self._cursor = cursor

    def __enter__(self) -> "_Connection":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False

    def transaction(self):
        return nullcontext()

    def cursor(self) -> _Cursor:
        return self._cursor


class _ConnectionFactory:
    def __init__(self) -> None:
        self.cursor = _Cursor()

    def connect(self) -> _Connection:
        return _Connection(self.cursor)


def test_validate_document_persistence_unit() -> None:
    # Given un document enregistré sans aucun run de diagnostic.
    # When la projection légère du corpus est lue depuis PostgreSQL.
    # Then la disponibilité de conversion est le booléen public False, jamais NULL.
    from app.source_processing.adapters.postgres_document_persistence import (
        PostgresDocumentPersistence,
    )

    factory = _ConnectionFactory()
    persistence = PostgresDocumentPersistence(connection_factory=factory)

    rows = persistence.list_document_status_rows(limit=1, after_document_id=None)

    assert len(rows) == 1
    assert rows[0].metadata_status == "LEGACY_DECLARED"
    assert rows[0].authors == ("Auteur historique",)
    assert rows[0].conversion_action_available is False
