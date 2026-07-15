"""Rendu HTML strict du chat documentaire local."""

from __future__ import annotations

from collections.abc import Sequence
from html import escape
import re

from app.platform.ui_conversation_api import (
    UiConversationTurn,
    UiConversationView,
)


_BOLD_MARKDOWN_PATTERN = re.compile(r"\*\*(?P<content>[^*\n]+)\*\*")
_DOCUMENT_SELECTION_SCRIPT = """<script>
(() => {
  const form = document.querySelector('form[data-document-selection-required="true"]');
  const submit = form.querySelector('button[type="submit"]');
  const documents = Array.from(form.querySelectorAll('input[name="selected_documents"]'));
  const synchronize = () => {
    const selectionPresent = documents.some((document) => document.checked);
    submit.disabled = !selectionPresent;
    submit.setAttribute('aria-disabled', String(!selectionPresent));
  };
  documents.forEach((document) => document.addEventListener('change', synchronize));
  synchronize();
})();
</script>"""
_CHAT_STYLE = """<style>
:root { color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, sans-serif; color: #10233d; background: #f3f6fa; }
* { box-sizing: border-box; }
body { margin: 0; background: #f3f6fa; }
.chat-shell { width: min(1120px, calc(100% - 2rem)); margin: 2rem auto; padding: 2rem; background: #fff; border: 1px solid #d7e0eb; border-radius: 18px; box-shadow: 0 14px 40px rgba(16, 35, 61, .08); }
h1, h2, h3, h4 { line-height: 1.2; }
h1 { margin-top: 0; font-size: clamp(2rem, 5vw, 3.5rem); }
code { overflow-wrap: anywhere; color: #153f6b; }
.chat-history { display: grid; gap: 1.25rem; margin: 2rem 0; }
.chat-turn { min-width: 0; padding: 1.25rem; border: 1px solid #d7e0eb; border-radius: 14px; background: #f9fbfd; }
.chat-answer { min-width: 0; margin-top: 1rem; padding: 1.25rem; border-left: 5px solid #2367a6; background: #eef6ff; border-radius: 10px; }
.answer-text { line-height: 1.65; overflow-wrap: anywhere; }
.citations { max-height: 24rem; overflow: auto; padding-right: .75rem; }
.citations li { margin-bottom: .55rem; overflow-wrap: anywhere; }
.chat-form { display: grid; gap: 1rem; margin-top: 2rem; padding-top: 1.5rem; border-top: 1px solid #d7e0eb; }
label { display: grid; gap: .4rem; font-weight: 650; }
input, select, textarea, button { width: 100%; font: inherit; }
input, select, textarea { padding: .75rem; border: 1px solid #9eb0c4; border-radius: 8px; background: #fff; }
textarea { min-height: 8rem; resize: vertical; }
fieldset { display: grid; gap: .75rem; min-width: 0; border: 1px solid #c8d4e1; border-radius: 10px; }
fieldset label { grid-template-columns: auto minmax(0, 1fr); align-items: start; font-weight: 500; }
fieldset input { width: auto; margin-top: .2rem; }
button { padding: .85rem 1rem; border: 0; border-radius: 9px; background: #153f6b; color: #fff; font-weight: 750; cursor: pointer; }
button:hover { background: #0e3156; }
@media (max-width: 640px) { .chat-shell { width: 100%; margin: 0; padding: 1rem; border: 0; border-radius: 0; box-shadow: none; } .chat-turn, .chat-answer { padding: 1rem; } }
</style>"""


def render_new_conversation_page(
    *,
    selectable_documents: Sequence[tuple[str, str]],
    error_code: str | None = None,
) -> str:
    """Affiche les choix explicites nécessaires avant toute conversation."""

    error = "" if error_code is None else _error_notice(error_code)
    selectable = _selectable_documents(selectable_documents)
    return "\n".join(
        (
            "<!doctype html>",
            '<html lang="fr"><head><meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>Nouvelle conversation documentaire</title>{_CHAT_STYLE}</head><body>",
            '<main class="chat-shell">',
            "<h1>Chat documentaire</h1>",
            error,
            '<form class="chat-form" method="post" action="/ui/conversations">',
            '<label>Titre<input name="title" required maxlength="160"></label>',
            '<label>Univers autorisé<input name="allowed_universe" required maxlength="500"></label>',
            '<label>Langue<select name="language" required><option value="">Choisir</option><option value="fr">Français</option><option value="en">Anglais</option></select></label>',
            '<label>Niveau de détail<select name="detail_level" required><option value="">Choisir</option><option value="synthétique">Synthétique</option><option value="détaillé">Détaillé</option></select></label>',
            '<label>Format de réponse<select name="format" required><option value="">Choisir</option><option value="texte">Texte</option><option value="puces">Puces</option></select></label>',
            '<label>Style de citation<select name="citation_style" required><option value="">Choisir</option><option value="page">Page et document</option></select></label>',
            "<p>Les documents seront sélectionnés au moment de la question. Seuls les documents SEARCHABLE y seront proposés.</p>",
            selectable,
            '<button type="submit">Ouvrir la conversation</button></form>',
            '<p><a href="/ui/corpus-pdf">Retour au corpus</a></p>',
            "</main></body></html>",
        )
    )


def render_conversation_page(
    *,
    conversation: UiConversationView,
    turns: Sequence[UiConversationTurn],
    selectable_documents: Sequence[tuple[str, str]],
    error_code: str | None = None,
    error_field: str | None = None,
    draft_message: str | None = None,
) -> str:
    """Affiche une réponse CV publique et le formulaire du tour suivant."""

    if not isinstance(conversation, UiConversationView):
        raise ValueError("conversation UI invalide")
    history = tuple(turns)
    if any(not isinstance(turn, UiConversationTurn) for turn in history):
        raise ValueError("historique conversationnel UI invalide")
    if any(turn.conversation_id != conversation.conversation_id for turn in history):
        raise ValueError("historique conversationnel UI incohérent")
    if error_code is None and error_field is not None:
        raise ValueError("champ d'erreur sans code public")
    if draft_message is not None and (
        not isinstance(draft_message, str)
        or draft_message.strip() == ""
        or draft_message != draft_message.strip()
    ):
        raise ValueError("brouillon conversationnel invalide")
    document_choices = _selectable_documents(selectable_documents, checkbox=True)
    history_html = _render_history(history)
    error = "" if error_code is None else _error_notice(error_code, field=error_field)
    draft = "" if draft_message is None else escape(draft_message)
    return "\n".join(
        (
            "<!doctype html>",
            '<html lang="fr"><head><meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>Conversation documentaire</title>{_CHAT_STYLE}</head><body>",
            '<main class="chat-shell">',
            "<h1>Chat documentaire</h1>",
            f"<p>Conversation : <code>{escape(conversation.conversation_id)}</code> — {escape(conversation.title)}</p>",
            f"<p>Statut : <code>{escape(conversation.status)}</code></p>",
            error,
            history_html,
            f'<form class="chat-form" data-document-selection-required="true" method="post" action="/ui/conversations/{escape(conversation.conversation_id)}/messages">',
            f'<label>Question autonome<textarea name="message" required maxlength="8000">{draft}</textarea></label>',
            '<input type="hidden" name="requested_mode" value="CHAT_DOCUMENTAIRE">',
            '<fieldset><legend>Documents SEARCHABLE à interroger</legend>',
            '<p id="document-selection-help">Sélectionnez au moins un document SEARCHABLE pour rendre l’envoi disponible. La sélection doit être confirmée à chaque tour.</p>',
            document_choices,
            "</fieldset>",
            '<button type="submit" disabled aria-disabled="true">Envoyer la question</button></form>',
            _DOCUMENT_SELECTION_SCRIPT,
            '<p><a href="/ui/corpus-pdf">Retour au corpus</a></p>',
            "</main></body></html>",
        )
    )


def _render_history(turns: tuple[UiConversationTurn, ...]) -> str:
    if len(turns) == 0:
        return (
            '<section class="chat-history" aria-labelledby="historique-conversationnel">'
            '<h2 id="historique-conversationnel">Historique</h2>'
            "<p>Aucun tour.</p></section>"
        )
    articles = "".join(_render_turn(turn) for turn in turns)
    return (
        '<section class="chat-history" aria-labelledby="historique-conversationnel">'
        '<h2 id="historique-conversationnel">Historique</h2>'
        f"{articles}</section>"
    )


def _render_turn(turn: UiConversationTurn) -> str:
    presentation = "" if turn.presentation is None else _render_answer(turn)
    return "".join(
        (
            '<article class="chat-turn">',
            f"<h3>Tour {turn.sequence}</h3>",
            f"<p>Question utilisateur : {escape(turn.message)}</p>",
            presentation,
            "</article>",
        )
    )


def _render_answer(turn: UiConversationTurn) -> str:
    answer = turn.presentation
    if answer is None:
        raise ValueError("présentation conversationnelle UI absente")
    citations = "".join(
        "".join(
            (
                "<li>",
                f'<code>{escape(citation.citation_id)}</code> — ',
                f'Document <code>{escape(str(citation.source_locator["document_id"]))}</code>, ',
                f'page {escape(str(citation.source_locator["page_pdf"]))}, ',
                f'<a href="/ui/documents/{escape(str(citation.source_locator["document_id"]))}/pdf">ouvrir le PDF</a>',
                "</li>",
            )
        )
        for citation in answer.citations
    )
    gaps = "" if len(answer.knowledge_gaps) == 0 else f"<pre>{escape(str(answer.knowledge_gaps))}</pre>"
    conflicts = "" if len(answer.unresolved_conflicts) == 0 else f"<pre>{escape(str(answer.unresolved_conflicts))}</pre>"
    return "".join(
        (
            '<section class="chat-answer" aria-label="Réponse conversationnelle">',
            '<h4>Réponse conversationnelle</h4>',
            f'<p>Tour : <code>{escape(answer.turn_id)}</code></p>',
            f'<p>Question résolue : {escape(answer.resolved_question)}</p>',
            f'<p>Mode : <code>{escape(answer.mode)}</code></p>',
            f'<p>Justification : {escape(answer.mode_justification)}</p>',
            f'<p>Statut documentaire : <code>{escape(answer.support_status)}</code></p>',
            f'<p class="answer-text">Réponse : {_format_answer_text(answer.answer_text)}</p>',
            f'<p>Réponse vérifiée : <code>{escape(answer.verified_answer_ref)}</code></p>',
            f'<h3>Citations</h3><ol class="citations">{citations}</ol>',
            f"<h3>Lacunes documentaires</h3>{gaps}",
            f"<h3>Conflits non résolus</h3>{conflicts}",
            "</section>",
        )
    )


def _format_answer_text(value: str) -> str:
    escaped = escape(value)
    with_bold = _BOLD_MARKDOWN_PATTERN.sub(r"<strong>\g<content></strong>", escaped)
    return with_bold.replace(" * ", "<br>• ")


def _selectable_documents(
    documents: Sequence[tuple[str, str]],
    *,
    checkbox: bool = False,
) -> str:
    choices = tuple(documents)
    if len(choices) == 0:
        return '<p role="alert">Aucun document SEARCHABLE n’est disponible pour le chat.</p>'
    rendered: list[str] = []
    for document_id, title in choices:
        if not isinstance(document_id, str) or not document_id.startswith("DOC-"):
            raise ValueError("document sélectionnable invalide")
        if not isinstance(title, str) or title.strip() == "":
            raise ValueError("titre sélectionnable invalide")
        if checkbox:
            rendered.append(
                f'<label><input type="checkbox" name="selected_documents" value="{escape(document_id)}">'
                f"{escape(title)} <code>{escape(document_id)}</code></label>"
            )
        else:
            rendered.append(f"<p>{escape(title)} <code>{escape(document_id)}</code></p>")
    return "".join(rendered)


def _error_notice(error_code: str, *, field: str | None = None) -> str:
    if not isinstance(error_code, str) or error_code.strip() == "":
        raise ValueError("error_code UI invalide")
    if field is not None and (
        not isinstance(field, str) or field.strip() == "" or field != field.strip()
    ):
        raise ValueError("champ d'erreur UI invalide")
    field_notice = (
        ""
        if field is None
        else f"<p>Champ à corriger : <code>{escape(field)}</code>.</p>"
    )
    return (
        '<section role="alert"><h2>Action impossible</h2>'
        f'<p>Le service a répondu avec le code <code>{escape(error_code)}</code>.</p>'
        f"{field_notice}</section>"
    )


__all__ = ["render_conversation_page", "render_new_conversation_page"]
