from __future__ import annotations

from app.platform.ui_corpus import render_document_inspection


def test_given_a_running_projection_when_the_public_inspection_is_rendered_then_the_ui_displays_percentage_and_progress_bar() -> None:
    """Given-When-Then : l'UI rend uniquement la progression publique KA."""

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
