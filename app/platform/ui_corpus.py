"""Premier écran UI local du corpus PDF."""

from __future__ import annotations

import html
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.contracts.identity import DomainIdentifier
from app.contracts.document_public_statuses import (
    PublicConversionStatus,
    PublicDiagnosticStatus,
    PublicProjectionStatus,
    PublicSourceStatus,
)


SOURCE_STATUSES = frozenset(status.value for status in PublicSourceStatus)
DIAGNOSTIC_STATUSES = frozenset(status.value for status in PublicDiagnosticStatus)
CONVERSION_STATUSES = frozenset(status.value for status in PublicConversionStatus)
PROJECTION_STATUSES = frozenset(
    status.value for status in PublicProjectionStatus
)
READ_MODEL_STATUSES = frozenset(
    {
        "READ_MODEL_READY",
        "READ_MODEL_UNAVAILABLE",
    }
)
_PDF_VIEWER_PATH_PATTERN = re.compile(r"^/ui/documents/(?P<document_id>[^/]+)/pdf$")
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
    conversion_action_available: bool
    selected: bool
    manual_review_reason: str | None = None
    failure_error_code: str | None = None

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
        if not isinstance(self.conversion_action_available, bool):
            raise ValueError("disponibilité conversion invalide")
        if self.conversion_action_available and (
            self.diagnostic_status != "ROUTE_PLANNED"
            or self.conversion_status != "CONVERSION_NOT_REQUESTED"
        ):
            raise ValueError("disponibilité conversion incohérente")
        if not isinstance(self.selected, bool):
            raise ValueError("selection document invalide")
        if self.diagnostic_status == "MANUAL_REVIEW":
            object.__setattr__(self, "manual_review_reason", _ensure_text(self.manual_review_reason, "motif de revue manuelle requis"))
        elif self.manual_review_reason is not None:
            object.__setattr__(self, "manual_review_reason", _ensure_text(self.manual_review_reason, "motif de revue manuelle invalide"))
        if self.diagnostic_status == "FAILED":
            object.__setattr__(self, "failure_error_code", _ensure_text(self.failure_error_code, "code d'échec requis"))
        elif self.failure_error_code is not None:
            raise ValueError("code d'échec interdit hors FAILED")

    @property
    def selectable_for_conversation(self) -> bool:
        return self.projection_status == "SEARCHABLE"


@dataclass(frozen=True)
class CorpusPdfScreenState:
    """État public nécessaire au rendu du premier écran corpus."""

    documents: Sequence[CorpusPdfDocument]
    active_selected_document_ids: Sequence[str]
    read_model_status: str
    public_error: Mapping[str, Any] | None = None
    current_cursor: str | None = None
    next_cursor: str | None = None
    registration_notice: Mapping[str, Any] | None = None

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
        if self.current_cursor is not None:
            object.__setattr__(self, "current_cursor", _ensure_document_id(self.current_cursor))
        if self.next_cursor is not None:
            object.__setattr__(self, "next_cursor", _ensure_document_id(self.next_cursor))
        if self.registration_notice is not None:
            notice = dict(self.registration_notice)
            if set(notice) != {"document_id", "duplicate"}:
                raise ValueError("confirmation d'enregistrement invalide")
            notice["document_id"] = _ensure_document_id(notice["document_id"])
            if not isinstance(notice["duplicate"], bool):
                raise ValueError("confirmation duplicate invalide")
            object.__setattr__(self, "registration_notice", notice)
        object.__setattr__(
            self,
            "read_model_status",
            _ensure_member(
                self.read_model_status,
                READ_MODEL_STATUSES,
                "statut read-model UI invalide",
            ),
        )
        if self.read_model_status == "READ_MODEL_READY":
            if self.public_error is not None:
                raise ValueError("erreur publique interdite pour un read-model prêt")
            return
        if not isinstance(self.public_error, Mapping):
            raise ValueError("erreur publique requise pour un read-model indisponible")
        error_payload = dict(self.public_error)
        ensure_no_destructive_ui_fields(error_payload)
        _ensure_text(error_payload.get("error_code"), "error_code public requis")
        object.__setattr__(self, "public_error", error_payload)


def build_unavailable_corpus_pdf_state(
    *,
    public_error: Mapping[str, Any],
) -> CorpusPdfScreenState:
    """Construit le blocage UI à partir d'une erreur réellement observée."""

    return CorpusPdfScreenState(
        documents=(),
        active_selected_document_ids=(),
        read_model_status="READ_MODEL_UNAVAILABLE",
        public_error=public_error,
    )


def build_registration_payload(
    *,
    original_content: bytes,
    title: str,
    authors: Sequence[str],
    publication_year: int,
    edition: str,
) -> Mapping[str, Any]:
    """Construit le payload strict de `POST /v1/documents`."""

    if not isinstance(original_content, bytes) or len(original_content) == 0:
        raise ValueError("original_content requis")
    payload: dict[str, Any] = {
        "original_content": original_content,
        "bibliographic_metadata": {
            "title": _ensure_text(title, "title requis"),
            "authors": _ensure_authors(authors),
            "publication_year": _ensure_publication_year(publication_year),
            "edition": _ensure_text(edition, "edition requise"),
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
    read_model_connected = parsed_state.read_model_status == "READ_MODEL_READY"
    document_rows = "\n".join(_render_document_row(document) for document in parsed_state.documents)
    if document_rows == "":
        document_rows = (
            '<tr><td colspan="7" class="empty-state">'
            "Aucun PDF public dans le read-model documentaire.</td></tr>"
        )
    blocking_notice = ""
    fieldset_attributes = ""
    if not read_model_connected:
        fieldset_attributes = ' disabled aria-disabled="true"'
        public_error = html.escape(
            str(dict(parsed_state.public_error)),
            quote=True,
        )
        blocking_notice = (
            '<div class="blocking-notice" role="status" aria-live="polite">'
            '<strong>Fonction UI non opérationnelle</strong><br>'
            f'<code>{public_error}</code></div>'
        )
    pagination = '<nav aria-label="Pagination du corpus"><a href="/ui/corpus-pdf">Retour au début</a>'
    if parsed_state.next_cursor is not None:
        pagination += (
            '<form method="get" action="/ui/corpus-pdf">'
            f'<input type="hidden" name="cursor" value="{_escape(parsed_state.next_cursor)}">'
            '<button type="submit">Page suivante</button></form>'
        )
    pagination += "</nav>"
    registration_confirmation = ""
    if parsed_state.registration_notice is not None:
        duplicate_label = "doublon existant" if parsed_state.registration_notice["duplicate"] else "nouveau document"
        registration_confirmation = (
            '<div role="status" aria-live="polite"><strong>Enregistrement confirmé</strong> : '
            f'<code>{_escape(parsed_state.registration_notice["document_id"])}</code> ({duplicate_label}).</div>'
        )
    return "\n".join(
        (
            "<!doctype html>",
            '<html lang="fr">',
            "<head>",
            '  <meta charset="utf-8">',
            '  <meta name="viewport" content="width=device-width, initial-scale=1">',
            "  <title>Corpus PDF</title>",
            "  <style>",
            "    body { font-family: Arial, sans-serif; margin: 24px; color: #1f2933; }",
            "    header, main { max-width: 1180px; margin: 0 auto; }",
            "    .status { font-weight: 700; }",
            "    table { border-collapse: collapse; width: 100%; margin-top: 16px; }",
            "    th, td { border: 1px solid #ccd3dc; padding: 8px; text-align: left; }",
            "    th { background: #eef2f6; }",
            "    .document-registration-form { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 16px 0; }",
            "    .row-action-form { display: inline-block; margin: 6px 0 0; }",
            "    fieldset { display: contents; }",
            "    fieldset:disabled { opacity: 0.6; }",
            "    label { display: grid; gap: 4px; font-size: 14px; }",
            "    button, a.button { border: 1px solid #465a69; background: #f7f9fb; padding: 6px 10px; color: #1f2933; text-decoration: none; }",
            "    .empty-state { color: #52616f; }",
            "    .blocking-notice { border-left: 4px solid #9b2c2c; background: #fff5f5; padding: 12px; margin: 16px 0; }",
            "    .table-scroll { width: 100%; overflow-x: auto; }",
            "    @media (max-width: 720px) { body { margin: 12px; } .document-registration-form { grid-template-columns: 1fr; } table { min-width: 820px; } }",
            "  </style>",
            "</head>",
            "<body>",
            "  <header>",
            "    <h1>Corpus PDF</h1>",
            f'    <p>Read-model documentaire: <span class="status">{_escape(parsed_state.read_model_status)}</span></p>',
            f"    {blocking_notice}",
            f"    {registration_confirmation}",
            "  </header>",
            "  <main>",
            '    <section aria-labelledby="ajout-pdf">',
            '      <h2 id="ajout-pdf">Ajouter un PDF</h2>',
            '      <p>Contrat appelé: <code>POST /v1/documents</code>. PDF de 50 Mio maximum.</p>',
            '      <form class="document-registration-form" method="post" action="/v1/documents" enctype="multipart/form-data">',
            f"        <fieldset{fieldset_attributes}>",
            '        <label>Fichier PDF original<input name="original_content" type="file" accept="application/pdf" required></label>',
            '        <label>Titre documentaire<input name="title" maxlength="512" type="text" required></label>',
            '        <label>Auteur<input name="authors" maxlength="256" type="text" required></label>',
            '        <label>Année de publication<input name="publication_year" type="number" min="1" required></label>',
            '        <label>Édition<input name="edition" maxlength="64" type="text" required></label>',
            "        <button type=\"submit\">Ajouter au corpus</button>",
            "        </fieldset>",
            "      </form>",
            "    </section>",
            '    <section aria-labelledby="liste-pdf">',
            '      <h2 id="liste-pdf">PDF du corpus</h2>',
            '      <div class="table-scroll"><table>',
            "        <thead>",
            "          <tr><th>Document</th><th>Source</th><th>Diagnostic</th><th>Conversion</th><th>Projection</th><th>Sélection</th><th>PDF</th></tr>",
            "        </thead>",
            f"        <tbody>{document_rows}</tbody>",
            "      </table></div>",
            f"      {pagination}",
            "    </section>",
            "  </main>",
            "</body>",
            "</html>",
        )
    )


def render_pdf_viewer(document: CorpusPdfDocument) -> str:
    """Rend un visualiseur public en lecture seule pour un PDF original."""

    parsed_document = _ensure_document(document)
    escaped_document_id = _escape(parsed_document.document_id)
    return "\n".join(
        (
            "<!doctype html>",
            '<html lang="fr">',
            "<head>",
            '  <meta charset="utf-8">',
            '  <meta name="viewport" content="width=device-width, initial-scale=1">',
            f"  <title>PDF original {escaped_document_id}</title>",
            "  <style>",
            "    html, body { height: 100%; margin: 0; color: #1f2933; font-family: Arial, sans-serif; }",
            "    body.pdf-viewer-page { min-height: 100vh; display: flex; flex-direction: column; background: #f7f9fb; }",
            "    .pdf-viewer-header { padding: 16px 24px; border-bottom: 1px solid #ccd3dc; background: #ffffff; }",
            "    .pdf-viewer-header h1 { margin: 0 0 8px; font-size: 24px; line-height: 1.25; word-break: break-word; }",
            "    .pdf-viewer-header p { margin: 4px 0; font-size: 14px; }",
            "    .pdf-viewer-main { flex: 1; min-height: 0; padding: 12px; }",
            "    .pdf-viewer-frame { display: block; width: 100%; height: calc(100vh - 132px); min-height: 640px; border: 0; background: #ffffff; }",
            "  </style>",
            "</head>",
            '<body class="pdf-viewer-page">',
            '  <header class="pdf-viewer-header">',
            f"    <h1>PDF original {_escape(parsed_document.title)}</h1>",
            f"    <p>Identifiant public: <code>{escaped_document_id}</code></p>",
            "    <p>Visualisation locale contrôlée en lecture seule.</p>",
            "  </header>",
            '  <main class="pdf-viewer-main">',
            f'    <iframe class="pdf-viewer-frame" title="PDF original" type="application/pdf" src="/ui/documents/{escaped_document_id}/pdf/content"></iframe>',
            f'    <p><a href="/ui/documents/{escaped_document_id}/pdf/content">Télécharger le PDF original</a></p>',
            "  </main>",
            "</body>",
            "</html>",
        )
    )


def render_document_inspection(
    *,
    title: str,
    response: Any,
    action_progress: Any | None,
) -> str:
    """Rend une sortie ou erreur publique déjà validée par le client UI."""

    parsed_title = _ensure_text(title, "titre inspection requis")
    status_code = getattr(response, "status_code", None)
    payload = getattr(response, "payload", None)
    if isinstance(status_code, bool) or not isinstance(status_code, int):
        raise ValueError("status_code inspection invalide")
    if not isinstance(payload, Mapping):
        raise ValueError("payload inspection invalide")
    ensure_no_destructive_ui_fields(payload)
    if status_code >= 400:
        error_code = _escape(str(payload.get("error_code")))
        field = payload.get("field")
        field_help = (
            ""
            if field is None
            else f"<p>Champ à corriger : <code>{_escape(str(field))}</code>.</p>"
        )
        feature_not_delivered = payload.get("error_code") in {
            "CONVERSION_NOT_REQUESTED",
            "PROJECTION_NOT_REQUESTED",
            "SERVICE_NOT_CONFIGURED",
        }
        guidance = (
            "<p>fonctionnalité non livrée</p>"
            if feature_not_delivered
            else "<p>Vérifiez les champs indiqués ou la disponibilité du service.</p>"
        )
        content = "".join(
            (
                '<section role="alert" aria-labelledby="erreur-documentaire">',
                '<h2 id="erreur-documentaire">Action impossible</h2>',
                f"<p>Le service a répondu avec le code <code>{error_code}</code>.</p>",
                field_help,
                guidance,
                '<p><a href="/ui/corpus-pdf">Retour au corpus</a></p>',
                "</section>",
            )
        )
    elif parsed_title.casefold() == "diagnostic":
        progress_html, refresh_html = _render_action_progress(
            action_progress,
            expected_action_name="DIAGNOSE",
        )
        pages = payload.get("pages")
        if not isinstance(pages, list):
            raise ValueError("pages diagnostic requises pour le rendu")
        page_items = "".join(
            "".join(
                (
                    f'<li><h3>Page {_escape(str(page.get("page_number")))}</h3>',
                    f'<p>Manifeste : <code>{_escape(str(page.get("manifest_status")))}</code></p>',
                    f'<section aria-label="Signaux page">{_render_mapping_details(page.get("diagnostic"))}</section>',
                    f'<section aria-label="Justification de route">{_render_mapping_details(page.get("route"))}</section></li>',
                )
            )
            for page in pages
            if isinstance(page, Mapping)
        )
        content = "".join(
            (
                '<section aria-labelledby="resume-diagnostic">',
                '<h2 id="resume-diagnostic">Résumé du diagnostic</h2>',
                progress_html,
                f'<p>Statut : <code>{_escape(str(payload.get("diagnostic_status")))}</code></p>',
                f'<p>Pages diagnostiquées : {_escape(str(payload.get("diagnosed_page_count")))} / {_escape(str(payload.get("source_page_count")))}</p>',
                f"<ol>{page_items}</ol></section>",
            )
        )
    elif parsed_title.casefold() == "conversion":
        progress_html, refresh_html = _render_action_progress(
            action_progress,
            expected_action_name="CONVERT_DOCUMENT",
        )
        canonical_version_id = payload.get("canonical_version_id")
        canonical_html = (
            "<p>Version canonique : aucune.</p>"
            if canonical_version_id is None
            else f'<p>Version canonique : <code>{_escape(str(canonical_version_id))}</code></p>'
        )
        rejection_error_code = payload.get("qa_rejection_error_code")
        rejection_html = (
            ""
            if rejection_error_code is None
            else f'<p>Erreur terminale : <code>{_escape(str(rejection_error_code))}</code></p>'
        )
        content = "".join(
            (
                '<section aria-labelledby="resume-conversion">',
                '<h2 id="resume-conversion">Résumé de la conversion</h2>',
                progress_html,
                f'<p>Statut : <code>{_escape(str(payload.get("conversion_status")))}</code></p>',
                canonical_html,
                rejection_html,
                "</section>",
            )
        )
    else:
        visible_items = _render_mapping_details(payload)
        content = "".join(
            (
                f'<section aria-labelledby="resume-{_escape(parsed_title.casefold())}">',
                f'<h2 id="resume-{_escape(parsed_title.casefold())}">Données publiques</h2>',
                f"{visible_items}</section>",
            )
        )
    return "\n".join(
        (
            "<!doctype html>",
            '<html lang="fr">',
            '<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">',
            refresh_html
            if parsed_title.casefold() in {"diagnostic", "conversion"} and status_code < 400
            else "",
            '<title>Inspection documentaire</title></head>',
            "<body>",
            f"<h1>{_escape(parsed_title)}</h1>",
            f"<p>Statut HTTP public: <code>{status_code}</code></p>",
            content,
            '<p><a href="/ui/corpus-pdf">Retour au corpus</a></p>',
            "</body>",
            "</html>",
        )
    )


def _render_action_progress(
    value: Any,
    *,
    expected_action_name: str,
) -> tuple[str, str]:
    if value is None:
        raise ValueError("progression d'action requise")
    payload = getattr(value, "payload", value)
    if isinstance(payload, Mapping):
        action_name = payload.get("action_name")
        phase = payload.get("phase")
        completed_units = payload.get("completed_units")
        total_units = payload.get("total_units")
        failure_error_code = payload.get("failure_error_code")
    else:
        action_name = getattr(payload, "action_name", None)
        phase = getattr(payload, "phase", None)
        completed_units = getattr(payload, "completed_units", None)
        total_units = getattr(payload, "total_units", None)
        failure_error_code = getattr(payload, "failure_error_code", None)
    if action_name != expected_action_name:
        raise ValueError("action de progression invalide")
    if phase not in {"NOT_REQUESTED", "QUEUED", "RUNNING", "SUCCEEDED", "FAILED"}:
        raise ValueError("phase de progression invalide")
    if isinstance(completed_units, bool) or not isinstance(completed_units, int) or completed_units < 0:
        raise ValueError("unités réalisées invalides")
    if isinstance(total_units, bool) or not isinstance(total_units, int) or total_units < 1:
        raise ValueError("total d'unités invalide")
    if completed_units > total_units:
        raise ValueError("progression supérieure au total")
    if phase == "FAILED":
        _ensure_text(failure_error_code, "code d'échec progression requis")
    elif failure_error_code is not None:
        raise ValueError("code d'échec interdit hors échec")
    refresh_html = (
        '<meta http-equiv="refresh" content="1">'
        if phase in {"QUEUED", "RUNNING"}
        else ""
    )
    failure_html = (
        ""
        if failure_error_code is None
        else f'<p>Erreur : <code>{_escape(failure_error_code)}</code></p>'
    )
    progress_percentage = completed_units * 100 // total_units
    progress_label = {
        "CONVERT_DOCUMENT": "Avancement de la conversion",
        "DIAGNOSE": "Avancement du diagnostic",
    }[action_name]
    return (
        "".join(
            (
                '<section aria-live="polite" aria-label="Progression de l’action">',
                f'<p>Action : <code>{_escape(action_name)}</code></p>',
                f'<p>Phase : <code>{_escape(phase)}</code></p>',
                f'<p>Avancement : {progress_percentage} % ({completed_units} / {total_units})</p>',
                (
                    f'<progress aria-label="{progress_label} : {progress_percentage} %" '
                    f'value="{completed_units}" max="{total_units}">{progress_percentage} %</progress>'
                ),
                failure_html,
                "</section>",
            )
        ),
        refresh_html,
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
            _render_diagnostic_cell(document),
            "</td><td>",
            _render_conversion_cell(document),
            "</td><td>",
            _escape(document.projection_status),
            '<br><a href="/ui/documents/',
            _escape(document.document_id),
            '/projection">Inspecter</a>',
            "</td><td>",
            _escape(selected_text),
            '</td><td><a class="button" href="/ui/documents/',
            _escape(document.document_id),
            '/pdf">Ouvrir le PDF</a></td></tr>',
        )
    )


def _render_diagnostic_cell(document: CorpusPdfDocument) -> str:
    parsed_document = _ensure_document(document)
    diagnostic_status = _escape(parsed_document.diagnostic_status)
    if parsed_document.diagnostic_status != "DIAGNOSTIC_NOT_REQUESTED":
        reason = parsed_document.manual_review_reason or parsed_document.failure_error_code
        reason_html = "" if reason is None else f"<br><strong>Motif :</strong> {_escape(reason)}"
        return "".join(
            (
                diagnostic_status,
                reason_html,
                '<br><a href="/ui/documents/',
                _escape(parsed_document.document_id),
                '/diagnostic">Inspecter</a>',
            )
        )
    escaped_document_id = _escape(parsed_document.document_id)
    return "".join(
        (
            diagnostic_status,
            '<form class="row-action-form" method="post" action="/v1/documents/',
            escaped_document_id,
            '/diagnose">',
            '<button type="submit">Diagnostiquer</button>',
            "</form>",
            '<br><a href="/ui/documents/',
            escaped_document_id,
            '/diagnostic">Inspecter</a>',
        )
    )


def _render_conversion_cell(document: CorpusPdfDocument) -> str:
    parsed_document = _ensure_document(document)
    escaped_document_id = _escape(parsed_document.document_id)
    action_html = (
        ""
        if not parsed_document.conversion_action_available
        else "".join(
            (
                '<form class="row-action-form" method="post" action="/v1/documents/',
                escaped_document_id,
                '/convert">',
                '<button type="submit">Convertir</button>',
                "</form>",
            )
        )
    )
    return "".join(
        (
            _escape(parsed_document.conversion_status),
            action_html,
            '<br><a href="/ui/documents/',
            escaped_document_id,
            '/conversion">Inspecter</a>',
        )
    )


def _render_not_found(value: str) -> str:
    return "\n".join(
        (
            "<!doctype html>",
            '<html lang="fr">',
            "<head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>Ressource UI absente</title></head>",
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


def _ensure_authors(value: Sequence[str]) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError("authors requis")
    authors = tuple(_ensure_text(author, "author requis") for author in value)
    if len(authors) == 0:
        raise ValueError("authors requis")
    return authors


def _ensure_publication_year(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("publication_year invalide")
    return value


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


def _inspection_state(value: Any) -> str:
    if value is None:
        return "Non disponible"
    if isinstance(value, Mapping):
        status = value.get("route_name") or value.get("page_state")
        return "Disponible" if status is None else str(status)
    if isinstance(value, list):
        return f"{len(value)} élément(s)"
    return str(value)


def _render_mapping_details(value: Any) -> str:
    """Affiche chaque preuve publique validée sans masquer les structures imbriquées."""

    if value is None:
        return "<p>Non disponible</p>"
    if isinstance(value, Mapping):
        items = "".join(
            f"<dt>{_escape(str(key))}</dt><dd>{_render_mapping_details(child)}</dd>"
            for key, child in value.items()
        )
        return f"<dl>{items}</dl>"
    if isinstance(value, list):
        items = "".join(f"<li>{_render_mapping_details(child)}</li>" for child in value)
        return f"<ol>{items}</ol>"
    return f"<code>{_escape(str(value))}</code>"


__all__ = [
    "CorpusPdfDocument",
    "CorpusPdfScreenState",
    "build_registration_payload",
    "build_unavailable_corpus_pdf_state",
    "ensure_no_destructive_ui_fields",
    "remove_from_active_selection",
    "render_corpus_pdf_screen",
    "render_document_inspection",
    "render_pdf_viewer",
    "ui_get_response",
]
