# Journal M-011 - Expérience reproductible

## État initial

- Branche de planification: `codex/plan-m011-experience-reproductible`.
- Base vérifiée: `master` et `origin/master` à `3606b54e65dea73d10bd2af3039c981a9ab37335`.
- Milestone amont requis: M-010 présent dans `master`.
- Gates rapides avant création: `scripts/validate_task_system.ps1` GREEN avec `11 milestone(s), 110 tâche(s) contrôlée(s)`; `scripts/lint.ps1` GREEN avec `20 validation(s), 0 test(s)`.
- Test global avant création: `scripts/test.ps1` RED sur `tests/m003/validate_m003_precondition_acceptance.ps1`, car les validateurs de précondition amont autorisent les branches aval jusqu'à M-010 mais pas encore une branche M-011; T-001 porte cette récupération de précondition.
- Gates après création: `scripts/validate_task_system.ps1` GREEN avec `12 milestone(s), 122 tâche(s) contrôlée(s)`; `scripts/lint.ps1` GREEN avec `20 validation(s), 0 test(s)`; `git diff --check` GREEN.
- Test global après création: `scripts/test.ps1` RED sur `tests/m003/validate_m003_precondition_acceptance.ps1` avec `La précondition M-003 doit être GREEN sur la base courante. Code obtenu: 1`; le RED reste porté par T-001.

## Découpage

- T-001 vérifie et rétablit la précondition GREEN M-011.
- T-002 publie la spécification détaillée M-011.
- T-003 planifie une expérience depuis un `StrategySnapshot` et l'inscrit dans `ExperimentRepository`.
- T-004 fige le snapshot de données point-in-time.
- T-005 fige le modèle de coûts et l'environnement d'exécution.
- T-006 planifie, annule ou démarre l'expérience avec entrées verrouillées et transitions append-only.
- T-007 exécute le backtest déterministe.
- T-008 enregistre un résultat d'expérience immuable et la transition terminale dans le registre append-only.
- T-009 conserve les résultats négatifs et les échecs.
- T-010 reproduit une expérience avec les mêmes entrées et couvre `CompareExperiments`.
- T-011 expose les endpoints de backtest et d'expériences.
- T-012 relie M-011 aux métriques, à la traçabilité et aux gates.

## Exécution

- À renseigner pendant l'implémentation M-011.

## Revue d'adhérence

- Findings de revue résolus après planification:
  - T-006 couvre désormais `ExperimentScheduler`, `ExperimentScheduled`, `CancelExperiment`, `ExperimentCancelled` et la transition `SCHEDULED -> CANCELLED`.
  - T-008 couvre désormais les séries temporelles, positions, transactions, avertissements, logs, références hashées et le contexte d'interprétation des métriques.
  - T-010 vérifie désormais l'empreinte des paramètres du `StrategySnapshot` dans la reproduction.
  - T-003, T-006 et T-008 couvrent désormais `ExperimentRepository`, le registre append-only des expériences, l'interdiction de suppression et l'absence de réécriture des transitions.
  - T-010 et T-012 couvrent désormais `CompareExperiments` et `ExperimentComparisonCompleted` comme contrat EX explicite.
  - T-009 couvre désormais la correction d'un résultat invalidé par création d'une nouvelle expérience liée, sans réutiliser le même `ExperimentId`.
  - T-007 et T-012 couvrent désormais les contrôles minimaux de backtest M-011 comme checklist traçable, sans report implicite vers M-012.
