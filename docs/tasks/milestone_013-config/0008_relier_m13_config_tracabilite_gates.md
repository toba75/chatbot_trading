# T-008 - Relier M13-config à la traçabilité et aux gates

## Milestone

- Nom: M13-config - Configuration applicative sans environnement.
- Source: ADR-016; `docs/specs/plan_implementation_milestones_workstreams.md`; définition d'achèvement transverse.
- Objectif métier: clôturer le sous-milestone avec des preuves rejouables et empêcher l'acceptation V1 si la configuration repasse par l'environnement.

## Contexte DDD

- Domaine: gouvernance, évaluation et exploitation V1.
- Bounded context: transverse, EV, `platform`.
- Objectif métier: rendre la décision `M13-config` visible dans la matrice de traçabilité, les rapports de gouvernance et les gates finales.
- Langage ubiquitaire: exigence M13-config, preuve de gate, audit de configuration, V1 non acceptable, absence de fallback, rapport de clôture.
- Invariants critiques: l'exigence ADR-016 est reliée à tests, code, documentation et rapport; une violation de configuration bloque les gates; les preuves synthétiques ne suffisent pas.
- Garde-fous: ne pas déclarer M-013 clôturé par ce sous-milestone; ne pas accepter une V1 dont un processus lit l'environnement applicatif.

## Blocages Ou Préconditions

- État GREEN/RED connu: T-001 à T-007 doivent être GREEN.
- Présence des milestones amont dans master: M-000 à M-012 visibles dans `master`.
- Décisions manquantes: aucune.
- Risques: livrer la migration technique sans traçabilité, ou faire croire que `M13-config` clôture tout M-013.

## Tâches

### T-008 - Relier M13-config à la traçabilité et aux gates

- But métier: prouver que l'interdiction de variables d'environnement est contrôlée par les gates du dépôt et visible dans les rapports V1.
- Portée DDD: `docs/traceability/matrix.md`, gouvernance M13-config, scripts de validation, journal de sous-milestone, rapport d'audit.
- Scénario BDD:
  - Given les tâches M13-config ont migré configuration, gateway, Compose, scans et runbooks.
  - When les gates de traçabilité et de lint sont exécutées.
  - Then chaque exigence ADR-016 est reliée à une preuve et toute régression d'environnement bloque la validation.
- Tests d'acceptation à écrire: `tests/m013_config/validate_m013_config_traceability_acceptance.ps1`, couvrant exigences, tests, scripts, docs, ADR-016, rapport d'audit et absence de clôture implicite de M-013.
- Tests unitaires à écrire: `tests/m013_config/validate_m013_config_traceability_unit.ps1`, couvrant mapping exigence-test-code-doc, comptage des validations enrôlées, et refus d'une preuve manquante.
- Implémentation attendue: créer `docs/governance/m013_config_audit.md`, `scripts/validate_m013_config_traceability.ps1`, enrôler les validations M13-config dans `scripts/test.ps1` et `scripts/lint.ps1`, mettre à jour `docs/traceability/matrix.md` et compléter `docs/tasks/milestone_013-config/journal.md`.
- Invariants et garde-fous: aucune clôture automatique de M-013; aucune exigence ADR-016 sans test; aucun rapport V1 acceptant une configuration par environnement.
- Dépendances: T-001 à T-007; ADR-016; `scripts/validate_traceability.ps1`; `scripts/lint.ps1`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_m013_config_traceability_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_m013_config_traceability_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_config_traceability.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(governance): couvrir tracabilite m13 config`.
- Commit GREEN: `docs(governance): relier m13 config aux gates`.
