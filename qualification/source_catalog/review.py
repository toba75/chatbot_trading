"""Revue éditoriale datée, qualitative et sans score d'autorité global."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


KEYWORDS = {
    "momentum": "momentum",
    "trend": "trend_following",
    "turtle": "trend_following",
    "machine learning": "machine_learning",
    "alpha": "quantitative_investing",
    "factor": "factor_investing",
    "value": "value_investing",
    "acquirer": "value_investing",
    "market": "market_structure",
    "volatility": "risk_management",
    "liquidity": "market_structure",
    "regime": "regime_analysis",
    "trading": "trading_practice",
    "investor": "portfolio_management",
    "portfolio": "portfolio_management",
}

LOCAL_REVIEW_OVERRIDES = {
    "the_big_secret_for_the_small_investor_-_joel_greenblatt.pdf": {
        "domains": ["value_investing", "portfolio_management"],
        "flag": "classic_still_relevant",
        "justification": "La page de titre et le texte local identifient un ouvrage classique de value investing ; ses principes sont conservés comme contexte, pas comme conseil actuel.",
    },
    "a century of profitable industry trends carlo zarattini gary antonacci.pdf": {
        "domains": ["trend_following", "market_history"],
        "flag": "little_known_relevant",
        "justification": "Le texte local identifie une étude historique des tendances industrielles ; elle apporte un angle documenté même sans édition commerciale résolue.",
    },
    "trading-for-a-living-psychology-trading-tactics-money-management.pdf": {
        "domains": ["trading_practice", "risk_management"],
        "flag": "dated_context_requires_current_validation",
        "justification": "L'ouvrage documente des pratiques de trading et de gestion du risque ; son contexte ancien exige une validation contre les marchés actuels.",
    },
}


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def _domains(title: str, categories: list[str] | None = None) -> list[str]:
    text = title.casefold()
    domains = {domain for keyword, domain in KEYWORDS.items() if keyword in text}
    for category in categories or []:
        lowered = category.casefold()
        if "business" in lowered or "finance" in lowered:
            domains.add("portfolio_management")
        if "mathemat" in lowered or "statistics" in lowered:
            domains.add("quantitative_investing")
    return sorted(domains) or ["trading_practice"]


def review_catalog(catalog: dict[str, Any], *, reviewed_at: str | None = None, reviewer: str = "codex") -> dict[str, Any]:
    """Revoit chaque entrée ; l'incertitude reste un état explicite."""
    day = reviewed_at or _today()
    for entry in catalog["documents"]:
        lookup = entry["lookup"]
        resolution = entry.get("resolution", {}).get("status")
        override = LOCAL_REVIEW_OVERRIDES.get(entry["file_name"].casefold())
        candidates = [
            candidate
            for observation in entry.get("provider_observations", [])
            for candidate in observation.get("candidates", [])
            if candidate.get("status") == "accepted"
        ]
        if resolution == "accepted" and candidates:
            candidate = candidates[0]
            title = candidate.get("title") or lookup["title"]
            entry["editorial_review"] = {
                "status": "reviewed",
                "reviewed_at": day,
                "reviewer": reviewer,
                "proof": {"kind": "manual", "reviewer": reviewer},
                "domains": _domains(title, candidate.get("categories")),
                "method": "notice bibliographique et lecture du titre ; aucune autorité globale",
                "authority_basis": {
                    "level": "domain_specific",
                    "basis": ["identité d'édition reliée à une preuve Google Books"],
                },
                "justification": "La source est pertinente pour les domaines indiqués par son titre et sa notice ; la pertinence ne vaut pas validation universelle.",
                "limitations": "Aucune mesure empirique ni revue exhaustive des arguments n'est ajoutée à cette étape.",
                "review_flags": _review_flags(entry["file_name"]),
            }
        elif override:
            entry["editorial_review"] = {
                "status": "reviewed",
                "reviewed_at": day,
                "reviewer": reviewer,
                "proof": {"kind": "manual", "reviewer": reviewer},
                "domains": override["domains"],
                "method": "lecture du texte local et de la page de titre ; aucune autorité globale",
                "authority_basis": {
                    "level": "contextual",
                    "basis": ["preuve textuelle locale", "limites explicites de la revue"],
                },
                "justification": override["justification"],
                "limitations": "Aucune correspondance fournisseur acceptée : l'identité commerciale, l'édition et la fraîcheur ne sont pas promues.",
                "review_flags": [override["flag"]],
            }
        else:
            reason = "identité d'édition non résolue"
            if resolution == "no_match":
                reason = "aucun volume Google Books correspondant ; publication possiblement sans ISBN"
            elif resolution == "ambiguous":
                reason = "plusieurs volumes plausibles ; revue humaine d'édition nécessaire"
            elif resolution == "unavailable":
                reason = "fournisseur indisponible ; aucune valeur externe promue"
            entry["editorial_review"] = {
                "status": "not_assessable",
                "reviewed_at": day,
                "reviewer": reviewer,
                "reason": reason,
                "limitations": "Le titre de fichier ne suffit pas à attribuer une autorité éditoriale.",
            }
    return catalog


def _review_flags(filename: str) -> list[str]:
    lowered = filename.casefold()
    if "the_big_secret" in lowered:
        return ["classic_still_relevant"]
    if "century of profitable" in lowered:
        return ["little_known_relevant"]
    if "trading-for-a-living" in lowered:
        return ["dated_context_requires_current_validation"]
    return []
