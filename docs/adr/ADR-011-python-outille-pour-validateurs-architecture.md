# ADR-011 - Python outillé pour les validateurs d'architecture

**Statut :** Acceptée
**Date :** 2026-06-25
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** `docs/tasks/milestone_001/0010_interdire_couplages_intercontextes.md`, revue M-001

## Contexte

M-001 ajoute un validateur de frontières d'import qui inspecte l'AST Python des modules `app/`. Cette inspection est plus fiable via la bibliothèque standard Python qu'avec une analyse textuelle PowerShell.

ADR-010 conserve `scripts/test.ps1` et `scripts/lint.ps1` comme entrées canoniques PowerShell. L'ajout de Python concerne l'outillage interne d'un validateur appelé par ces gates, pas une dépendance applicative métier.

## Décision

Les gates PowerShell PEUVENT appeler un validateur Python outillé lorsque le contrôle exige l'analyse d'un code Python.

Le wrapper PowerShell qui appelle ce validateur DOIT vérifier explicitement la présence de Python et la version minimale `3.10` avant d'exécuter le script Python.

Le wrapper NE DOIT PAS retourner GREEN si l'interpréteur Python est absent, trop ancien, non résolu ou si le code de sortie du processus Python est absent.

Aucune dépendance tierce Python n'est autorisée pour ce validateur M-001: seule la bibliothèque standard est utilisée.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| AST Python via bibliothèque standard | Retenue | Contrôle précis des imports sans dépendance tierce et cohérent avec le code analysé. |
| Analyse textuelle PowerShell | Rejetée | Trop fragile pour les imports relatifs, alias et formes syntaxiques Python. |
| Dépendance tierce de lint/import graph | Rejetée | Ajoute une surface supply chain non nécessaire pour M-001. |

## Conséquences

### Positives

- Le validateur d'architecture inspecte une syntaxe Python réelle.
- L'absence de Python produit un RED explicite.
- Les gates PowerShell restent les points d'entrée canoniques.

### Négatives ou coûts

- Les postes exécutant M-001 doivent disposer de Python 3.10 ou supérieur.
- Le wrapper PowerShell porte un préflight de version supplémentaire.

### Risques et contrôles

- Risque: Python absent mais gate GREEN. Contrôle: préflight `Get-Command python` et version minimale.
- Risque: dépendance applicative déguisée. Contrôle: bibliothèque standard uniquement et documentation dans les préconditions de validation.
- Risque: chemin de validation détourné. Contrôle: confinement des chemins sous le dépôt.

## Impact d'implémentation

- Modules concernés: `scripts/validate_architecture_boundaries.ps1`, `scripts/validate_architecture_boundaries.py`.
- Configuration concernée: `PATH` doit résoudre `python`.
- Tests attendus: `tests/m001/validate_architecture_boundaries_unit.ps1`.
- Milestones concernées: M-001.

## Liens de traçabilité

- Spécification: `docs/specs/m001_frontieres_ddd_contrats_publies.md`.
- Plan d'implémentation: `docs/tasks/milestone_001/0010_interdire_couplages_intercontextes.md`.
- Tests d'acceptation: `tests/m001/validate_architecture_boundaries_acceptance.ps1`.
- Commits: corrections de revue M-001.
