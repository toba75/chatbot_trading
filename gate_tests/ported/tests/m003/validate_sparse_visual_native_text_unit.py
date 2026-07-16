from __future__ import annotations

from typing import Any

from app.source_processing.adapters.pdf_inspection_worker import _inspect_page
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


class _PdfObject:
    def __init__(self, value: Any) -> None:
        self._value = value

    def get_object(self) -> Any:
        return self._value


class _CaptionedChartPage:
    def __init__(self, caption: str) -> None:
        self._caption = caption
        self._resources = _PdfObject(
            {
                "/XObject": _PdfObject(
                    {
                        "/Image1": _PdfObject({"/Subtype": "/Image"}),
                        "/Image2": _PdfObject({"/Subtype": "/Image"}),
                    }
                )
            }
        )

    def get(self, key: str) -> Any:
        return self._resources if key == "/Resources" else None

    def extract_text(self, *, visitor_text: Any) -> str:
        visitor_text(self._caption)
        return self._caption


def _route_for(signals: PageDiagnosticSignals) -> tuple[PageDecisionState, PageRouteName]:
    decision = PageDiagnosticPolicy().classify(
        page_number=PageNumber.from_value(174),
        signals=signals,
        diagnostic_version=DiagnosticVersion.from_value("pypdf-isolated-v4"),
        justification="Page visuelle complexe avec couche native mesurée.",
    )
    route = PageRoutingPolicy().decide_page_route(
        page_decision=decision,
        routing_configuration=PageRoutingConfiguration(
            routing_policy_version=RoutingPolicyVersion.from_value("routing-v1"),
            auto_confidence_min=0.90,
            benchmark_confidence_min=0.85,
        ),
    )
    return decision.page_state, route.route_name


def test_sparse_native_caption_does_not_require_targeted_native_candidate() -> None:
    # Given une page de graphique complexe dont la couche native contient
    # seulement une courte légende, comme la page réelle 174.
    inspection = _inspect_page(
        174,
        _CaptionedChartPage("Figure B.2 Asset Sharpe Ratios, 1974-2012"),
        {
            "max_xobjects_per_page": 10,
            "max_text_characters_per_page": 10_000,
            "max_total_text_characters": 10_000,
        },
        [0],
    )

    # When le diagnostic mesure la fiabilité native puis décide la route.
    sparse_state, sparse_route = _route_for(
        PageDiagnosticSignals(
            native_text_state=inspection["native_text_state"],
            image_state=inspection["image_state"],
            existing_ocr_state=inspection["existing_ocr_state"],
            layout_complexity=inspection["layout_complexity"],
            corruption_state=inspection["corruption_state"],
            mixed_content_detected=inspection["mixed_content_detected"],
            has_table=inspection["has_table"],
            has_formula=inspection["has_formula"],
        )
    )

    # Then la légende est suspecte et Granite porte l'autorité visuelle ; une
    # vraie page native complexe conserve l'adjudication ciblée ADR-040.
    assert inspection["text_characters"] < 80
    assert inspection["native_text_state"] == "SUSPECT"
    assert sparse_state is PageDecisionState.SCAN_CLEAN
    assert sparse_route is PageRouteName.SCAN_GRANITE

    reliable_state, reliable_route = _route_for(
        PageDiagnosticSignals(
            native_text_state="RELIABLE",
            image_state="SCAN_CLEAN",
            existing_ocr_state="VALID",
            layout_complexity="COMPLEX",
            corruption_state="NONE",
            mixed_content_detected=True,
            has_table=True,
            has_formula=False,
        )
    )
    assert reliable_state is PageDecisionState.COMPLEX_VISUAL
    assert reliable_route is PageRouteName.TARGETED_ENRICHMENT
