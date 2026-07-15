"""Rendu HTML strict du chat documentaire local."""

from __future__ import annotations

from collections.abc import Sequence
from html import escape

from app.platform.ui_conversation_api import (
    UiConversationTurn,
    UiConversationView,
)


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
            "<title>Nouvelle conversation documentaire</title></head><body>",
            "<main>",
            "<h1>Chat documentaire</h1>",
            error,
            '<form method="post" action="/ui/conversations">',
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
) -> str:
    """Affiche une réponse CV publique et le formulaire du tour suivant."""

    if not isinstance(conversation, UiConversationView):
        raise ValueError("conversation UI invalide")
    history = tuple(turns)
    if any(not isinstance(turn, UiConversationTurn) for turn in history):
        raise ValueError("historique conversationnel UI invalide")
    if any(turn.conversation_id != conversation.conversation_id for turn in history):
        raise ValueError("historique conversationnel UI incohérent")
    document_choices = _selectable_documents(selectable_documents, checkbox=True)
    history_html = _render_history(history)
    error = "" if error_code is None else _error_notice(error_code)
    return "\n".join(
        (
            "<!doctype html>",
            '<html lang="fr"><head><meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>Conversation documentaire</title></head><body>",
            "<main>",
            "<h1>Chat documentaire</h1>",
            f"<p>Conversation : <code>{escape(conversation.conversation_id)}</code> — {escape(conversation.title)}</p>",
            f"<p>Statut : <code>{escape(conversation.status)}</code></p>",
            error,
            history_html,
            f'<form method="post" action="/ui/conversations/{escape(conversation.conversation_id)}/messages">',
            '<label>Question autonome<textarea name="message" required maxlength="8000"></textarea></label>',
            '<input type="hidden" name="requested_mode" value="CHAT_DOCUMENTAIRE">',
            '<fieldset><legend>Documents SEARCHABLE à interroger</legend>',
            document_choices,
            "</fieldset>",
            '<button type="submit">Envoyer la question</button></form>',
            '<p><a href="/ui/corpus-pdf">Retour au corpus</a></p>',
            "</main></body></html>",
        )
    )


def _render_history(turns: tuple[UiConversationTurn, ...]) -> str:
    if len(turns) == 0:
        return (
            '<section aria-labelledby="historique-conversationnel">'
            '<h2 id="historique-conversationnel">Historique</h2>'
            "<p>Aucun tour.</p></section>"
        )
    articles = "".join(_render_turn(turn) for turn in turns)
    return (
        '<section aria-labelledby="historique-conversationnel">'
        '<h2 id="historique-conversationnel">Historique</h2>'
        f"{articles}</section>"
    )


def _render_turn(turn: UiConversationTurn) -> str:
    presentation = "" if turn.presentation is None else _render_answer(turn)
    return "".join(
        (
            "<article>",
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
            '<section aria-label="Réponse conversationnelle">',
            '<h4>Réponse conversationnelle</h4>',
            f'<p>Tour : <code>{escape(answer.turn_id)}</code></p>',
            f'<p>Question résolue : {escape(answer.resolved_question)}</p>',
            f'<p>Mode : <code>{escape(answer.mode)}</code></p>',
            f'<p>Justification : {escape(answer.mode_justification)}</p>',
            f'<p>Statut documentaire : <code>{escape(answer.support_status)}</code></p>',
            f'<p>Réponse : {escape(answer.answer_text)}</p>',
            f'<p>Réponse vérifiée : <code>{escape(answer.verified_answer_ref)}</code></p>',
            f"<h3>Citations</h3><ol>{citations}</ol>",
            f"<h3>Lacunes documentaires</h3>{gaps}",
            f"<h3>Conflits non résolus</h3>{conflicts}",
            "</section>",
        )
    )


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


def _error_notice(error_code: str) -> str:
    if not isinstance(error_code, str) or error_code.strip() == "":
        raise ValueError("error_code UI invalide")
    return f'<section role="alert"><h2>Action impossible</h2><p><code>{escape(error_code)}</code></p></section>'


__all__ = ["render_conversation_page", "render_new_conversation_page"]
