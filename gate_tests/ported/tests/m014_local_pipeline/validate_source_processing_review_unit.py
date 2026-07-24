"""Régressions de revue du chemin public et de l'exécution SP M14."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from app.platform.job_runtime import InMemoryJobQueue, JOB_RUNTIME_CATALOG
from app.source_processing.adapters.local_page_artifacts import LocalPageArtifactStore
from app.source_processing.application.document_commands import (
    DocumentConversionCommandService,
    DocumentConversionExecutionPhase,
    DocumentConversionState,
    DocumentConversionStatus,
)
from app.source_processing.application.execute_document_page import PageRouteConverters
from app.source_processing.application.fan_out_document_pages import (
    DISTRIBUTED_PAGE_FAN_OUT_VERSION,
    DistributedDocumentConversionWorker,
)
from app.source_processing.domain.distribution_contracts import (
    LocalArtifactIdentity,
    PageResultErrorCode,
    PageResultStatus,
)
from validate_page_execution_unit import (
    _Converter,
    _claimed,
    _handler_for,
    _page_jobs,
    _standard_metrics,
)
from validate_page_fan_out_unit import (
    _FanOutRepository,
    _ProcessingRuns,
    _assets,
    _parent_job,
    _planned_run,
    _source,
)


class _Sources:
    def __init__(self, source):
        self.source = source

    def find_by_document_id(self, document_id):
        return self.source if self.source.document_id == document_id else None


class _Conversions:
    def __init__(self, queue):
        self.queue = queue
        self.request = None

    def find_conversion_by_document_id(self, document_id):
        return None

    def submit_conversion_request(self, conversion_state, job_request):
        self.request = job_request
        return self.queue.submit(request=job_request, recalculate=False)


class _OriginalPaths:
    def __init__(self, path: Path):
        self.path = path

    def resolve_internal_path(self, storage_ref):
        return self.path


class _MissingReader:
    def resolve_verified_path(self, descriptor):
        from app.source_processing.domain.distribution_contracts import ArtifactContractError

        raise ArtifactContractError("ARTIFACT_NOT_FOUND")


def _commande_publique_selectionne_explicitement_le_fan_out_m014() -> None:
    source = _source()
    run = _planned_run(source)
    queue = InMemoryJobQueue.empty(catalog=JOB_RUNTIME_CATALOG)
    conversions = _Conversions(queue)
    service = DocumentConversionCommandService(
        source_document_repository=_Sources(source),
        processing_run_repository=_ProcessingRuns(run),
        document_conversion_repository=conversions,
        environment="test",
        deployment_id="ostrading-test-local",
        conversion_configuration_hash="c" * 64,
        code_version="m014-review-v1",
        model_version="docling-review-v1",
        orchestration_version=DISTRIBUTED_PAGE_FAN_OUT_VERSION,
    )

    service.request_document_conversion(document_id=source.document_id.value)

    assert conversions.request is not None
    assert conversions.request.payload["orchestration_version"] == (
        DISTRIBUTED_PAGE_FAN_OUT_VERSION
    )


def _worker_distribue_materialise_une_source_immutable_puis_cree_les_pages() -> None:
    source = _source()
    run = _planned_run(source)
    parent = _parent_job(source, run)
    claim = replace(
        _claimed(parent, job_number=81, owner="worker-documents-a"),
        trace_id="TRACE-M014-FANOUT-UNIT",
    )
    repository = _FanOutRepository()
    with TemporaryDirectory(prefix="ostrading-m014-review-") as temporary:
        root = Path(temporary)
        original = root / "original.pdf"
        original.write_bytes(b"%PDF-1.7\nM014 fan-out unit\n%%EOF\n")
        worker = DistributedDocumentConversionWorker(
            source_document_repository=_Sources(source),
            processing_run_repository=_ProcessingRuns(run),
            page_fan_out_repository=repository,
            original_source_store=_OriginalPaths(original),
            source_artifact_store=LocalPageArtifactStore(
                profile_root=(root / "artifacts").resolve()
            ),
            locked_assets=_assets(),
        )

        result = worker.execute(claim)

        assert result["page_job_count"] == 3
        assert repository.plan is not None
        materialized = repository.plan.source_artifact
        path = materialized.identity.resolve_under((root / "artifacts").resolve())
        assert path.is_file()
        assert path.read_bytes() == original.read_bytes()


def _erreur_artefact_devient_completion_failed_et_garde_configuration() -> None:
    request, _, _ = _page_jobs()
    claim = _claimed(request, job_number=82, owner="worker-documents-a")
    routed = _Converter(metrics=_standard_metrics())
    converters = PageRouteConverters.from_routed(routed)
    handler, _, writer, completion, _ = _handler_for(
        b"%PDF-1.7\nM014 fan-out unit\n%%EOF\n",
        converters=converters,
        reader=_MissingReader(),
        expected_locked_assets=_assets(),
    )

    outcome = handler.execute_standard(claim)

    assert outcome.result.status is PageResultStatus.FAILED
    assert outcome.result.error_code is PageResultErrorCode.ARTIFACT_NOT_FOUND
    assert writer.writes == 0
    assert len(completion.calls) == 1
    message = completion.messages[0]
    assert message.configuration_hash == "c" * 64


def _publication_artefact_refuse_un_claim_expire() -> None:
    with TemporaryDirectory(prefix="ostrading-m014-atomic-") as temporary:
        root = Path(temporary).resolve()
        store = LocalPageArtifactStore(profile_root=root)
        identity = LocalArtifactIdentity(
            environment="test",
            artifact_ref="artifact:source_processing.local/test/pages/page-1.json",
            relative_path="pages/page-1.json",
        )
        try:
            store.write_immutable(
                identity=identity,
                content=b"resultat",
                lease_expires_at=datetime.now(UTC) - timedelta(seconds=1),
            )
        except Exception as error:
            assert "JOB_LEASE_LOST" in str(error)
        else:
            raise AssertionError("un claim expiré ne doit pas publier l'artefact")
        assert not identity.resolve_under(root).exists()


def _codes_m014_sont_des_echecs_publics_stables() -> None:
    source = _source()
    for code in (
        "PAGE_MANIFEST_INCOMPLETE",
        "PAGE_RESULT_TERMINAL_FAILURE",
        "CANONICAL_ASSEMBLY_REPLAY_DIVERGENCE",
    ):
        state = DocumentConversionState(
            document_id=source.document_id,
            conversion_status=DocumentConversionStatus.QA_REJECTED,
            canonical_version_id=None,
            rejection_error_code=code,
            execution_phase=DocumentConversionExecutionPhase.FAILED,
            completed_units=1,
            total_units=4,
            failure_error_code=code,
        )
        assert state.failure_error_code == code


def test_corrections_revue_source_processing() -> None:
    _commande_publique_selectionne_explicitement_le_fan_out_m014()
    _worker_distribue_materialise_une_source_immutable_puis_cree_les_pages()
    _erreur_artefact_devient_completion_failed_et_garde_configuration()
    _publication_artefact_refuse_un_claim_expire()
    _codes_m014_sont_des_echecs_publics_stables()
