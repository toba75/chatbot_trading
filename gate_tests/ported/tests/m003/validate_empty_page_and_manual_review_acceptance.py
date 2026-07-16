from __future__ import annotations

from pathlib import Path
import sys


def test_validate_empty_page_and_manual_review_acceptance() -> None:
    repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    sys.path.insert(0, str(repository_root))

    from app.source_processing.application.resolve_manual_review import (
        ResolveManualReviewCommand,
        ResolveManualReviewHandler,
    )
    from app.source_processing.domain.document_processing_run import (
        DiagnosticVersion,
        DocumentProcessingRun,
        DocumentProcessingRunStatus,
        ManualReviewDecisionType,
        NativeTextSignal,
        PageCorruptionSignal,
        PageDecision,
        PageDiagnosticSignals,
        PageImageSignal,
        PageManifest,
        PageManifestEntry,
        PageManifestEntryState,
        PageNumber,
        PageRouteName,
        PageRoutingConfiguration,
        ProcessingRunId,
        RouteDecisionMode,
        RoutingPolicyVersion,
    )
    from app.source_processing.domain.source_document import (
        DocumentId,
        OriginalStorageRef,
        SourceDocument,
        SourceFingerprint,
    )

    class Repository:
        def __init__(self, run: DocumentProcessingRun) -> None:
            self.run = run
            self.transitions: list[tuple[str, str]] = []

        def find_by_document_id(self, document_id: DocumentId) -> DocumentProcessingRun | None:
            return self.run if self.run.document_id == document_id else None

        def save_transition(
            self,
            processing_run: DocumentProcessingRun,
            *,
            expected_status: DocumentProcessingRunStatus,
        ) -> None:
            self.transitions.append((expected_status.value, processing_run.status.value))
            self.run = processing_run

    def source() -> SourceDocument:
        fingerprint = SourceFingerprint.from_content(b"%PDF-1.7\nempty-review\n%%EOF")
        document_id = DocumentId.from_fingerprint(fingerprint)
        return SourceDocument.register_original(
            document_id=document_id,
            fingerprint=fingerprint,
            original_storage_ref=OriginalStorageRef.from_value(
                f"artifact:source_processing.original_sources/{document_id.value}/{fingerprint.value}.pdf"
            ),
            metadata=None,
        )

    def signals(*, empty: bool = False, corrupt: bool = False) -> PageDiagnosticSignals:
        return PageDiagnosticSignals(
            native_text_state=NativeTextSignal.ABSENT if empty or corrupt else NativeTextSignal.RELIABLE,
            image_state=PageImageSignal.NONE,
            existing_ocr_state="NONE",
            layout_complexity="SIMPLE",
            corruption_state=PageCorruptionSignal.CORRUPT if corrupt else PageCorruptionSignal.NONE,
            mixed_content_detected=False,
            has_table=False,
            has_formula=False,
        )

    def diagnosed_run(*, middle_empty: bool, middle_corrupt: bool, run_id: str) -> DocumentProcessingRun:
        document = source()
        manifest = PageManifest.from_entries(
            source_page_count=3,
            entries=tuple(
                PageManifestEntry(
                    page_number=PageNumber.from_value(page_number),
                    state=(
                        PageManifestEntryState.EMPTY
                        if page_number == 2 and middle_empty
                        else PageManifestEntryState.PRESENT
                    ),
                )
                for page_number in range(1, 4)
            ),
        )
        run = DocumentProcessingRun.start(
            processing_run_id=ProcessingRunId.from_value(run_id),
            source_document=document,
            page_manifest=manifest,
        )
        decisions = tuple(
            PageDecision(
                page_number=PageNumber.from_value(page_number),
                page_state=(
                    "EMPTY"
                    if page_number == 2 and middle_empty
                    else (
                        "UNSUPPORTED_OR_CORRUPT"
                        if page_number == 2 and middle_corrupt
                        else "NATIVE_OK"
                    )
                ),
                signals=signals(
                    empty=page_number == 2 and middle_empty,
                    corrupt=page_number == 2 and middle_corrupt,
                ),
                diagnostic_version=DiagnosticVersion.from_value("diag-v1"),
                justification=f"Diagnostic page {page_number}.",
            )
            for page_number in range(1, 4)
        )
        return run.record_page_diagnostics(decisions)

    routing = PageRoutingConfiguration(
        routing_policy_version=RoutingPolicyVersion.from_value("routing-v1"),
        auto_confidence_min=0.90,
        benchmark_confidence_min=0.85,
    )

    # Given une page 2 déjà diagnostiquée EMPTY, When le routage est décidé,
    # Then elle est ignorée explicitement sans revue manuelle.
    empty_run = diagnosed_run(
        middle_empty=True,
        middle_corrupt=False,
        run_id="RUN-M003-EMPTY-SKIP",
    ).decide_route_plan(routing)
    assert empty_run.status is DocumentProcessingRunStatus.ROUTE_PLANNED
    assert tuple(route.route_name for route in empty_run.route_plan.page_routes) == (
        PageRouteName.NATIVE_STANDARD,
        PageRouteName.SKIP_EMPTY,
        PageRouteName.NATIVE_STANDARD,
    )
    assert empty_run.manual_review_reason is None

    # Given une vraie page ambiguë, When un réviseur assigne une route,
    # Then la décision est persistée et le plan devient exécutable.
    manual_run = diagnosed_run(
        middle_empty=False,
        middle_corrupt=True,
        run_id="RUN-M003-MANUAL-ROUTE",
    ).decide_route_plan(routing)
    assert manual_run.status is DocumentProcessingRunStatus.MANUAL_REVIEW
    repository = Repository(manual_run)
    resolved = ResolveManualReviewHandler(
        processing_run_repository=repository,
        routing_configuration=routing,
    ).handle(
        ResolveManualReviewCommand(
            document_id=manual_run.document_id,
            decision=ManualReviewDecisionType.ASSIGN_ROUTE,
            page_number=PageNumber.from_value(2),
            route_name=PageRouteName.SCAN_GRANITE,
            reviewer_id="maxim",
            reason="La page contient une image lisible à convertir par Granite.",
        )
    )
    assert resolved.status is DocumentProcessingRunStatus.ROUTE_PLANNED
    assigned_route = resolved.route_plan.page_routes[1]
    assert assigned_route.route_name is PageRouteName.SCAN_GRANITE
    assert assigned_route.decision_mode is RouteDecisionMode.MANUAL
    assert resolved.page_decisions[1].manual_review_resolution.reviewer_id == "maxim"
    assert repository.transitions == [("MANUAL_REVIEW", "ROUTE_PLANNED")]

    # Given une page ambiguë confirmée vide, Then elle devient SKIP_EMPTY.
    confirm_run = diagnosed_run(
        middle_empty=False,
        middle_corrupt=True,
        run_id="RUN-M003-MANUAL-EMPTY",
    ).decide_route_plan(routing)
    confirmed = ResolveManualReviewHandler(
        processing_run_repository=Repository(confirm_run),
        routing_configuration=routing,
    ).handle(
        ResolveManualReviewCommand(
            document_id=confirm_run.document_id,
            decision=ManualReviewDecisionType.CONFIRM_EMPTY,
            page_number=PageNumber.from_value(2),
            route_name=None,
            reviewer_id="maxim",
            reason="Contrôle visuel : cette page est réellement blanche.",
        )
    )
    assert confirmed.status is DocumentProcessingRunStatus.ROUTE_PLANNED
    assert confirmed.route_plan.page_routes[1].route_name is PageRouteName.SKIP_EMPTY

    # Given une revue refusée, Then le document devient terminalement REJECTED.
    rejected_run = diagnosed_run(
        middle_empty=False,
        middle_corrupt=True,
        run_id="RUN-M003-MANUAL-REJECT",
    ).decide_route_plan(routing)
    rejected = ResolveManualReviewHandler(
        processing_run_repository=Repository(rejected_run),
        routing_configuration=routing,
    ).handle(
        ResolveManualReviewCommand(
            document_id=rejected_run.document_id,
            decision=ManualReviewDecisionType.REJECT_DOCUMENT,
            page_number=None,
            route_name=None,
            reviewer_id="maxim",
            reason="Le document est corrompu et ne doit pas être publié.",
        )
    )
    assert rejected.status is DocumentProcessingRunStatus.REJECTED

    # Given un document historique bloqué uniquement par une page EMPTY,
    # When la migration ADR-041 est appliquée,
    # Then elle reconstruit le plan SKIP_EMPTY et clôt la revue obsolète.
    migration = (
        repository_root
        / "deploy"
        / "postgres"
        / "migrations"
        / "017_manual_review_page_resolution.sql"
    ).read_text(encoding="utf-8")
    for required_sql in (
        "legacy_empty_route_candidates",
        "INSERT INTO source_processing.route_plans",
        "INSERT INTO source_processing.page_routes",
        "WHEN d.page_state = 'EMPTY' THEN 'SKIP_EMPTY'",
        "SET status = 'ROUTE_PLANNED'",
    ):
        assert required_sql in migration
