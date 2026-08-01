from __future__ import annotations

import argparse
import json
import time
import tracemalloc
from pathlib import Path
from typing import Any

from docling_core.types.doc import DoclingDocument

from pdf_math_audit.alignment import DoclingAlignment
from pdf_math_audit.analyzer import analyze_pdf
from pdf_math_audit.semantic_evaluation import evaluate_regions

from qualification.math_audit.file_integrity import (
    require_hash as _require_hash,
    validate_independent_proofs,
    verify_independent_proofs as _verify_independent_proofs,
)
from qualification.math_audit.gate_acceptance import build_gate_report
from qualification.math_audit.measurement import measure


def _run_audit(pdf: Path, document_path: Path) -> tuple[dict[str, Any], dict[str, float]]:
    document = DoclingDocument.model_validate_json(document_path.read_bytes())
    alignment = DoclingAlignment(document)
    tracemalloc.start()
    wall_start, cpu_start = time.perf_counter(), time.process_time()
    source_report = analyze_pdf(pdf, on_evidence=alignment.observe_glyph)
    report = {"alignment": alignment.finalize(source_report)}
    cpu_seconds = time.process_time() - cpu_start
    wall_seconds = time.perf_counter() - wall_start
    _current, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return report, {
        "wall_seconds": round(wall_seconds, 6),
        "cpu_seconds": round(cpu_seconds, 6),
        "peak_python_bytes": peak_bytes,
    }


def _audit(
    root: Path,
    corpus: dict[str, Any],
    runtime_requirements: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, float]]:
    pdf = root / corpus["pdf"]
    _require_hash(pdf, corpus["pdf_sha256"])
    provenance_path = root / corpus["candidate_provenance"]
    _require_hash(provenance_path, corpus["candidate_provenance_sha256"])
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    if provenance["source_pdf_sha256"] != corpus["pdf_sha256"]:
        raise ValueError("La capture Docling ne correspond pas au PDF du manifeste")
    runtime = provenance["runtime_proof"]
    if not runtime_requirements.items() <= runtime.items():
        raise ValueError("La capture ne prouve pas le runtime CUDA/Granite requis")
    document = provenance_path.parent / provenance["docling_document"]
    document_sha256 = provenance["docling_document_sha256"]
    response = provenance_path.parent / provenance["raw_response"]
    _require_hash(response, provenance["raw_response_sha256"])
    _require_hash(document, document_sha256)
    audit, resources = _run_audit(pdf, document)
    resources["docling_processing_seconds"] = provenance["processing_time"]
    return audit, resources


def _mutation_glyphs(text: str) -> list[dict[str, Any]]:
    return [
        {
            "page": 1,
            "sequence_index": index,
            "glyph_name": character,
            "unicode": character,
            "font_resource": "/oracle",
            "code": ord(character),
            "code_hex": f"{ord(character):04X}",
            "cff_gid": index + 1,
            "rendered_gid": index + 1,
            "to_unicode": character,
            "rendered_unicode": character,
            "rendered_origin_y": 10.0,
            "rendered_size": 10.0,
            "rawdict": {"block": 0, "line": 0, "span": 0, "char": index},
        }
        for index, character in enumerate(text)
    ]


def _observed_mutation(mutation: dict[str, Any]) -> str:
    if set(mutation) != {"id", "source", "candidate", "expected"}:
        raise ValueError(f"Contrat de mutation invalide : {mutation.get('id')}")
    region = {
        "region_id": mutation["id"],
        "kind": "formula",
        "page": 1,
        "status": "traced",
        "candidate_text": mutation["candidate"],
        "candidate_format": "latex",
        "glyph_sequence_indices": list(range(len(mutation["source"]))),
    }
    regions, _metrics = evaluate_regions([region], _mutation_glyphs(mutation["source"]))
    return regions[0]["verdict"]


def _validate_oracle(oracle: dict[str, Any], corpus: dict[str, Any]) -> None:
    properties = {"exhaustive": "exhaustive_oracle", "representative": "representative"}
    for property_name, corpus_property in properties.items():
        if oracle[property_name] is not corpus[corpus_property]:
            raise ValueError(
                f"Propriété {property_name} incohérente pour {corpus['id']}"
            )
    region_ids = [region["id"] for region in oracle["regions"]]
    if len(region_ids) != len(set(region_ids)):
        raise ValueError(f"Identifiants de régions dupliqués pour {corpus['id']}")
    expected_non_verifiable = oracle.get("expected_non_verifiable", {})
    if not isinstance(expected_non_verifiable, dict) or not set(
        expected_non_verifiable
    ) <= set(region_ids):
        raise ValueError(f"Refus sémantiques invalides pour {corpus['id']}")
    if any(not isinstance(reason, str) for reason in expected_non_verifiable.values()):
        raise ValueError(f"Raison de refus invalide pour {corpus['id']}")
    if any(not region.get("semantic_assertions") for region in oracle["regions"]):
        raise ValueError(f"Assertion sémantique manquante pour {corpus['id']}")
    validate_independent_proofs(oracle, required=corpus["representative"])


def _oracle_regions(oracle: dict[str, Any]) -> list[dict[str, Any]]:
    expected_non_verifiable = oracle.get("expected_non_verifiable", {})
    return [
        region
        | (
            {
                "expected_verdict": "non_verifiable",
                "expected_reason": expected_non_verifiable[region["id"]],
            }
            if region["id"] in expected_non_verifiable
            else {}
        )
        for region in oracle["regions"]
    ]


def _validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest["schema_version"] != 1:
        raise ValueError("Version de manifeste invalide")
    iou = manifest["iou_threshold"]
    if isinstance(iou, bool) or not isinstance(iou, (int, float)) or not 0 < iou <= 1:
        raise ValueError("Seuil invalide : iou_threshold")
    thresholds = manifest["thresholds"]
    for name in (
        "detection_recall",
        "detection_precision",
        "traceability_coverage",
        "semantic_expectation_accuracy",
    ):
        value = thresholds[name]
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 <= value <= 1
        ):
            raise ValueError(f"Seuil invalide : {name}")
    false_conformant = thresholds["false_conformant_mutations"]
    if (
        isinstance(false_conformant, bool)
        or not isinstance(false_conformant, int)
        or false_conformant < 0
    ):
        raise ValueError("Seuil invalide : false_conformant_mutations")


def qualify(manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _validate_manifest(manifest)
    root = manifest_path.parent
    corpus_results = []
    for corpus in manifest["corpora"]:
        oracle_path = root / corpus["oracle"]
        _require_hash(oracle_path, corpus["oracle_sha256"])
        oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
        _validate_oracle(oracle, corpus)
        independent_proofs = (
            _verify_independent_proofs(oracle_path, oracle)
            if corpus["representative"]
            else []
        )
        audit, resources = _audit(root, corpus, manifest["runtime_requirements"])
        measurement = measure(_oracle_regions(oracle), audit, manifest["iou_threshold"])
        corpus_results.append(
            {
                "id": corpus["id"],
                "exhaustive_oracle": corpus["exhaustive_oracle"],
                "representative": corpus["representative"],
                "independent_proofs": independent_proofs,
                **measurement,
                "resources": resources,
            }
        )

    mutation_results = [
        {**mutation, "observed": _observed_mutation(mutation)}
        for mutation in manifest["mutations"]
    ]
    return build_gate_report(manifest, corpus_results, mutation_results)


def main() -> int:
    parser = argparse.ArgumentParser(description="Qualifie la couverture mathématique.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = qualify(args.manifest)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if report["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
