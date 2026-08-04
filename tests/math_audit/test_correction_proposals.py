import io
import zipfile
from pathlib import Path

import fitz

from pdf_math_audit.correction import CorrectionConfig
from pdf_math_audit.correction_proposals import propose_proven_latex
from pdf_math_audit.gemma_proposal import Proposal


ROOT = Path(__file__).parents[2]
PDF = ROOT / "experiments/math_pipeline_comparison/source-pages-7-10.pdf"
CONFIG = CorrectionConfig("http://gemma/v1", "gemma", 300, 4.0, 10, 10_000)


def _region(tokens: list[str]) -> dict[str, object]:
    return {
        "region_id": "proposal:1",
        "bbox": [10.0, 10.0, 40.0, 30.0],
        "source_canonical_tokens": tokens,
        "source_relation_signature": tokens,
    }


def _attempt(
    region: dict[str, object], proposal: str, *, independent: bool
):
    calls = []

    def vision(**arguments: object) -> Proposal:
        calls.append(arguments)
        return Proposal(proposal, {}, {})

    evidence = io.BytesIO()
    with (
        fitz.open(PDF) as pdf,
        zipfile.ZipFile(evidence, "w", zipfile.ZIP_DEFLATED) as archive,
    ):
        attempt = propose_proven_latex(
            region,
            pdf[0],
            archive,
            CONFIG,
            vision,
            None,
            require_independent_vision=independent,
        )
    return attempt, calls


def test_demande_au_modele_de_regrouper_un_identifiant_textuel() -> None:
    attempt, calls = _attempt(
        _region(list("density")), r"\operatorname{density}", independent=False
    )

    assert len(calls) == 1
    assert attempt.latex == r"\operatorname{density}"
    assert attempt.rejection_reason is None
    assert attempt.details["deterministic_proposal"] == "d e n s i t y"
    assert attempt.details["deterministic_rejection_reason"] == (
        "deterministic_text_grouping_unproven"
    )
    assert attempt.details["selected_engine"] == "vision_proven_by_source"


def test_la_confirmation_independante_utilise_la_proposition_visuelle() -> None:
    attempt, calls = _attempt(_region(["x"]), r"\mathrm{x}", independent=True)

    assert len(calls) == 1
    assert "logical glyph sequence" not in calls[0]["prompt"]
    assert attempt.latex == r"\mathrm{x}"
    assert attempt.details["selected_engine"] == "vision_proven_by_source"
