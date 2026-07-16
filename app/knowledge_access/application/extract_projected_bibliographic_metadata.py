"""Extraction bibliographique prouvée depuis le texte canonique projeté."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.contracts.llm_inference import (
    LlmInferenceGateway,
    LlmInferenceMessage,
    LlmInferenceRequest,
)


_MISSING_VALUE = "NON_RENSEIGNEE"
_EVIDENCE_FIELDS = frozenset({"title", "authors", "publication_year", "edition"})
_MAX_EVIDENCE_COUNT = 32
_MAX_EVIDENCE_CHARACTERS = 40_000
_PROMPT_VERSION = "1.1"
_SCHEMA_VERSION = "1.1"
_PROMPT = (
    "Extrais les informations bibliographiques uniquement depuis les extraits "
    "paginés fournis. N'utilise aucune connaissance externe et n'infère rien. "
    "Le titre et au moins un auteur sont obligatoires. Pour une année ou une "
    "édition non explicitement écrite, retourne exactement NON_RENSEIGNEE. "
    "Chaque valeur trouvée doit posséder une preuve copiée mot pour mot depuis "
    "la page indiquée. Le champ field de chaque preuve vaut exactement title, "
    "authors, publication_year ou edition. Retourne uniquement l'objet JSON "
    "conforme au schéma."
)


class ProjectedBibliographicMetadataExtractionError(RuntimeError):
    """Échec terminal et stable de la phase bibliographique KA."""

    def __init__(self, error_code: str) -> None:
        if not isinstance(error_code, str) or re.fullmatch(r"[A-Z][A-Z0-9_]{2,127}", error_code) is None:
            raise ValueError("code d'extraction bibliographique invalide")
        self.error_code = error_code
        super().__init__(error_code)


@dataclass(frozen=True, slots=True)
class ProjectedTextEvidence:
    """Extrait canonique paginé admis dans le prompt bibliographique."""

    page_pdf: int
    text: str

    def __post_init__(self) -> None:
        if isinstance(self.page_pdf, bool) or not isinstance(self.page_pdf, int) or self.page_pdf < 1:
            raise ValueError("page de preuve bibliographique invalide")
        object.__setattr__(self, "text", _required_text(self.text, "texte de preuve invalide"))


@dataclass(frozen=True, slots=True)
class BibliographicFieldEvidence:
    """Citation canonique qui soutient une valeur bibliographique."""

    field: str
    page_pdf: int
    quoted_text: str

    def __post_init__(self) -> None:
        if self.field not in _EVIDENCE_FIELDS:
            raise ValueError("champ de preuve bibliographique invalide")
        if isinstance(self.page_pdf, bool) or not isinstance(self.page_pdf, int) or self.page_pdf < 1:
            raise ValueError("page de preuve bibliographique invalide")
        object.__setattr__(self, "quoted_text", _required_text(self.quoted_text, "citation bibliographique invalide"))


@dataclass(frozen=True, slots=True)
class ProjectedBibliographicMetadata:
    """Métadonnées dérivées, régénérables et accompagnées de preuves."""

    title: str
    authors: tuple[str, ...]
    publication_year: int | None
    edition: str | None
    evidences: tuple[BibliographicFieldEvidence, ...]
    model_id: str
    model_revision: str
    runtime_version: str

    def __post_init__(self) -> None:
        title = _required_text(self.title, "titre bibliographique invalide")
        if len(title) > 512:
            raise ValueError("titre bibliographique trop long")
        object.__setattr__(self, "title", title)
        if not isinstance(self.authors, tuple) or not 1 <= len(self.authors) <= 16:
            raise ValueError("auteurs bibliographiques invalides")
        authors = tuple(_required_text(author, "auteur bibliographique invalide") for author in self.authors)
        if any(len(author) > 256 for author in authors):
            raise ValueError("auteur bibliographique trop long")
        object.__setattr__(self, "authors", authors)
        if self.publication_year is not None:
            if (
                isinstance(self.publication_year, bool)
                or not isinstance(self.publication_year, int)
                or not 1 <= self.publication_year <= 9999
            ):
                raise ValueError("année bibliographique invalide")
        if self.edition is not None:
            edition = _required_text(self.edition, "édition bibliographique invalide")
            if len(edition) > 64:
                raise ValueError("édition bibliographique trop longue")
            object.__setattr__(self, "edition", edition)
        if not isinstance(self.evidences, tuple) or len(self.evidences) < 2:
            raise ValueError("preuves bibliographiques absentes")
        if any(not isinstance(evidence, BibliographicFieldEvidence) for evidence in self.evidences):
            raise ValueError("preuve bibliographique invalide")
        evidenced_fields = {evidence.field for evidence in self.evidences}
        required_fields = {"title", "authors"}
        if self.publication_year is not None:
            required_fields.add("publication_year")
        if self.edition is not None:
            required_fields.add("edition")
        if not required_fields.issubset(evidenced_fields):
            raise ValueError("preuve bibliographique incomplète")
        object.__setattr__(self, "model_id", _required_text(self.model_id, "model_id bibliographique invalide"))
        object.__setattr__(self, "model_revision", _required_text(self.model_revision, "model_revision bibliographique invalide"))
        object.__setattr__(self, "runtime_version", _required_text(self.runtime_version, "runtime_version bibliographique invalide"))


@dataclass(frozen=True, slots=True)
class ExtractProjectedBibliographicMetadataCommand:
    document_id: str
    projection_id: str
    evidences: tuple[ProjectedTextEvidence, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.document_id, str) or not self.document_id.startswith("DOC-"):
            raise ValueError("document_id bibliographique invalide")
        if not isinstance(self.projection_id, str) or not self.projection_id.startswith("PROJ-"):
            raise ValueError("projection_id bibliographique invalide")
        if not isinstance(self.evidences, tuple) or not 1 <= len(self.evidences) <= _MAX_EVIDENCE_COUNT:
            raise ValueError("preuves projetées invalides")
        if any(not isinstance(evidence, ProjectedTextEvidence) for evidence in self.evidences):
            raise ValueError("preuve projetée invalide")
        if sum(len(evidence.text) for evidence in self.evidences) > _MAX_EVIDENCE_CHARACTERS:
            raise ValueError("preuves projetées trop volumineuses")


class ProjectedBibliographicMetadataExtractor:
    """Appelle une seule fois le gateway puis vérifie chaque citation retournée."""

    def __init__(self, *, inference_gateway: LlmInferenceGateway) -> None:
        if not callable(getattr(inference_gateway, "infer", None)):
            raise ValueError("gateway bibliographique invalide")
        self._inference_gateway = inference_gateway

    def extract(
        self,
        command: ExtractProjectedBibliographicMetadataCommand,
    ) -> ProjectedBibliographicMetadata:
        if not isinstance(command, ExtractProjectedBibliographicMetadataCommand):
            raise ValueError("commande d'extraction bibliographique invalide")
        response = self._inference_gateway.infer(_request(command))
        if response.status_code != 200:
            raise ProjectedBibliographicMetadataExtractionError(
                "BIBLIOGRAPHIC_METADATA_LLM_UNAVAILABLE"
            )
        structured = response.payload.get("structured_output")
        provenance = response.payload.get("provenance")
        if not isinstance(structured, Mapping) or not isinstance(provenance, Mapping):
            raise ProjectedBibliographicMetadataExtractionError(
                "BIBLIOGRAPHIC_METADATA_OUTPUT_INVALID"
            )
        try:
            return _metadata_from_output(
                structured=structured,
                provenance=provenance,
                source_evidences=command.evidences,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectedBibliographicMetadataExtractionError(
                "BIBLIOGRAPHIC_METADATA_OUTPUT_INVALID"
            ) from exc


def _request(command: ExtractProjectedBibliographicMetadataCommand) -> LlmInferenceRequest:
    evidence_text = "\n\n".join(
        f"[PAGE_PDF={evidence.page_pdf}]\n{evidence.text}"
        for evidence in command.evidences
    )
    request_hash = hashlib.sha256(
        (
            f"{command.projection_id}\n{_PROMPT_VERSION}\n"
            f"{_SCHEMA_VERSION}\n{evidence_text}"
        ).encode("utf-8")
    ).hexdigest()
    return LlmInferenceRequest(
        messages=(
            LlmInferenceMessage(
                role="user",
                content=f"{_PROMPT}\n\n{evidence_text}",
            ),
        ),
        output_schema=_output_schema(),
        schema_name="projected_bibliographic_metadata",
        schema_version=_SCHEMA_VERSION,
        trace_id=f"TRACE-M005-METADATA-{command.document_id.removeprefix('DOC-')}",
        request_id=f"REQ-M005-METADATA-{command.projection_id.removeprefix('PROJ-')}",
        idempotency_key=f"IDEMP-M005-METADATA-{request_hash}",
        prompt_id="m005-bibliographic-metadata-extraction",
        prompt_version=_PROMPT_VERSION,
        sampling_parameters={"temperature": 0.0, "max_tokens": 2048},
    )


def _metadata_from_output(
    *,
    structured: Mapping[str, Any],
    provenance: Mapping[str, Any],
    source_evidences: tuple[ProjectedTextEvidence, ...],
) -> ProjectedBibliographicMetadata:
    expected = {"title", "authors", "publication_year", "edition", "evidence"}
    if set(structured) != expected:
        raise ValueError("sortie bibliographique incompatible")
    title = _required_text(structured["title"], "titre bibliographique invalide")
    raw_authors = structured["authors"]
    if not isinstance(raw_authors, list):
        raise ValueError("auteurs bibliographiques invalides")
    authors = tuple(_required_text(author, "auteur bibliographique invalide") for author in raw_authors)
    publication_year = _optional_year(structured["publication_year"])
    edition = _optional_text(structured["edition"])
    raw_evidences = structured["evidence"]
    if not isinstance(raw_evidences, list):
        raise ValueError("preuves bibliographiques invalides")
    evidences = tuple(_field_evidence(item) for item in raw_evidences)
    _verify_evidence_quotes(evidences=evidences, sources=source_evidences)
    return ProjectedBibliographicMetadata(
        title=title,
        authors=authors,
        publication_year=publication_year,
        edition=edition,
        evidences=evidences,
        model_id=_required_mapping_text(provenance, "model_id"),
        model_revision=_required_mapping_text(provenance, "model_revision"),
        runtime_version=_required_mapping_text(provenance, "runtime_version"),
    )


def _field_evidence(value: Any) -> BibliographicFieldEvidence:
    if not isinstance(value, Mapping) or set(value) != {"field", "page_pdf", "quoted_text"}:
        raise ValueError("preuve bibliographique incompatible")
    return BibliographicFieldEvidence(
        field=value["field"],
        page_pdf=value["page_pdf"],
        quoted_text=value["quoted_text"],
    )


def _verify_evidence_quotes(
    *,
    evidences: tuple[BibliographicFieldEvidence, ...],
    sources: tuple[ProjectedTextEvidence, ...],
) -> None:
    source_texts: dict[int, str] = {}
    for source in sources:
        source_texts[source.page_pdf] = f"{source_texts.get(source.page_pdf, '')} {source.text}"
    for evidence in evidences:
        source_text = source_texts.get(evidence.page_pdf)
        if source_text is None or _normalized(evidence.quoted_text) not in _normalized(source_text):
            raise ValueError("citation bibliographique non vérifiable")


def _optional_year(value: Any) -> int | None:
    if value == _MISSING_VALUE:
        return None
    if not isinstance(value, str) or re.fullmatch(r"[1-9][0-9]{0,3}", value) is None:
        raise ValueError("année bibliographique invalide")
    return int(value)


def _optional_text(value: Any) -> str | None:
    if value == _MISSING_VALUE:
        return None
    return _required_text(value, "édition bibliographique invalide")


def _required_mapping_text(value: Mapping[str, Any], field: str) -> str:
    return _required_text(value[field], f"{field} bibliographique invalide")


def _required_text(value: Any, message: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(message)
    return value


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def _output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["title", "authors", "publication_year", "edition", "evidence"],
        "properties": {
            "title": {"type": "string", "minLength": 1, "maxLength": 512},
            "authors": {
                "type": "array",
                "minItems": 1,
                "maxItems": 16,
                "items": {"type": "string", "minLength": 1, "maxLength": 256},
            },
            "publication_year": {"type": "string"},
            "edition": {"type": "string"},
            "evidence": {
                "type": "array",
                "minItems": 2,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["field", "page_pdf", "quoted_text"],
                    "properties": {
                        "field": {
                            "type": "string",
                            "enum": ["title", "authors", "publication_year", "edition"],
                        },
                        "page_pdf": {"type": "integer", "minimum": 1},
                        "quoted_text": {"type": "string", "minLength": 1},
                    },
                },
            },
        },
    }


__all__ = [
    "BibliographicFieldEvidence",
    "ExtractProjectedBibliographicMetadataCommand",
    "ProjectedBibliographicMetadata",
    "ProjectedBibliographicMetadataExtractionError",
    "ProjectedBibliographicMetadataExtractor",
    "ProjectedTextEvidence",
]
