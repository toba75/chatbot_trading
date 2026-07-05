# Journal M-012 - Évaluation pilote et calibration

## État initial

- Branche de planification: `codex/plan-m012-evaluation-pilote-calibration`.
- Base vérifiée: `master` et `origin/master` à `0a166827f921ec769e16462891aa8cebd0f7f299`.
- Milestone amont requis: M-011 présent dans `master`.
- Preuve de présence M-011: 54 entrées observées sous `docs/tasks/milestone_011`, `docs/specs/m011_experience_reproductible.md`, `scripts/validate_m011_precondition.ps1`, `scripts/validate_m011_specification.ps1`, `scripts/validate_m011_traceability.ps1`, `tests/m011`, `app/experimentation` et `app/contracts/strategy_experiments.py`.
- Gates rapides avant création: `scripts/validate_task_system.ps1` GREEN avec `12 milestone(s), 122 tâche(s) contrôlée(s)`; `scripts/lint.ps1` GREEN avec `22 validation(s), 0 test(s)`.
- Test global avant création: `scripts/test.ps1` RED sur `tests/m003/validate_m003_precondition_acceptance.ps1` avec `La précondition M-003 doit être GREEN sur la base courante. Code obtenu: 1`; T-001 porte cette récupération de précondition pour M-012.
- Gates après création: `scripts/validate_task_system.ps1` GREEN avec `13 milestone(s), 134 tâche(s) contrôlée(s)`; `scripts/lint.ps1` GREEN avec `22 validation(s), 0 test(s)`; `git diff --check` GREEN.
- Test global après création: `scripts/test.ps1` RED sur `tests/m003/validate_m003_precondition_acceptance.ps1` avec `La précondition M-003 doit être GREEN sur la base courante. Code obtenu: 1`; le RED reste porté par T-001.

## Découpage

- T-001 vérifie et rétablit la précondition GREEN M-012.
- T-002 publie la spécification détaillée d'évaluation pilote.
- T-003 constitue le corpus pilote représentatif.
- T-004 publie le jeu annoté page par page.
- T-005 mesure les routes documentaires.
- T-006 calibre les seuils de conversion canonique.
- T-007 mesure la recherche de connaissances.
- T-008 mesure les réponses vérifiées et l'abstention.
- T-009 mesure le LLM principal par le chemin réel.
- T-010 mesure les stratégies et backtests pilotes.
- T-011 publie les décisions de calibration et de promotion.
- T-012 relie M-012 aux écarts V1, à la traçabilité et aux gates.

## Exécution

- À compléter pendant l'implémentation M-012.

## Revue d'adhérence

- Findings de revue résolus après planification:
  - T-002, T-011 et T-012 couvrent désormais explicitement les métriques et décisions EG/SD exigées par la section 19 de la spécification v4.1, en plus de SP, KA, RA, LLM et EX.
  - T-003 énumère désormais les strates normatives du corpus pilote: PDF numériques propres, scans propres, scans inclinés, scans bruités, anciennes couches OCR défectueuses, documents mixtes, textes français et anglais, tableaux financiers, équations, graphiques, colonnes multiples et éditions différentes.
  - T-003 rend désormais toute strate normative manquante bloquante: une absence ne peut plus être justifiée comme GREEN et doit rester RED avec écart V1 explicite.
  - T-008 produit désormais le benchmark EG avec taux de claims vérifiés, rejetés et en revue, affirmations sans preuve directe, distribution des verdicts, groupes de dépendance, supersession et délai de vérification.
  - T-010 produit désormais les métriques SD de la section 19: stratégies compilables, raisons de rejet, origines de règles, paramètres sans plan de calibration, conflits de compatibilité et versions par stratégie.
  - T-005 verrouille désormais toutes les métriques documentaires normatives dans les tests RED: CER/WER, exactitude numérique, signes, formules, cellules, ordre de lecture, temps par page, mémoire et stabilité.
  - T-008 couvre désormais les métriques RA obligatoires: statuts `SUPPORTED`, `PARTIALLY_SUPPORTED`, `INSUFFICIENT_EVIDENCE` et `CONFLICTING_EVIDENCE`, assertions non supportées retirées, couverture des obligations de recherche et réponses réutilisant une version obsolète.
  - T-009 verrouille désormais toutes les tâches obligatoires du benchmark LLM et leurs métriques techniques séparées avant toute décision de promotion.
  - T-011 et T-012 relient désormais les métriques RA, les tâches LLM obligatoires et les métriques documentaires normatives aux décisions, à la traçabilité et au rapport d'écarts V1.
  - T-002, T-011 et T-012 couvrent désormais explicitement CV par les critères de conversation, suivi, routage de mode et absence d'usage factuel de l'historique brut, au lieu de limiter le rapport final à SP, KA, EG, RA, SD, LLM et EX.
  - T-012 ne déclare plus M-013 comme dépendance d'implémentation; M-013 est seulement le consommateur aval du rapport d'écarts V1 produit par M-012.
  - T-009 distingue désormais les retries LLM bornés avant premier token, mesurés et idempotents, des retries après premier token ou illimités qui restent interdits.
