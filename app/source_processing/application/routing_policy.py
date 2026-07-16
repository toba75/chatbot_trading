"""Configuration canonique unique du routage documentaire M-003."""

from app.source_processing.domain.document_processing_run import (
    PageRoutingConfiguration,
    RoutingPolicyVersion,
)


DOCUMENT_ROUTING_POLICY_VERSION = "routing-v1"
DOCUMENT_ROUTING_AUTO_CONFIDENCE_MIN = 0.90
DOCUMENT_ROUTING_BENCHMARK_CONFIDENCE_MIN = 0.85


def build_document_routing_configuration() -> PageRoutingConfiguration:
    return PageRoutingConfiguration(
        routing_policy_version=RoutingPolicyVersion.from_value(
            DOCUMENT_ROUTING_POLICY_VERSION
        ),
        auto_confidence_min=DOCUMENT_ROUTING_AUTO_CONFIDENCE_MIN,
        benchmark_confidence_min=DOCUMENT_ROUTING_BENCHMARK_CONFIDENCE_MIN,
    )


__all__ = [
    "DOCUMENT_ROUTING_AUTO_CONFIDENCE_MIN",
    "DOCUMENT_ROUTING_BENCHMARK_CONFIDENCE_MIN",
    "DOCUMENT_ROUTING_POLICY_VERSION",
    "build_document_routing_configuration",
]
