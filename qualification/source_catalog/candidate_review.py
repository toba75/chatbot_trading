"""Revue humaine des correspondances non exactes du registre de sources.

Une correspondance par titre et auteur reste `candidate` jusqu'à revue. Les
décisions prises vivent ici avec leur preuve, leur réviseur et leur date, de
sorte qu'une nouvelle exécution d'`enrich` les reproduise à l'identique. La
revue décide d'une édition ; elle ne fabrique aucune valeur : toute
revendication doit correspondre à une preuve citée, et la preuve d'une valeur
bibliographique reste celle de sa source, jamais la décision elle-même.
"""

from __future__ import annotations

import re
from typing import Any


DECISIONS = {"accepted", "rejected"}

# Décisions prises sur les candidats que le résolveur n'a pas pu trancher.
# Chaque entrée nomme les candidats réellement observés ; une revue qui
# désigne un candidat absent échoue au lieu d'être ignorée.
CANDIDATE_REVIEWS: dict[str, dict[str, Any]] = {
    # bear-market-trading-strategies.pdf
    "9aff5d8d643604f1c7a414af82b6b97b4c55e9643655e2c8ecb42b0b9064189f": {
        "reviewer": "toba75",
        "reviewed_at": "2026-08-08",
        "decisions": {
            "google_books:scWrzgEACAAJ": "rejected",
            "google_books:PxM9tgEACAAJ": "rejected",
        },
        "justification": (
            "La page de titre prouve l'œuvre et son auteur. Le volume de Joann "
            "Giesel désigne un autre ouvrage. Celui de Matthew R. Kratter porte "
            "la même œuvre mais l'édition de 2018, alors que le fichier porte la "
            "mention « 2ND EDITION » : l'accepter attacherait une date d'édition "
            "de 2018 à une seconde édition. Aucun candidat ne décrit donc "
            "l'édition de ce PDF ; le titre et l'auteur restent prouvés par le "
            "texte source."
        ),
        "source_claims": {
            "title": "Bear Market Trading Strategies",
            "authors": ["Matthew R. Kratter"],
            "proofs": [
                {
                    "kind": "source_text",
                    "locator": {"page": 2, "docling_ref": "#/texts/3", "charspan": [0, 30]},
                    "value": "BEAR MARKET TRADING STRATEGIES",
                },
                {
                    "kind": "source_text",
                    "locator": {"page": 2, "docling_ref": "#/texts/5", "charspan": [0, 18]},
                    "value": "MATTHEW R. KRATTER",
                },
                {
                    "kind": "source_text",
                    "locator": {"page": 2, "docling_ref": "#/texts/4", "charspan": [0, 11]},
                    "value": "2ND EDITION",
                },
            ],
        },
    },
}


class CandidateReviewError(ValueError):
    """La revue ne correspond pas aux candidats ou aux preuves observés."""


def observed_candidates(entry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        candidate["candidate_id"]: candidate
        for observation in entry.get("provider_observations", [])
        for candidate in observation.get("candidates", [])
    }


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _manual_proof(review: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "manual",
        "reviewer": review["reviewer"],
        "reviewed_at": review["reviewed_at"],
        "justification": review["justification"],
    }


def _checked_claims(review: dict[str, Any], location: str) -> dict[str, Any] | None:
    """Refuse une revendication que les preuves citées n'établissent pas."""
    claims = review.get("source_claims")
    if not claims:
        return None
    proofs = claims.get("proofs") or []
    if not proofs:
        raise CandidateReviewError(f"{location} : revendication de revue sans preuve")
    proven = {_normalized(str(proof.get("value", ""))) for proof in proofs}
    revendications = [claims["title"]] if claims.get("title") else []
    revendications += list(claims.get("authors") or [])
    absentes = [value for value in revendications if _normalized(value) not in proven]
    if absentes:
        raise CandidateReviewError(
            f"{location} : valeur revendiquée sans preuve citée : {', '.join(absentes)}"
        )
    return claims


def _apply_source_claims(entry: dict[str, Any], claims: dict[str, Any]) -> None:
    """Inscrit les valeurs prouvées par le texte source, sans identité d'édition."""
    bibliography = entry["bibliography"]
    provenance = bibliography.setdefault("provenance", [])
    for proof in claims["proofs"]:
        if proof not in provenance:
            provenance.append(proof)
    if claims.get("title"):
        bibliography["title"] = claims["title"]
    if claims.get("authors"):
        bibliography["authors"] = list(claims["authors"])


def apply_candidate_review(
    entry: dict[str, Any],
    resolution: str,
    *,
    reviews: dict[str, dict[str, Any]] = CANDIDATE_REVIEWS,
) -> dict[str, Any] | None:
    """Applique la décision humaine et rend le candidat éventuellement accepté.

    L'appelant reste responsable de recopier la bibliographie d'un candidat
    accepté. L'opération est idempotente : une revue déjà appliquée redonne le
    même état. Toute incohérence échoue avant la moindre écriture.
    """
    review = reviews.get(entry["source_sha256"])
    if review is None:
        return None
    location = entry["file_name"]
    decided_by_review = (entry["resolution"].get("proof") or {}).get("kind") == "manual"
    if resolution == "accepted" and not decided_by_review:
        raise CandidateReviewError(
            f"{location} : la preuve d'identifiant prime, aucune revue n'est admise"
        )
    observed = observed_candidates(entry)
    unknown = sorted(set(review["decisions"]) - set(observed))
    if unknown:
        raise CandidateReviewError(
            f"{location} : candidat revu absent des observations : {', '.join(unknown)}"
        )
    invalid = sorted(value for value in review["decisions"].values() if value not in DECISIONS)
    if invalid:
        raise CandidateReviewError(f"{location} : décision inconnue : {', '.join(invalid)}")
    retenus = [
        candidate_id
        for candidate_id, decision in review["decisions"].items()
        if decision == "accepted"
    ]
    if len(retenus) > 1:
        raise CandidateReviewError(f"{location} : une revue ne peut accepter qu'une seule édition")
    claims = _checked_claims(review, location)

    proof = _manual_proof(review)
    for candidate_id, decision in review["decisions"].items():
        candidate = observed[candidate_id]
        candidate["status"] = decision
        # La décision est tracée à part : la preuve du candidat reste celle du
        # fournisseur, sinon la bibliographie qui en dérive perdrait sa source.
        candidate["review"] = proof
    if claims:
        _apply_source_claims(entry, claims)
    if not retenus:
        entry["resolution"] = {"status": "rejected", "candidate_id": None, "proof": proof}
        return None
    accepted = observed[retenus[0]]
    entry["resolution"] = {
        "status": "accepted",
        "candidate_id": accepted["candidate_id"],
        "proof": proof | {"match": "manual_review"},
    }
    return accepted
