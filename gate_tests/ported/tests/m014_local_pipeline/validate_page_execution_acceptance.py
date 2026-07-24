"""Acceptation BDD T-006 du résultat de page fenced et rejouable."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.platform.job_runtime.page_completion import (
    ClaimedPageCompletion,
    InMemoryPageCompletionOutbox,
    PageCompletionRelay,
)
from app.source_processing.application.record_page_completion import (
    InMemoryPageResultRepository,
    RecordPageCompletionHandler,
)
from app.source_processing.domain.distribution_contracts import DistributionContractError
from validate_page_execution_unit import (
    _claimed,
    _granite_lease,
    _handler_for,
    _page_jobs,
)


def test_deux_workers_reprise_et_redelivrance_ne_comptent_qu_une_fois(capsys) -> None:
    # Given deux workers ont calculé une page standard et une page Granite,
    # puis la lease du premier détenteur Granite est devenue obsolète.
    content = b"%PDF-1.7\nM014 fan-out unit\n%%EOF\n"
    standard_request, granite_request, _ = _page_jobs()
    standard = _claimed(standard_request, job_number=71, owner="worker-documents-a")
    expired = _claimed(granite_request, job_number=72, owner="worker-documents-a")
    resumed = _claimed(granite_request, job_number=72, owner="worker-documents-b")
    resumed = replace(
        resumed,
        claim_generation=2,
        claim_token="00000000-0000-4000-8000-000000000072",
        execution_attempts=2,
    )
    executor, _, _, standard_completion, granite_completion = _handler_for(content)

    standard_outcome = executor.execute_standard(standard)
    granite_outcome = executor.execute_granite(_granite_lease(resumed))
    assert standard_completion.calls and granite_completion.calls

    # When les deux enveloppes sont livrées à SP, puis la seconde est redélivrée.
    outbox = InMemoryPageCompletionOutbox.from_envelopes(
        (
            (standard, None, standard_outcome.envelope),
            (resumed, _granite_lease(resumed), granite_outcome.envelope),
        )
    )
    repository = InMemoryPageResultRepository(total_units=4, completed_units=1)
    relay = PageCompletionRelay(
        outbox=outbox,
        consumer=RecordPageCompletionHandler(repository=repository),
    )
    assert relay.relay_pending(
        limit=2,
        owner_id="relay-pages-a",
        lease_seconds=30,
    ) == 2
    replay_claim = outbox.replay(granite_outcome.envelope.completion_id)
    assert isinstance(replay_claim, ClaimedPageCompletion)
    assert relay.relay_claim(replay_claim) is False

    # Then chaque page existe une fois, la progression est bornée et l'ancien
    # détenteur ou une divergence ne peut ajouter aucun effet.
    assert repository.completed_units == 3
    assert repository.result_count == 2
    with pytest.raises(DistributionContractError, match="PAGE_RESULT_REPLAY_DIVERGENCE"):
        relay.relay_claim(
            outbox.divergent_replay(
                granite_outcome.envelope.completion_id,
                claim_token=expired.claim_token,
            )
        )
    assert repository.completed_units == 3
    assert repository.result_count == 2
    observations = capsys.readouterr().out
    for marker in (
        '"event_type": "page_completion_relay"',
        '"correlation_id": "TRACE-M014-PAGE-72"',
        '"error_code": "PAGE_RESULT_REPLAY_DIVERGENCE"',
        '"success_count": 1',
    ):
        assert marker in observations
    assert "claim_token" not in observations
    assert '"payload"' not in observations
