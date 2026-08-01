from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def require_hash(path: Path, expected: str) -> None:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(f"Empreinte inattendue pour {path}: {actual} != {expected}")


def validate_independent_proofs(oracle: dict[str, Any], *, required: bool) -> None:
    proofs = oracle.get("independent_proofs")
    if proofs is None:
        if required:
            raise ValueError("Preuves indépendantes manquantes pour le corpus représentatif")
        return
    if not isinstance(proofs, list) or not proofs:
        raise ValueError("Liste de preuves indépendantes invalide")
    if any(not isinstance(proof, dict) or set(proof) != {"id", "path", "sha256"} for proof in proofs):
        raise ValueError("Contrat de preuve indépendante invalide")
    identifiers = [proof["id"] for proof in proofs]
    paths = [proof["path"] for proof in proofs]
    if any(not isinstance(value, str) or not value for value in identifiers + paths):
        raise ValueError("Identifiant ou chemin de preuve indépendante invalide")
    if len(identifiers) != len(set(identifiers)) or len(paths) != len(set(paths)):
        raise ValueError("Preuves indépendantes dupliquées")
    if any(Path(path).is_absolute() for path in paths):
        raise ValueError("Le chemin d'une preuve indépendante doit être relatif")
    if any(not isinstance(proof["sha256"], str) or not SHA256_PATTERN.fullmatch(proof["sha256"]) for proof in proofs):
        raise ValueError("Empreinte de preuve indépendante invalide")


def verify_independent_proofs(
    oracle_path: Path, oracle: dict[str, Any]
) -> list[dict[str, str]]:
    proofs = oracle["independent_proofs"]
    for proof in proofs:
        require_hash(oracle_path.parent / proof["path"], proof["sha256"])
    return proofs
