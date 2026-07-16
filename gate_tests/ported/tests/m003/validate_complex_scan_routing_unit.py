from __future__ import annotations

from app.source_processing.domain.document_processing_run import (
    DiagnosticVersion,
    PageDecisionState,
    PageDiagnosticPolicy,
    PageDiagnosticSignals,
    PageNumber,
    PageRouteName,
    PageRoutingConfiguration,
    PageRoutingPolicy,
    RoutingPolicyVersion,
)


def test_complex_clean_scan_without_native_text_uses_granite_scan_route() -> None:
    # Given une page visuellement complexe, sans texte natif, mais contenant un
    # scan propre exploitable par le chemin visuel.
    decision = PageDiagnosticPolicy().classify(
        page_number=PageNumber.from_value(166),
        signals=PageDiagnosticSignals(
            native_text_state="ABSENT",
            image_state="SCAN_CLEAN",
            existing_ocr_state="NONE",
            layout_complexity="COMPLEX",
            corruption_state="NONE",
            mixed_content_detected=False,
            has_table=False,
            has_formula=False,
        ),
        diagnostic_version=DiagnosticVersion.from_value("pypdf-isolated-v4"),
        justification="Scan propre complexe sans couche textuelle native.",
    )

    # When la route documentaire est décidée.
    route = PageRoutingPolicy().decide_page_route(
        page_decision=decision,
        routing_configuration=PageRoutingConfiguration(
            routing_policy_version=RoutingPolicyVersion.from_value("routing-v1"),
            auto_confidence_min=0.90,
            benchmark_confidence_min=0.85,
        ),
    )

    # Then aucun candidat Docling standard absent n’est exigé : la page suit la
    # route Granite puis, uniquement si nécessaire, son fallback Gemma explicite.
    assert decision.page_state is PageDecisionState.SCAN_CLEAN
    assert route.route_name is PageRouteName.SCAN_GRANITE
