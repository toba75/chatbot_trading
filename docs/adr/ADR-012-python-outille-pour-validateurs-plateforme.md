# ADR-012 - Python outillé pour les validateurs de plateforme

**Statut :** Acceptée
**Date :** 2026-06-25
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** `docs/tasks/milestone_002/0003_declarer_topologie_docker_spark.md`, `docs/tasks/milestone_002/0004_configurer_stack_docker_locale.md`, `docs/tasks/milestone_002/0009_verrouiller_frontiere_reseau_locale.md`, revue M-002

## Contexte

M-002 ajoute des validateurs de plateforme qui doivent lire des structures JSON, YAML Compose et politiques réseau. Ces contrôles demandent un parseur déterministe et des structures de données plus fiables qu'une analyse textuelle PowerShell.

ADR-010 conserve les scripts PowerShell comme points d'entrée canoniques des gates. ADR-011 autorise déjà Python standard-library pour un validateur d'architecture M-001. M-002 étend ce principe aux validateurs de plateforme sans ajouter de dépendance applicative ni de bibliothèque tierce.

## Décision

Les gates PowerShell PEUVENT appeler un validateur Python standard-library pour contrôler les artefacts de plateforme M-002 lorsque le contrôle exige un parsing structuré.

Les wrappers PowerShell DOIVENT vérifier explicitement la présence de Python et la version minimale `3.10` via `scripts/require_python.ps1` avant d'exécuter le code Python.

Le wrapper NE DOIT PAS retourner GREEN si l'interpréteur Python est absent, trop ancien, non résolu, ou si le code de sortie du processus Python est absent.

Aucune dépendance tierce Python n'est autorisée pour les validateurs de plateforme M-002. La validation DOIT rester locale, déterministe et appelée depuis les gates PowerShell.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Python standard-library appelé par wrapper PowerShell | Retenue | Parsing structuré JSON/YAML restreint et règles réseau sans dépendance tierce. |
| Analyse textuelle PowerShell seule | Rejetée | Trop fragile pour les structures imbriquées Compose, les listes et les politiques de flux. |
| Bibliothèque tierce YAML ou réseau | Rejetée | Surface supply chain non nécessaire pour le périmètre M-002. |

## Conséquences

### Positives

- Les validateurs M-002 manipulent des structures explicites au lieu de chaînes ad hoc.
- L'absence de Python produit un RED explicite.
- Les points d'entrée opérationnels restent les scripts PowerShell gouvernés par ADR-010.

### Négatives ou coûts

- Les postes exécutant les gates M-002 doivent disposer de Python 3.10 ou supérieur.
- Les wrappers PowerShell portent une vérification de runtime supplémentaire.

### Risques et contrôles

- Risque: Python absent mais gate GREEN. Contrôle: `scripts/require_python.ps1` bloque avant l'exécution du validateur.
- Risque: dépendance applicative déguisée. Contrôle: bibliothèque standard uniquement et usage limité aux scripts de validation.
- Risque: parsing YAML incomplet. Contrôle: sous-ensemble YAML strict documenté par les tests M-002 et refus explicite des formes non supportées.

## Impact d'implémentation

- Modules concernés: `scripts/validate_platform_topology.ps1`, `scripts/validate_local_compose.ps1`, `scripts/validate_network_boundary.ps1`, `app/platform/topology.py`, `app/platform/local_compose.py`, `app/platform/security/network_boundary.py`.
- Configuration concernée: `PATH` doit résoudre `python`.
- Tests attendus: `tests/m002/validate_platform_topology_acceptance.ps1`, `tests/m002/validate_local_compose_acceptance.ps1`, `tests/m002/validate_network_boundary_acceptance.ps1`.
- Milestones concernées: M-002.

## Liens de traçabilité

- Spécification: `docs/specs/m002_plateforme_locale_sure.md`.
- Plan d'implémentation: `docs/tasks/milestone_002/0003_declarer_topologie_docker_spark.md`, `docs/tasks/milestone_002/0004_configurer_stack_docker_locale.md`, `docs/tasks/milestone_002/0009_verrouiller_frontiere_reseau_locale.md`.
- Tests d'acceptation: `tests/m002/validate_platform_topology_acceptance.ps1`, `tests/m002/validate_local_compose_acceptance.ps1`, `tests/m002/validate_network_boundary_acceptance.ps1`.
- Commits: corrections de revue M-002.
