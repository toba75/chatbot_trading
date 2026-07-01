"""Application command for compact CV context snapshots."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.conversation.domain.context_snapshot import (
    CONVERSATION_CONTEXT_COMPACTION_POLICY_VERSION,
    ConversationContextCompacted,
    ConversationContextCompactionPolicy,
    ConversationContextSnapshot,
)


class ConversationContextStore(Protocol):
    """Port for storing compact context snapshots."""

    def save(self, snapshot: ConversationContextSnapshot) -> ConversationContextSnapshot:
        """Persist a compact context snapshot."""


@dataclass(frozen=True)
class CompactConversationContextCommand:
    """Command carrying explicit CV context parts to compact."""

    conversation_id: str
    active_mandate: Mapping[str, Any]
    user_preferences: Mapping[str, Any]
    selected_document_ids: Sequence[str]
    verified_answer_refs: Sequence[str]
    historical_assertions: Sequence[str]
    ambiguities: Sequence[str]
    occurred_at: str


@dataclass(frozen=True)
class CompactConversationContextResult:
    """Public application result for context compaction."""

    status: str
    snapshot: ConversationContextSnapshot
    events: tuple[ConversationContextCompacted, ...]


class CompactConversationContextHandler:
    """Use case that compacts and stores CV context."""

    def __init__(
        self,
        *,
        context_store: ConversationContextStore,
        policy: ConversationContextCompactionPolicy | None = None,
    ) -> None:
        if not callable(getattr(context_store, "save", None)):
            raise ValueError("context_store sans save")
        self._context_store = context_store
        self._policy = policy if policy is not None else ConversationContextCompactionPolicy()

    def compact(
        self,
        command: CompactConversationContextCommand,
    ) -> CompactConversationContextResult:
        if not isinstance(command, CompactConversationContextCommand):
            raise ValueError("commande CompactConversationContext invalide")
        snapshot = self._policy.compact(
            conversation_id=command.conversation_id,
            active_mandate=command.active_mandate,
            user_preferences=command.user_preferences,
            selected_document_ids=command.selected_document_ids,
            verified_answer_refs=command.verified_answer_refs,
            historical_assertions=command.historical_assertions,
            ambiguities=command.ambiguities,
            occurred_at=command.occurred_at,
        )
        saved = self._context_store.save(snapshot)
        event = ConversationContextCompacted(
            conversation_id=saved.conversation_id,
            snapshot_created_at=saved.created_at,
            verified_answer_ref_count=len(saved.verified_answer_refs),
            historical_assertion_count=len(saved.historical_assertions_to_revalidate),
            policy_version=CONVERSATION_CONTEXT_COMPACTION_POLICY_VERSION,
        )
        return CompactConversationContextResult(
            status="CONVERSATION_CONTEXT_COMPACTED",
            snapshot=saved,
            events=(event,),
        )


__all__ = [
    "CompactConversationContextCommand",
    "CompactConversationContextHandler",
    "CompactConversationContextResult",
    "ConversationContextStore",
]
