# ADR-048 - Progression et parallélisme dans les profils explicites

**Statut :** Acceptée
**Date :** 2026-07-22
**Décideurs :** Propriétaire du projet
**Remplace :** ADR-031 ; ADR-037
**Remplacée par :** Aucune
**Source :** Revue de clôture M13-environments ; ADR-031 ; ADR-037 ; ADR-046

## Contexte

ADR-031 a rendu obligatoires l'exécution réelle des actions UI asynchrones et
leur progression publique. ADR-037 a fixé le parallélisme documentaire et de
projection. Ces deux décisions désignent toutefois encore `uv run ui` comme
point de démarrage et `config/application.yaml` comme configuration active.
ADR-046 a depuis fermé les points d'entrée opérateur à `development`, `test` et
`production`, sans formaliser la conservation des invariants fonctionnels des
deux décisions antérieures.

## Décision

ADR-048 remplace ADR-031 et ADR-037 en conservant leurs décisions de progression
publique et de parallélisme, mais en retirant leur ancien moyen de lancement.

Une action UI asynchrone NE DOIT être disponible que dans une pile réellement
démarrée par `uv run development`, `uv run test` ou `uv run production`. Sa
chaîne complète API, écriture, outbox, relais, worker, persistance et lecture
publique DOIT être supervisée dans le profil sélectionné. La progression
publique DOIT exposer phase, unités réalisées, total et erreur terminale
éventuelle. L'UI NE DOIT PAS déduire cette progression de logs ou d'un état
local.

Les deux replicas documentaires et les deux replicas de projection DOIVENT
conserver une identité d'instance, un lease et un fencing distincts. Le
parallélisme interne configuré DOIT rester borné par les ressources du profil et
la progression agrégée DOIT provenir des écritures persistées des workers réels.

`uv run ui` et `config/application.yaml` NE SONT PLUS des chemins opératoires.
L'UI demeure un service interne du profil sélectionné et chaque processus lit
uniquement `config/environments/<profil>.yaml` par le raccordement Compose.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Laisser ADR-031 et ADR-037 actives avec `uv run ui` | Rejetée | Maintient un quatrième point d'entrée contradictoire avec ADR-046. |
| Supprimer les clauses de lancement dans les ADR acceptées | Rejetée | Modifierait silencieusement leur sens et leur historique. |
| Les remplacer en réaffirmant progression et parallélisme | Retenue | Préserve les invariants tout en alignant le moyen de lancement sur les trois profils. |

## Conséquences

### Positives

- Les actions UI restent liées à leur chaîne réelle et à leur progression publique.
- Le parallélisme reste explicite, borné et observable par profil.
- Aucun document d'architecture actif n'autorise `uv run ui`.

### Négatives ou coûts

- Les validations documentaires doivent distinguer les références historiques des prescriptions actives.
- Toute preuve live doit nommer le profil et les quatre instances de worker réelles.

### Risques et contrôles

- Risque : réintroduire l'ancien point d'entrée dans un runbook. Contrôle : gate
  statique sur les ADR acceptées, les runbooks actifs et leur index.
- Risque : annoncer une action sans worker réel. Contrôle : cardinalité et identité
  vérifiées dans la gate live, avec progression publique persistée.

## Impact d'implémentation

- Modules concernés : orchestration des profils, API de progression et workers.
- Configuration concernée : `config/environments/*.yaml`.
- Tests attendus : cohérence ADR/runbooks, quatre identités workers, quatorze conteneurs et progression publique réelle.
- Milestones concernées : M-013, M13-environments.

## Liens de traçabilité

- Spécification : `docs/specs/m013_environments_environnements_explicites.md`.
- Plan d'implémentation : section M13-environments de `docs/specs/plan_implementation_milestones_workstreams.md`.
- Tests d'acceptation : `gate_tests/ported/tests/m013_environments/validate_review3_governance_remediation_unit.py`.
- Commits : commit RED puis commit GREEN de la remédiation gouvernance M13-environments.

## Notes

ADR-048 ne modifie ni ADR-046, ni ADR-047, ni ADR-014.
