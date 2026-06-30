# Journal M-007

## Planification initiale

- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, milestone `M-007 - Réponse documentaire vérifiée`.
- Dépendance amont: M-006, présent dans `master` au commit `236c2420a84c0439e8d1c101eb2251ba44069fa9`, identique à `origin/master` après `git fetch origin --prune`.
- Précondition observée pendant la planification: `scripts/test.ps1` a expiré une première fois à 904 secondes puis a conclu GREEN après relance large avec `15 validation(s), 134 test(s)`; `scripts/lint.ps1` GREEN avec `15 validation(s), 0 test(s)`; `scripts/validate_task_system.ps1` GREEN avec `7 milestone(s), 67 tâche(s) contrôlée(s)` avant création de M-007; `git diff --check` GREEN.
- Découpage retenu: précondition, spécification RA, cas de recherche avec mandat, jeu de preuves scellé, contradictions et lacunes, extraction d'assertions, support et citations, abstention pour données actuelles, commande `POST /v1/answer`, puis traçabilité et métriques.
- ADR: aucune nouvelle ADR planifiée à ce stade; les tâches appliquent les ADR existantes et exigent une nouvelle ADR si une décision structurante change le contrat public RA, la politique durable de fraîcheur ou le stockage des preuves.

## Clôture T-010 - métriques, traçabilité et gates

- Scénario BDD: Given les comportements M-007 sont implémentés et testés; When la matrice de traçabilité et les gates sont exécutés; Then chaque exigence M-007 est rattachée à un test GREEN, une commande de validation et une ADR ou justification explicite.
- ADR: non requise; T-010 applique localement `ADR-006`, `ADR-010`, `DDD-ADR-005` et `DDD-ADR-008` sans introduire de solution d'observabilité durable, de dépendance externe ou de stockage métrique.
- Commit RED: `5ab39d2e` (`test(m007): couvrir tracabilite metriques gates`).
- Preuves livrées: `app/research_answering/application/traceability_metrics.py`, `tests/m007/validate_m007_traceability_acceptance.ps1`, `tests/m007/validate_m007_traceability_unit.ps1`, `tests/m007/fixtures/m007_response_metrics_fixture.json`, `docs/governance/m007_response_metrics.json`, matrice M-007 complète et enrôlement de tous les tests M-007 dans `scripts/test.ps1`.
- Garde-fous vérifiés: les métriques RA publient des compteurs, statuts, hashes et identifiants; elles ne publient ni prompt, ni brouillon, ni réponse complète, ni texte documentaire complet; le nombre de citations reste un compteur et n'est jamais interprété comme consensus documentaire.
