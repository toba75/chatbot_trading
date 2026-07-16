from __future__ import annotations

from app.contracts.llm_inference import LlmInferenceResponse
from app.knowledge_access.application.extract_projected_bibliographic_metadata import (
    ExtractProjectedBibliographicMetadataCommand,
    ProjectedBibliographicMetadataExtractor,
    ProjectedTextEvidence,
)
from app.platform.orchestrator_api_models import DOCUMENT_MULTIPART_OPENAPI
from app.platform.ui_corpus import CorpusPdfScreenState, render_corpus_pdf_screen


class RecordingGateway:
    def __init__(self) -> None:
        self.requests = []

    def infer(self, request):
        self.requests.append(request)
        return LlmInferenceResponse(
            status_code=200,
            latency_ms=12.0,
            payload={
                "structured_output": {
                    "title": "Trading on Momentum",
                    "authors": ["Ken Wolff", "Chris Schumacher", "Jeff Tappan"],
                    "publication_year": "2002",
                    "edition": "NON_RENSEIGNEE",
                    "evidence": [
                        {"field": "title", "page_pdf": 1, "quoted_text": "Trading on Momentum"},
                        {"field": "authors", "page_pdf": 1, "quoted_text": "Ken Wolff with Chris Schumacher and Jeff Tappan"},
                        {"field": "publication_year", "page_pdf": 5, "quoted_text": "Copyright © 2002"},
                    ],
                },
                "provenance": {
                    "model_id": "google/gemma-4-26B-A4B-it",
                    "model_revision": "google/gemma-4-26B-A4B-it@test",
                    "runtime_version": "vllm-test",
                },
            },
        )


def test_admission_sans_metadonnees_et_extraction_apres_projection() -> None:
    # Given un PDF est admis sans saisie bibliographique.
    schema = DOCUMENT_MULTIPART_OPENAPI["requestBody"]["content"]["multipart/form-data"]["schema"]
    assert schema["required"] == ["original_content"]
    assert set(schema["properties"]) == {"original_content"}
    html = render_corpus_pdf_screen(
        CorpusPdfScreenState(
            documents=(),
            active_selected_document_ids=(),
            read_model_status="READ_MODEL_READY",
        )
    )
    assert 'name="title"' not in html
    assert 'name="authors"' not in html
    assert 'name="publication_year"' not in html
    assert 'name="edition"' not in html

    # When la phase post-projection appelle Gemma sur des preuves paginées.
    gateway = RecordingGateway()
    result = ProjectedBibliographicMetadataExtractor(inference_gateway=gateway).extract(
        ExtractProjectedBibliographicMetadataCommand(
            document_id="DOC-6A77FD40209CBB1E",
            projection_id="PROJ-6A77FD40209CBB1E",
            evidences=(
                ProjectedTextEvidence(
                    page_pdf=1,
                    text="Trading on Momentum Advanced Techniques Ken Wolff with Chris Schumacher and Jeff Tappan",
                ),
                ProjectedTextEvidence(page_pdf=5, text="Copyright © 2002 by Mtrader.com."),
            ),
        )
    )

    # Then seules les valeurs prouvées sont publiées et l'édition absente reste absente.
    assert result.title == "Trading on Momentum"
    assert result.authors == ("Ken Wolff", "Chris Schumacher", "Jeff Tappan")
    assert result.publication_year == 2002
    assert result.edition is None
    assert result.model_id == "google/gemma-4-26B-A4B-it"
    assert len(result.evidences) == 3
    assert len(gateway.requests) == 1
    assert gateway.requests[0].prompt_id == "m005-bibliographic-metadata-extraction"
