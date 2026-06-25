# Journal M-002 - Plateforme locale sûre

## Source

- Plan: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M-002 - Plateforme locale sûre`.
- Spécification normative: `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 13, 15, 16, 18, 19, 20 et 21.
- ADR applicables: ADR-007, ADR-008, ADR-009, DDD-ADR-006, DDD-ADR-008, DDD-ADR-007.

## Tâches planifiées

| Tâche | Statut initial | RED prévu | GREEN prévu | ADR |
|---|---|---|---|---|
| T-001 - Vérifier la précondition GREEN de M-002 | Planifiée | `test(m002): couvrir la précondition green de plateforme` | `docs(m002): valider la précondition green de plateforme` | ADR-010 |
| T-002 - Publier la spécification de plateforme locale sûre | Planifiée | `test(m002): couvrir la spécification de plateforme locale` | `docs(m002): publier la spécification de plateforme locale` | ADR-007; ADR-008; ADR-009; DDD-ADR-006; DDD-ADR-008 |
| T-003 - Déclarer la topologie docker-local et spark-inference | Planifiée | `test(m002): couvrir la topologie docker spark` | `feat(m002): déclarer la topologie docker spark` | ADR-007; ADR-009 |
| T-004 - Configurer la stack Docker locale contrôlée | Planifiée | `test(m002): couvrir la stack docker locale` | `feat(m002): configurer la stack docker locale` | ADR-007; ADR-008; ADR-009 |
| T-005 - Publier le contrat du gateway LLM | Planifiée | `test(m002): couvrir le contrat gateway llm` | `feat(m002): publier le contrat gateway llm` | ADR-008; ADR-009 |
| T-006 - Contrôler les pannes d'inférence Spark | Planifiée | `test(m002): couvrir les pannes inference spark` | `feat(m002): controler les pannes inference spark` | ADR-008; ADR-009; DDD-ADR-007 |
| T-007 - Livrer l'outbox d'événements idempotente | Planifiée | `test(m002): couvrir outbox et idempotence` | `feat(m002): livrer outbox idempotente` | DDD-ADR-006; DDD-ADR-008 |
| T-008 - Livrer la file de jobs priorisée et idempotente | Planifiée | `test(m002): couvrir la file de jobs idempotente` | `feat(m002): livrer la file de jobs idempotente` | Non requise à ce stade |
| T-009 - Verrouiller la frontière réseau locale | Planifiée | `test(m002): couvrir la frontiere reseau locale` | `feat(m002): verrouiller la frontiere reseau locale` | ADR-007; ADR-008; ADR-009 |
| T-010 - Observer le gateway sans payloads complets | Planifiée | `test(m002): couvrir observabilite gateway` | `feat(m002): observer le gateway sans payloads` | ADR-008; ADR-009 |
| T-011 - Relier M-002 à la traçabilité et aux gates | Planifiée | `test(m002): couvrir la tracabilite plateforme` | `docs(m002): relier m002 aux gates et a la tracabilite` | ADR-010 |

## Précondition observée à la planification

- Branche de planification: `codex/milestone-m002-plateforme-locale-sure`.
- `master`: `35a5765`.
- `scripts/test.ps1`: GREEN, 7 validations et 31 tests.
- `scripts/lint.ps1`: GREEN, 7 validations.
- Milestones amont dans `master`: `docs/tasks/milestone_000` et `docs/tasks/milestone_001`.

## Suivi d'exécution

- Statut: T-001 livrée en GREEN; la précondition M-002 refuse `master` absent, milestone amont absent, gate RED et branche locale non alignée sur `master`.

| Tâche | Commit RED | Commit GREEN | ADR consultées | ADR créée ou modifiée | Validations GREEN déclarées |
|---|---|---|---|---|---|
| T-001 - Vérifier la précondition GREEN de M-002 | `ff51415` | Commit courant `docs(m002): valider la précondition green de plateforme` | ADR-010 | Aucune | `tests/m002/validate_m002_precondition_acceptance.ps1`; `tests/m002/validate_m002_precondition_unit.ps1`; `scripts/validate_m002_precondition.ps1 -Path .\docs\governance\m002_precondition_green.md`; `scripts/validate_traceability.ps1`; `scripts/test.ps1`; `scripts/lint.ps1` |
| T-002 - Publier la spécification de plateforme locale sûre | `b7de11257d726e165d5dfb59f905d08ca30df979` | Commit courant `docs(m002): publier la spécification de plateforme locale` | ADR-007; ADR-008; ADR-009; DDD-ADR-006; DDD-ADR-008; ADR-010 | Aucune | `tests/m002/validate_m002_specification_acceptance.ps1`; `tests/m002/validate_m002_specification_unit.ps1`; `scripts/validate_m002_specification.ps1`; `scripts/validate_traceability.ps1`; `scripts/test.ps1`; `scripts/lint.ps1` |

## Clôture T-001

- Scénario BDD: Given M-000 et M-001 sont présents dans `master`; When les gates de validation sont exécutées avant la première tâche M-002; Then M-002 peut commencer uniquement si les tests, la lint, la traçabilité, les ADR et les frontières d'architecture sont GREEN.
- RED T-001 confirmé: `tests/m002/validate_m002_precondition_acceptance.ps1` échouait sur l'absence de `scripts/validate_m002_precondition.ps1`.
- ADR: aucune ADR créée ou modifiée; T-001 applique ADR-010 sans changer la politique durable des gates PowerShell.
- Risque traité: la précondition M-002 ne bascule pas vers une branche remote et refuse une base locale non alignée avant toute livraison de plateforme.

## Clôture T-002

- Scénario BDD: Given la spécification v4.1 impose deux plans physiques et une cohérence éventuelle par outbox; When la spécification M-002 est publiée; Then chaque règle de plateforme nomme le comportement attendu, les invariants, les tests et les ADR qui la gouvernent.
- RED T-002 confirmé: `tests/m002/validate_m002_specification_acceptance.ps1` échouait sur l'absence de `scripts/validate_m002_specification.ps1`.
- Implémentation documentaire: `docs/specs/m002_plateforme_locale_sure.md` publie le langage de plateforme, les placements `docker-local` et `spark-inference`, le gateway LLM unique, l'outbox transactionnelle, les jobs priorisés, les pannes explicites, l'observabilité technique et les commandes de validation.
- Validateur livré: `scripts/validate_m002_specification.ps1` refuse section manquante, ADR absente, placement incohérent, fallback silencieux et endpoint Spark codé en dur.
- ADR: aucune ADR créée ou modifiée; T-002 applique ADR-007, ADR-008, ADR-009, DDD-ADR-006, DDD-ADR-008 et ADR-010 sans changer leur sens.
- Hors périmètre confirmé: aucun Compose, gateway, outbox runtime, file de jobs, règle réseau ou observabilité runtime n'est implémenté par T-002.
