"""Erreurs explicites de la gate."""


class GateError(RuntimeError):
    """Erreur de contrat empêchant une exécution fiable de la gate."""


class ManifestError(GateError):
    """Le manifeste ne peut pas être utilisé."""


class PlanError(GateError):
    """Le graphe de dépendances est invalide."""
