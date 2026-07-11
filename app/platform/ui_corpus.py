"""Premier écran UI local du corpus PDF."""

from __future__ import annotations

import html
import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.contracts.identity import DomainIdentifier


SOURCE_STATUSES = frozenset(
    {
        "SOURCE_REGISTERED",
        "DUPLICATE_SOURCE",
        "SOURCE_QUARANTINED",
        "SOURCE_UNREADABLE",
    }
)
DIAGNOSTIC_STATUSES = frozenset(
    {
        "DIAGNOSTIC_NOT_REQUESTED",
        "DIAGNOSTIC_REQUESTED",
        "ROUTE_EXPLICIT",
        "MANUAL_REVIEW",
        "SOURCE_QUARANTINED",
    }
)
CONVERSION_STATUSES = frozenset(
    {
        "CONVERSION_NOT_REQUESTED",
        "CONVERSION_REQUESTED",
        "CANONICAL_ACCEPTED",
        "SOURCE_NOT_ROUTED",
        "SOURCE_QUARANTINED",
        "SOURCE_NOT_CANONICAL",
        "PAGE_AUTHORITY_MISSING",
        "REJECTED",
    }
)
PROJECTION_STATUSES = frozenset(
    {
        "PROJECTION_NOT_REQUESTED",
        "INDEXATION_REQUESTED",
        "REQUESTED",
        "BUILDING",
        "BUILT",
        "INDEXING",
        "SEARCHABLE",
        "STALE",
        "FAILED",
        "RETIRED",
        "PROJECTION_NOT_FOUND",
        "PROJECTION_STALE",
        "SEARCH_INDEX_UNAVAILABLE",
    }
)
READ_MODEL_STATUSES = frozenset(
    {
        "READ_MODEL_READY",
        "READ_MODEL_NOT_CONNECTED",
        "READ_MODEL_UNAVAILABLE",
    }
)
_PDF_VIEWER_PATH_PATTERN = re.compile(r"^/ui/documents/(?P<document_id>[^/]+)/pdf$")
_PDF_CONTENT_PATH_PATTERN = re.compile(r"^/ui/documents/(?P<document_id>[^/]+)/pdf/content$")
_DESTRUCTIVE_FIELD_NAMES = frozenset(
    {
        "delete",
        "deleted",
        "deletion",
        "destroy",
        "purge",
        "purge_requested",
        "remove_from_corpus",
        "supprimer",
        "suppression",
    }
)
_INTERNAL_FIELD_NAMES = frozenset(
    {
        "original_storage_ref",
        "storage_path",
        "qdrant_collection",
        "qdrant_point_id",
        "postgres_table",
        "sp_table",
    }
)


@dataclass(frozen=True)
class CorpusPdfDocument:
    """Document PDF affichable par le premier écran UI."""

    document_id: str
    title: str
    source_status: str
    diagnostic_status: str
    conversion_status: str
    canonical_version_id: str | None
    projection_status: str
    selected: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "document_id", _ensure_document_id(self.document_id))
        object.__setattr__(self, "title", _ensure_text(self.title, "titre requis"))
        object.__setattr__(
            self,
            "source_status",
            _ensure_member(
                self.source_status,
                SOURCE_STATUSES,
                "statut source public invalide",
            ),
        )
        object.__setattr__(
            self,
            "diagnostic_status",
            _ensure_member(
                self.diagnostic_status,
                DIAGNOSTIC_STATUSES,
                "statut diagnostic public invalide",
            ),
        )
        object.__setattr__(
            self,
            "conversion_status",
            _ensure_member(
                self.conversion_status,
                CONVERSION_STATUSES,
                "statut conversion public invalide",
            ),
        )
        if self.canonical_version_id is not None:
            object.__setattr__(
                self,
                "canonical_version_id",
                _ensure_text(self.canonical_version_id, "canonical_version_id requis"),
            )
        object.__setattr__(
            self,
            "projection_status",
            _ensure_member(
                self.projection_status,
                PROJECTION_STATUSES,
                "statut projection public invalide",
            ),
        )
        if not isinstance(self.selected, bool):
            raise ValueError("selection document invalide")

    @property
    def selectable_for_conversation(self) -> bool:
        return self.projection_status == "SEARCHABLE"


@dataclass(frozen=True)
class CorpusPdfScreenState:
    """État public nécessaire au rendu du premier écran corpus."""

    documents: Sequence[CorpusPdfDocument]
    active_selected_document_ids: Sequence[str]
    read_model_status: str

    def __post_init__(self) -> None:
        documents = _ensure_documents(self.documents)
        active_selection = tuple(
            _ensure_document_id(document_id)
            for document_id in self.active_selected_document_ids
        )
        document_ids = {document.document_id for document in documents}
        for document_id in active_selection:
            if document_id not in document_ids:
                raise ValueError("selection active sans document public")
        object.__setattr__(self, "documents", documents)
        object.__setattr__(self, "active_selected_document_ids", active_selection)
        object.__setattr__(
            self,
            "read_model_status",
            _ensure_member(
                self.read_model_status,
                READ_MODEL_STATUSES,
                "statut read-model UI invalide",
            ),
        )


def build_unconnected_corpus_pdf_state() -> CorpusPdfScreenState:
    """Construit un état explicite quand le read-model documentaire n'est pas branché."""

    return CorpusPdfScreenState(
        documents=(),
        active_selected_document_ids=(),
        read_model_status="READ_MODEL_NOT_CONNECTED",
    )


def build_corpus_pdf_state_from_corpus_root(*, corpus_root: Path) -> CorpusPdfScreenState:
    """Construit le read-model public depuis le corpus PDF local configuré."""

    root = _ensure_corpus_root_path(corpus_root)
    if not root.is_dir():
        return CorpusPdfScreenState(
            documents=(),
            active_selected_document_ids=(),
            read_model_status="READ_MODEL_UNAVAILABLE",
        )

    documents = tuple(
        _document_from_pdf_file(pdf_path)
        for pdf_path in sorted(
            (candidate for candidate in root.iterdir() if _is_pdf_file(candidate)),
            key=lambda candidate: candidate.name.casefold(),
        )
    )
    return CorpusPdfScreenState(
        documents=documents,
        active_selected_document_ids=(),
        read_model_status="READ_MODEL_READY",
    )


def build_registration_payload(
    *,
    original_content: bytes,
    title: str,
    issuer: str,
    document_date: str,
    document_type: str,
    language: str,
) -> Mapping[str, Any]:
    """Construit le payload strict de `POST /v1/documents`."""

    if not isinstance(original_content, bytes) or len(original_content) == 0:
        raise ValueError("original_content requis")
    payload: dict[str, Any] = {
        "original_content": original_content,
        "bibliographic_metadata": {
            "title": _ensure_text(title, "title requis"),
            "issuer": _ensure_text(issuer, "issuer requis"),
            "document_date": _ensure_text(document_date, "document_date requis"),
            "document_type": _ensure_text(document_type, "document_type requis"),
            "language": _ensure_text(language, "language requis"),
        },
    }
    ensure_no_destructive_ui_fields(payload)
    return payload


def remove_from_active_selection(
    *,
    selected_document_ids: Sequence[str],
    document_id: str,
) -> tuple[str, ...]:
    """Retire un document de la sélection active sans supprimer le corpus."""

    parsed_document_id = _ensure_document_id(document_id)
    parsed_selection = tuple(_ensure_document_id(value) for value in selected_document_ids)
    if parsed_document_id not in parsed_selection:
        raise ValueError("document absent de la sélection active")
    return tuple(value for value in parsed_selection if value != parsed_document_id)


def ensure_no_destructive_ui_fields(payload: Mapping[str, Any]) -> None:
    """Refuse les champs de suppression et les champs de stockage interne."""

    _inspect_payload_fields(payload)


def render_corpus_pdf_screen(state: CorpusPdfScreenState) -> str:
    """Rend le premier écran local du corpus PDF."""

    parsed_state = _ensure_screen_state(state)
    document_rows = "\n".join(_render_document_row(document) for document in parsed_state.documents)
    if document_rows == "":
        document_rows = (
            '<tr><td colspan="7" class="empty-state">'
            "Aucun PDF public dans le read-model documentaire.</td></tr>"
        )
    return "\n".join(
        (
            "<!doctype html>",
            '<html lang="fr">',
            "<head>",
            '  <meta charset="utf-8">',
            "  <title>Corpus PDF</title>",
            "  <style>",
            "    body { font-family: Arial, sans-serif; margin: 24px; color: #1f2933; }",
            "    header, main { max-width: 1180px; margin: 0 auto; }",
            "    .status { font-weight: 700; }",
            "    table { border-collapse: collapse; width: 100%; margin-top: 16px; }",
            "    th, td { border: 1px solid #ccd3dc; padding: 8px; text-align: left; }",
            "    th { background: #eef2f6; }",
            "    form { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 16px 0; }",
            "    label { display: grid; gap: 4px; font-size: 14px; }",
            "    button, a.button { border: 1px solid #465a69; background: #f7f9fb; padding: 6px 10px; color: #1f2933; text-decoration: none; }",
            "    .empty-state { color: #52616f; }",
            "  </style>",
            "</head>",
            "<body>",
            "  <header>",
            "    <h1>Corpus PDF</h1>",
            f'    <p>Read-model documentaire: <span class="status">{_escape(parsed_state.read_model_status)}</span></p>',
            "  </header>",
            "  <main>",
            '    <section aria-labelledby="ajout-pdf">',
            '      <h2 id="ajout-pdf">Ajouter un PDF</h2>',
            '      <p>Contrat appelé: <code>POST /v1/documents</code></p>',
            '      <form method="post" action="/v1/documents" enctype="multipart/form-data">',
            '        <label>Fichier PDF original<input name="original_content" type="file" accept="application/pdf" required></label>',
            '        <label>Titre documentaire<input name="title" type="text" required></label>',
            '        <label>Émetteur ou origine<input name="issuer" type="text" required></label>',
            '        <label>Date documentaire<input name="document_date" type="text" required></label>',
            '        <label>Type documentaire<input name="document_type" type="text" required></label>',
            '        <label>Langue principale<input name="language" type="text" required></label>',
            "        <button type=\"submit\">Ajouter au corpus</button>",
            "      </form>",
            "    </section>",
            '    <section aria-labelledby="liste-pdf">',
            '      <h2 id="liste-pdf">PDF du corpus</h2>',
            "      <table>",
            "        <thead>",
            "          <tr><th>Document</th><th>Source</th><th>Diagnostic</th><th>Conversion</th><th>Projection</th><th>Sélection</th><th>PDF</th></tr>",
            "        </thead>",
            f"        <tbody>{document_rows}</tbody>",
            "      </table>",
            "    </section>",
            "  </main>",
            "</body>",
            "</html>",
        )
    )


def render_pdf_viewer(document: CorpusPdfDocument) -> str:
    """Rend un visualiseur public en lecture seule pour un PDF original."""

    parsed_document = _ensure_document(document)
    return "\n".join(
        (
            "<!doctype html>",
            '<html lang="fr">',
            "<head>",
            '  <meta charset="utf-8">',
            f"  <title>PDF original {_escape(parsed_document.document_id)}</title>",
            "</head>",
            "<body>",
            f"  <h1>PDF original {_escape(parsed_document.title)}</h1>",
            f"  <p>Identifiant public: <code>{_escape(parsed_document.document_id)}</code></p>",
            '  <p>Visualisation locale contrôlée en lecture seule.</p>',
            f'  <iframe title="PDF original" src="/ui/documents/{_escape(parsed_document.document_id)}/pdf/content"></iframe>',
            "</body>",
            "</html>",
        )
    )


def ui_get_response(
    *,
    path: str,
    state: CorpusPdfScreenState,
) -> tuple[int, str, str]:
    """Route les lectures HTML du service local `ui`."""

    parsed_path = _ensure_path(path)
    parsed_state = _ensure_screen_state(state)
    if parsed_path in {"/", "/ui", "/ui/corpus-pdf"}:
        return 200, "text/html; charset=utf-8", render_corpus_pdf_screen(parsed_state)
    match = _PDF_VIEWER_PATH_PATTERN.fullmatch(parsed_path)
    if match is not None:
        document_id = _ensure_document_id(match.group("document_id"))
        for document in parsed_state.documents:
            if document.document_id == document_id:
                return 200, "text/html; charset=utf-8", render_pdf_viewer(document)
        return 404, "text/html; charset=utf-8", _render_not_found(document_id)
    return 404, "text/html; charset=utf-8", _render_not_found(parsed_path)


def ui_get_pdf_content_response(
    *,
    path: str,
    corpus_root: Path,
) -> tuple[int, str, bytes]:
    """Retourne le contenu PDF original sans divulguer son chemin local."""

    parsed_path = _ensure_path(path)
    match = _PDF_CONTENT_PATH_PATTERN.fullmatch(parsed_path)
    if match is None:
        raise ValueError("chemin contenu PDF invalide")
    document_id = _ensure_document_id(match.group("document_id"))
    root = _ensure_corpus_root_path(corpus_root)
    if not root.is_dir():
        return 503, "text/plain; charset=utf-8", "Corpus indisponible".encode("utf-8")
    for pdf_path in sorted(
        (candidate for candidate in root.iterdir() if _is_pdf_file(candidate)),
        key=lambda candidate: candidate.name.casefold(),
    ):
        pdf_content = _read_pdf_content(pdf_path)
        if _document_id_from_pdf_content(pdf_content) == document_id:
            return 200, "application/pdf", pdf_content
    return 404, "text/plain; charset=utf-8", "PDF introuvable".encode("utf-8")


def _render_document_row(document: CorpusPdfDocument) -> str:
    selected_text = "Sélection active" if document.selected else "Hors sélection active"
    selectable = "true" if document.selectable_for_conversation else "false"
    canonical = document.canonical_version_id if document.canonical_version_id is not None else "Aucune version canonique"
    return "".join(
        (
            '<tr data-document-id="',
            _escape(document.document_id),
            '" data-selectable="',
            selectable,
            '"><td><strong>',
            _escape(document.title),
            "</strong><br><code>",
            _escape(document.document_id),
            "</code><br><span>",
            _escape(canonical),
            "</span></td><td>",
            _escape(document.source_status),
            "</td><td>",
            _escape(document.diagnostic_status),
            "</td><td>",
            _escape(document.conversion_status),
            "</td><td>",
            _escape(document.projection_status),
            "</td><td>",
            _escape(selected_text),
            '<br><button type="button" data-action="retirer_selection_active" data-document-id="',
            _escape(document.document_id),
            '">Retirer de la sélection active</button></td><td><a class="button" href="/ui/documents/',
            _escape(document.document_id),
            '/pdf">Ouvrir le PDF</a></td></tr>',
        )
    )


def _render_not_found(value: str) -> str:
    return "\n".join(
        (
            "<!doctype html>",
            '<html lang="fr">',
            "<head><meta charset=\"utf-8\"><title>Ressource UI absente</title></head>",
            "<body>",
            f"<h1>Ressource UI absente</h1><p>{_escape(value)}</p>",
            "</body>",
            "</html>",
        )
    )


def _inspect_payload_fields(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized_key = _ensure_text(str(key), "champ payload UI requis").lower()
            if normalized_key in _DESTRUCTIVE_FIELD_NAMES:
                raise ValueError("champ UI destructif interdit")
            if normalized_key in _INTERNAL_FIELD_NAMES:
                raise ValueError("champ UI interne interdit")
            _inspect_payload_fields(child)
    elif isinstance(value, (tuple, list)):
        for child in value:
            _inspect_payload_fields(child)


def _document_from_pdf_file(pdf_path: Path) -> CorpusPdfDocument:
    parsed_path = _ensure_pdf_file(pdf_path)
    pdf_content = _read_pdf_content(parsed_path)
    return CorpusPdfDocument(
        document_id=_document_id_from_pdf_content(pdf_content),
        title=_ensure_text(parsed_path.stem, "titre PDF requis"),
        source_status="SOURCE_REGISTERED",
        diagnostic_status="DIAGNOSTIC_NOT_REQUESTED",
        conversion_status="CONVERSION_NOT_REQUESTED",
        canonical_version_id=None,
        projection_status="PROJECTION_NOT_REQUESTED",
        selected=False,
    )


def _document_id_from_pdf_content(pdf_content: bytes) -> str:
    if not isinstance(pdf_content, bytes):
        raise ValueError("contenu PDF non binaire")
    if len(pdf_content) == 0:
        raise ValueError("contenu PDF vide")
    return "DOC-" + hashlib.sha256(pdf_content).hexdigest()[:16].upper()


def _read_pdf_content(pdf_path: Path) -> bytes:
    parsed_path = _ensure_pdf_file(pdf_path)
    content = parsed_path.read_bytes()
    if len(content) == 0:
        raise ValueError("PDF du corpus vide")
    return content


def _is_pdf_file(path: Path) -> bool:
    return path.is_file() and path.suffix.casefold() == ".pdf"


def _ensure_pdf_file(value: Path) -> Path:
    if not isinstance(value, Path):
        raise ValueError("chemin PDF invalide")
    path = value.resolve()
    if not path.is_file() or path.suffix.casefold() != ".pdf":
        raise ValueError("fichier PDF du corpus invalide")
    return path


def _ensure_corpus_root_path(value: Path) -> Path:
    if not isinstance(value, Path):
        raise ValueError("corpus_root invalide")
    return value.resolve()


def _ensure_documents(value: Sequence[CorpusPdfDocument]) -> tuple[CorpusPdfDocument, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError("documents UI invalides")
    documents = tuple(value)
    for document in documents:
        _ensure_document(document)
    document_ids = tuple(document.document_id for document in documents)
    if len(set(document_ids)) != len(document_ids):
        raise ValueError("document UI dupliqué")
    return documents


def _ensure_document(value: CorpusPdfDocument) -> CorpusPdfDocument:
    if not isinstance(value, CorpusPdfDocument):
        raise ValueError("document UI invalide")
    return value


def _ensure_screen_state(value: CorpusPdfScreenState) -> CorpusPdfScreenState:
    if not isinstance(value, CorpusPdfScreenState):
        raise ValueError("état écran UI invalide")
    return value


def _ensure_member(value: Any, allowed_values: frozenset[str], message: str) -> str:
    parsed_value = _ensure_text(value, message)
    if parsed_value not in allowed_values:
        raise ValueError(message)
    return parsed_value


def _ensure_text(value: Any, message: str) -> str:
    if not isinstance(value, str):
        raise ValueError(message)
    if value.strip() == "":
        raise ValueError(message)
    if value != value.strip():
        raise ValueError(message)
    return value


def _ensure_document_id(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("document_id invalide")
    try:
        return str(DomainIdentifier.parse_with_prefix(value, "DOC"))
    except ValueError as exc:
        raise ValueError("document_id invalide") from exc


def _ensure_path(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("chemin UI invalide")
    if value.strip() == "":
        raise ValueError("chemin UI vide")
    if value != value.strip() or not value.startswith("/"):
        raise ValueError("chemin UI invalide")
    return value


def _escape(value: str) -> str:
    return html.escape(value, quote=True)


__all__ = [
    "CorpusPdfDocument",
    "CorpusPdfScreenState",
    "build_registration_payload",
    "build_corpus_pdf_state_from_corpus_root",
    "build_unconnected_corpus_pdf_state",
    "ensure_no_destructive_ui_fields",
    "remove_from_active_selection",
    "render_corpus_pdf_screen",
    "render_pdf_viewer",
    "ui_get_pdf_content_response",
    "ui_get_response",
]
