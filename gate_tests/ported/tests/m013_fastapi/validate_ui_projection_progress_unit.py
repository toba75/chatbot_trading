from __future__ import annotations

import pytest

from app.platform.ui_corpus import render_document_inspection


def test_given_public_projection_states_when_inspection_is_rendered_then_the_ui_displays_strict_progress() -> None:
    """Given-When-Then : l'UI rend les progressions publiques KA strictes."""

    html = render_document_inspection(
        title="Projection",
        response=type(
            "ProjectionResponse",
            (),
            {
                "status_code": 200,
                "payload": {
                    "document_id": "DOC-M013-UI-PROJECTION",
                    "projection_status": "INDEXING",
                    "chunk_count": 0,
                },
            },
        )(),
        action_progress={
            "action_name": "PROJECT_DOCUMENT",
            "phase": "RUNNING",
            "completed_units": 50,
            "total_units": 200,
            "failure_error_code": None,
        },
    )

    assert "Avancement : 25 % (50 / 200)" in html
    assert '<progress aria-label="Avancement de la projection : 25 %" value="50" max="200">25 %</progress>' in html
    assert 'http-equiv="refresh" content="1"' in html
    response = type(
        "ProjectionResponse",
        (),
        {
            "status_code": 200,
            "payload": {
                "document_id": "DOC-M014-UI-AUTOMATIC-WAIT",
                "projection_status": "PROJECTION_NOT_REQUESTED",
            },
        },
    )()
    not_requested = {
        "action_name": "PROJECT_DOCUMENT",
        "phase": "NOT_REQUESTED",
        "completed_units": 0,
        "total_units": None,
        "failure_error_code": None,
    }

    html = render_document_inspection(
        title="Projection",
        response=response,
        action_progress=not_requested,
    )

    assert "Projection automatique en attente" in html
    assert "publication canonique" in html
    assert 'http-equiv="refresh" content="1"' in html
    assert "<progress" not in html

    invalid_partial_states = (
        {**not_requested, "completed_units": 1},
        {**not_requested, "completed_units": False},
        {**not_requested, "completed_units": 0.0},
        {**not_requested, "total_units": 1},
        {**not_requested, "failure_error_code": "PROJECTION_FAILURE"},
    )
    for invalid_state in invalid_partial_states:
        with pytest.raises(ValueError, match="progression NOT_REQUESTED invalide"):
            render_document_inspection(
                title="Projection",
                response=response,
                action_progress=invalid_state,
            )
