"""Acceptation BDD T-005 du fan-out sans exécution de convertisseur."""

from __future__ import annotations

from validate_page_fan_out_unit import (
    _FanOutRepository,
    _handler,
    _parent_job,
    _planned_run,
    _source,
    _source_artifact,
)


def test_convert_document_eclate_quatre_pages_sans_convertir() -> None:
    # Given un traitement routé de quatre pages, dont une SKIP_EMPTY.
    source = _source()
    run = _planned_run(source)
    repository = _FanOutRepository()

    # When CONVERT_DOCUMENT active explicitement le fan-out puis est rejoué.
    first = _handler(run, repository).handle(
        parent_job=_parent_job(source, run),
        source_artifact=_source_artifact(source),
        trace_id="TRACE-M014-FANOUT-UNIT",
    )
    replay = _handler(run, repository).handle(
        parent_job=_parent_job(source, run),
        source_artifact=_source_artifact(source),
        trace_id="TRACE-M014-FANOUT-UNIT",
    )

    # Then un résultat vide et trois enveloppes identiques existent, sans
    # convertisseur dans le cas d'usage ni succès public inventé.
    assert first.created is True
    assert replay.created is False
    assert first.total_units == 4
    assert first.completed_units == 1
    assert first.page_job_count == 3
    assert not hasattr(first, "canonical_version_id")
    assert repository.plan is not None
    assert not hasattr(repository.plan, "converter")
