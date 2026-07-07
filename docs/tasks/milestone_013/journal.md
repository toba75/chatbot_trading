# Journal M-013 - Durcissement et acceptation V1

## Prévol de planification

- Branche de planification: `codex/plan-m013-durcissement-acceptation-v1`.
- Base utilisée: `master` et `origin/master` à `5ef94d942bda6ad0f3ceb29de4973fe6ac05d9c1`.
- Précondition amont: M-012 est présent dans `master` avec `docs/tasks/milestone_012`, `docs/specs/m012_evaluation_pilote_calibration.md`, `scripts/validate_m012_precondition.ps1`, `scripts/validate_m012_specification.ps1`, `scripts/validate_m012_traceability.ps1`, `tests/m012`, `app/evaluation`, `docs/governance/m012_v1_gap_report.md` et `docs/traceability/matrix.md`.
- `scripts/validate_task_system.ps1`: GREEN avant création de M-013 avec `13 milestone(s), 134 tâche(s) contrôlée(s)`.
- `scripts/lint.ps1`: GREEN avant création de M-013 avec `24 validation(s), 0 test(s)`.
- `scripts/test.ps1`: RED avant création de M-013 sur `tests/m003/validate_m003_precondition_acceptance.ps1` avec `La précondition M-003 doit être GREEN sur la base courante. Code obtenu: 1`; T-001 porte la récupération de cette précondition pour M-013.

## Sources normatives

- `docs/specs/plan_implementation_milestones_workstreams.md`, M-013.
- `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 18, 19, 20, 21, 22, 23 et 24.
- `docs/governance/m012_v1_gap_report.md`.
- ADR-007, ADR-008, ADR-009, ADR-010, DDD-ADR-006, DDD-ADR-010 et DDD-ADR-011.

## Découpage initial

- T-001 vérifie et rétablit la précondition GREEN M-013.
- T-002 publie la spécification de durcissement et acceptation V1.
- T-003 contrôle les écarts V1 issus de M-012.
- T-004 construit la suite de régression V1.
- T-005 audite la frontière réseau Spark.
- T-006 éprouve les pannes Spark sans fallback.
- T-007 valide les sauvegardes chiffrées et la restauration.
- T-008 décide la rétention et la purge administrative.
- T-009 publie le monitoring local d'exploitation.
- T-010 publie les runbooks et la documentation utilisateur.
- T-011 vérifie les anti-patterns interdits V1.
- T-012 publie le rapport d'acceptation V1.

## Écarts V1 hérités de M-012

- SP: `différé`, qualité documentaire, formules, cellules, temps, mémoire et stabilité.
- KA: `différé`, rappel pilote sous seuil pour la recherche de connaissances.
- EG: `satisfait`, gouvernance des preuves séparée de RA.
- RA: `différé`, abstention correcte et réponses vérifiées à renforcer.
- CV: `satisfait`, conversation, suivi, routage de mode et absence d'usage factuel de l'historique brut.
- SD: `bloquant`, paramètres sans plan de calibration.
- LLM: `bloquant`, checkpoint principal non promu sur toutes les tâches obligatoires.
- EX: `satisfait`, backtests pilotes reproductibles et résultats négatifs conservés.

## Règles d'exécution

- Chaque tâche conserve le flux BDD, ATDD et TDD.
- Le commit RED contient uniquement scénario, spécification, ADR éventuelle et test RED.
- Le commit GREEN contient l'implémentation stricte et les ajustements nécessaires.
- Aucune valeur par défaut, aucun fallback silencieux et aucune décision implicite ne sont acceptés.
- Toute nouvelle décision structurante crée une ADR à partir de `docs/adr/TEMPLATE.md` et met à jour `docs/adr/index.md`.

## Revue d'adhérence et corrections ciblées

- T-005 précise désormais que le point d'entrée utilisateur `docker-local` doit être lié à `127.0.0.1` par défaut et refuse tout binding `0.0.0.0` hors profil explicitement documenté.
- T-006 couvre désormais l'ouverture et la fermeture du circuit breaker, ainsi que le maintien des fonctions locales qui ne nécessitent pas Gemma pendant une panne Spark.
- T-009 couvre désormais le profil de ressources V1: optimisation Gemma sur DGX Spark, capacité CPU/GPU/I/O sur `docker-local`, digest ou version de l'image vLLM, révision du modèle, concurrence et longueur de contexte justifiées par benchmark.

## Exécution T-002

- RED: ajout de `tests/m013/validate_m013_specification_acceptance.ps1` et `tests/m013/validate_m013_specification_unit.ps1`.
- GREEN: publication de `docs/specs/m013_durcissement_acceptation_v1.md`, création de `scripts/validate_m013_specification.ps1`, enrôlement dans `scripts/test.ps1` et `scripts/lint.ps1`, et rattachement `REQ-M013-002` dans `docs/traceability/matrix.md`.
- ADR: non requise; T-002 applique ADR-007, ADR-008, ADR-009, ADR-010, DDD-ADR-006, DDD-ADR-010 et DDD-ADR-011 sans imposer de nouvelle politique de rétention, sans rendre mTLS obligatoire et sans remplacer la topologie existante.

## Exécution T-003

- RED: ajout de `tests/m013/validate_v1_gap_decisions_acceptance.ps1` et `tests/m013/validate_v1_gap_decisions_unit.ps1`; commit RED `2c697fb7e`.
- GREEN: publication de `app/evaluation/domain/v1_gap_decisions.py`, `docs/governance/m013_v1_gap_decisions.md` et `scripts/validate_m013_v1_gap_decisions.ps1`; enrôlement dans `scripts/test.ps1` et `scripts/lint.ps1`; rattachement `REQ-M013-003` dans `docs/traceability/matrix.md`.
- Décision livrée: SP, KA et RA restent `différé`; SD et LLM restent `bloquant`; EG, CV et EX sont explicitement `accepté`; les cinq écarts non acceptés sont transmis au futur `V1AcceptanceReport`.
- ADR: non requise; T-003 applique ADR-010 et DDD-ADR-011 sans changer critère d'acceptation, politique de calibration ou frontière de bounded context.
