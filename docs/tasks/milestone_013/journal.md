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

## Exécution T-004

- RED: ajout de `tests/m013/validate_v1_regression_suite_acceptance.ps1`; commit RED `1a890109c`.
- GREEN: publication de `docs/evaluation/m013/v1_regression_suite.json`, création de `scripts/validate_m013_regression.ps1`, ajout de `tests/m013/validate_v1_regression_suite_unit.ps1`, enrôlement dans `scripts/test.ps1` et `scripts/lint.ps1`, alignement du comportement V1-003 dans la spécification M-013, et rattachement `REQ-M013-004` dans `docs/traceability/matrix.md`.
- Décision livrée: la suite couvre huit critères V1 et dix parcours produit; EG, CV et EX obtiennent un verdict logiciel `GREEN`; SP, KA, RA, SD et LLM restent des écarts non acceptés visibles et reliés au rapport M-012.
- Limite explicite: T-004 ne corrige pas les tests scientifiques RED M-012 et ne rend pas la V1 acceptable tant que SD et LLM restent bloquants.
- ADR: non requise; T-004 applique ADR-010 et DDD-ADR-011 sans changer la politique d'exécution des gates ni la propriété EV des écarts V1.

## Exécution T-005

- RED: ajout de `tests/m013/validate_m013_network_security_acceptance.ps1`; commit RED `2b32c6c1f`.
- GREEN: publication de `docs/governance/m013_security_audit.md`, création de `scripts/validate_m013_security.ps1`, ajout de `tests/m013/validate_m013_network_security_unit.ps1`, enrôlement dans `scripts/test.ps1` et `scripts/lint.ps1`, alignement du comportement V1-004 dans la spécification M-013, et rattachement `REQ-M013-005` dans `docs/traceability/matrix.md`.
- Décision livrée: le point d'entrée utilisateur reste lié à `127.0.0.1` par défaut; aucun service interne n'est publié; le navigateur, les workers, les stockages et Internet ne peuvent pas joindre Spark; seul `llm-gateway -> spark-inference` est autorisé avec TLS, certificat et clé API par fichier secret.
- ADR: non requise; T-005 applique ADR-007, ADR-008 et ADR-009 sans remplacer la topologie locale, sans changer le chemin LLM et sans rendre mTLS obligatoire.

## Exécution T-006

- RED: ajout de `tests/m013/validate_spark_failure_acceptance.ps1`; commit RED `10f3c94c8`.
- GREEN: publication de `app/platform/llm_gateway/spark_failure_drill.py`, `docs/governance/m013_spark_failure_drill.md` et `scripts/validate_m013_spark_failures.ps1`; ajout de `tests/m013/validate_spark_failure_unit.ps1`; enrôlement dans `scripts/test.ps1` et `scripts/lint.ps1`; rattachement `REQ-M013-006` dans `docs/traceability/matrix.md`.
- Décision livrée: les pannes Spark produisent `LLM_UNAVAILABLE` ou un diagnostic explicite, ne publient aucune réponse factuelle incomplète, ne snapshotent aucune stratégie, ne promeuvent aucun benchmark LLM, n'appellent aucun provider alternatif, interdisent le retry après premier token et exposent le circuit breaker ouvrable et refermable.
- Garde-fous conservés: les fonctions locales hors Gemma restent disponibles, les métriques ne contiennent aucun prompt complet et l'outbox reste idempotente sans double publication.
- ADR: non requise; T-006 applique ADR-008, ADR-009 et DDD-ADR-006 sans changer le chemin LLM principal et sans introduire de nouveau mode de dégradation fonctionnelle.

## Exécution T-007

- RED: ajout de `tests/m013/validate_backup_restore_acceptance.ps1`, `tests/m013/validate_backup_restore_unit.ps1` et `docs/adr/ADR-013-contrat-manifeste-sauvegarde-restauration.md`; commit RED `572140b47`.
- GREEN: publication de `app/platform/backup_restore.py`, `docs/governance/m013_backup_restore_drill.md` et `scripts/validate_m013_backup_restore.ps1`; enrôlement dans `scripts/test.ps1` et `scripts/lint.ps1`; rattachement `REQ-M013-007` dans `docs/traceability/matrix.md`.
- Décision livrée: la V1 utilise le manifeste `M013-BackupManifest-1.0`, vérifie les hashes restaurés, garde la clé hors dépôt, refuse les secrets versionnés, conserve les résultats négatifs et supersédés, traite Qdrant comme projection régénérable non autorité et confirme qu'aucune donnée métier n'est restaurée sur Spark.
- Garde-fous conservés: aucune sauvegarde partielle déclarée complète, aucune restauration destructive silencieuse et aucun `restore_test_result` sans commande de restauration.
- ADR: ADR-013 créée pour le contrat durable de manifeste de sauvegarde et restauration; T-007 applique aussi ADR-009, DDD-ADR-004 et DDD-ADR-010.

## Exécution T-008

- RED: ajout de `tests/m013/validate_retention_purge_acceptance.ps1`, `tests/m013/validate_retention_purge_unit.ps1` et `docs/adr/DDD-ADR-012-politique-retention-purge-administrative-v1.md`; commit RED `4a38c072c`.
- GREEN: publication de `app/platform/retention.py`, `docs/governance/m013_retention_policy.md` et `scripts/validate_m013_retention.ps1`; enrôlement dans `scripts/test.ps1` et `scripts/lint.ps1`; alignement de la spécification M-013, des compteurs M-012 et rattachement `REQ-M013-008` dans `docs/traceability/matrix.md`.
- Décision livrée: la V1 conserve les artefacts d'autorité hors conversation pendant 120 mois, les conversations pendant 18 mois et les projections régénérables pendant 3 mois; toute purge administrative exige justification, audit, opérateur, date, identifiants stables et preuve de compatibilité de lecture.
- Garde-fous conservés: aucune purge ordinaire, aucun effacement de résultat négatif ou supersédé, aucune cascade CV vers KA, EG, RA, SD ou EX, et aucune purge de projection sans commande de reconstruction depuis les artefacts d'autorité conservés.
- ADR: DDD-ADR-012 créée pour la politique V1 de rétention et purge administrative; T-008 ne modifie pas le sens de DDD-ADR-010.
