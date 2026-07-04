# Journal M-010 - Stratégie candidate attribuée

## État initial

- Branche de planification: `codex/milestone-m010-strategie-candidate-attribuee`.
- Base vérifiée: `master` et `origin/master` à `ef419b4c068e958d328262cdf7c5d0f84b9adb92`.
- Milestone amont requis: M-009 présent dans `master`.
- Gates rapides avant création: `scripts/validate_task_system.ps1` GREEN avec `10 milestone(s), 99 tâche(s) contrôlée(s)`; `scripts/lint.ps1` GREEN avec `18 validation(s), 0 test(s)`.
- Gates après création: `scripts/validate_task_system.ps1` GREEN avec `11 milestone(s), 110 tâche(s) contrôlée(s)`; `scripts/lint.ps1` GREEN avec `18 validation(s), 0 test(s)`; `git diff --check` GREEN.
- Test global: `scripts/test.ps1` RED sur `tests/m003/validate_m003_precondition_acceptance.ps1`, car `scripts/validate_m003_precondition.ps1` autorise les branches aval jusqu'à `codex/milestone-m009-recherche-approfondie` mais refuse `codex/milestone-m010-strategie-candidate-attribuee`; T-001 porte cette récupération de précondition.

## Découpage

- T-001 vérifie et rétablit la précondition GREEN M-010.
- T-002 publie la spécification détaillée M-010.
- T-003 ouvre une stratégie candidate depuis un résultat vérifié.
- T-004 attribue les origines des règles de stratégie.
- T-005 contrôle les paramètres à calibrer.
- T-006 analyse la compatibilité de stratégie.
- T-007 valide la stratégie candidate avec diagnostics.
- T-008 compile une stratégie candidate déterministe.
- T-009 crée le snapshot immuable de stratégie.
- T-010 expose les endpoints de stratégie.
- T-011 relie M-010 aux métriques, à la traçabilité et aux gates.

## Exécution

### T-001 - Précondition GREEN M-010

- Commit RED: `938ec5d5 test(m010): couvrir la precondition green strategie candidate`.
- Reprise main-agent: arrêt de l'ancien arbre `scripts/test.ps1` lancé par le worker après plus de 60 minutes sans verdict exploitable.
- Implémentation: création de `scripts/validate_m010_precondition.ps1`, création de `docs/governance/m010_precondition_green.md`, enrôlement des tests M-010 et autorisation explicite de la branche `codex/milestone-m010-strategie-candidate-attribuee` dans les validateurs de précondition M-003 à M-009.
- Validations GREEN: `tests/m010/validate_m010_precondition_unit.ps1`, `scripts/validate_m010_precondition.ps1 -Path .\docs\governance\m010_precondition_green.md`, `tests/m010/validate_m010_precondition_acceptance.ps1`.
- Gate M-010: le rapport canonique `docs/governance/m010_precondition_green.md` consigne `scripts/test.ps1` GREEN avec `18 validation(s), 192 test(s)` et `scripts/lint.ps1` GREEN avec `18 validation(s), 0 test(s)`.
- Contrôle de propreté: `git diff --check` GREEN après retrait des lignes vides finales ajoutées par le worker.

### T-002 - Spécification de stratégie candidate attribuée

- Précondition ciblée: `tests/m010/validate_m010_precondition_acceptance.ps1` GREEN et `tests/m010/validate_m010_precondition_unit.ps1` GREEN.
- Commit RED: `159db19c test(m010): couvrir la specification strategie candidate`.
- RED utile: `tests/m010/validate_m010_specification_acceptance.ps1` échoue sur le contrat exécutable absent; `tests/m010/validate_m010_specification_unit.ps1` échoue sur le validateur absent.
- ADR: aucune nouvelle ADR; T-002 applique `ADR-010`, `DDD-ADR-009` et `DDD-ADR-010` sans changer leur décision.
- Implémentation: publication de `docs/specs/m010_strategie_candidate_attribuee.md`, création de `scripts/validate_m010_specification.ps1`, enrôlement dans `scripts/test.ps1` et `scripts/lint.ps1`, et rattachement `REQ-M010-002` dans `docs/traceability/matrix.md`.
- Validations ciblées GREEN: `tests/m010/validate_m010_specification_acceptance.ps1`, `tests/m010/validate_m010_specification_unit.ps1`, `scripts/validate_m010_specification.ps1`, `scripts/validate_traceability.ps1` avec `106 exigence(s) contrôlée(s)`, et `scripts/lint.ps1` avec `19 validation(s), 0 test(s)`.
- Gate global GREEN: `scripts/test.ps1` avec `19 validation(s), 202 test(s)`.
- Commit GREEN: `4856c8d4 docs(m010): publier la specification strategie candidate`.

### T-003 - Ouverture de stratégie candidate depuis résultat vérifié

- Précondition ciblée: les tests M-010 de précondition et de spécification restent GREEN avant ouverture de l'agrégat SD.
- Commit RED: `52f186a4 test(m010): couvrir ouverture strategie candidate`.
- RED utile: les tests T-003 échouaient sur le module d'ouverture de stratégie candidate absent et sur le dépôt mémoire SD absent.
- Reprise main-agent: arrêt de l'arbre `scripts/test.ps1` laissé actif par le worker après plus de 60 minutes sans verdict exploitable, puis nettoyage des répertoires générés `.tmp` et `__pycache__`.
- Implémentation: création de l'agrégat `StrategyCandidate`, du mandat SD, de la référence `VerifiedResearchRef`, des diagnostics issus de traduction RA vers SD, du cas d'usage `CreateStrategyCandidateHandler` et du dépôt mémoire avec concurrence optimiste explicite.
- Alignement documentaire: ajout de la table `Relations intercontextes publiées` dans la spécification unifiée v4.1 afin que le gate d'architecture exécuté avec cette source canonique lise les contrats RA -> SD, EG -> SD et SD -> EX sans dépendre d'un modèle interne.
- ADR: aucune nouvelle ADR; T-003 applique `ADR-010` et `DDD-ADR-010` sans changer leur décision.
- Validations ciblées GREEN: `tests/m010/validate_strategy_candidate_creation_acceptance.ps1`, `tests/m010/validate_strategy_candidate_creation_unit.ps1`, `scripts/validate_architecture_boundaries.ps1 -AppRoot .\app -ContextRegistryPath .\app\context_registry.json -SpecificationPath .\docs\specs\specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`.
- Gates GREEN: `scripts/lint.ps1` avec `19 validation(s), 0 test(s)`, `git diff --check`, et `scripts/test.ps1` avec `19 validation(s), 204 test(s)`.

### T-004 - Origines des règles de stratégie

- Précondition ciblée: `tests/m010/validate_strategy_candidate_creation_acceptance.ps1` et `tests/m010/validate_strategy_candidate_creation_unit.ps1` restent GREEN avant extension de l'agrégat SD.
- Commit RED: `53f6b5e9 test(m010): couvrir origines regles strategie`.
- RED utile: `tests/m010/validate_strategy_rule_origin_acceptance.ps1` échoue sur le cas d'usage d'ajout et d'attribution absent; `tests/m010/validate_strategy_rule_origin_unit.ps1` échoue sur les objets de domaine `RuleExpression`, `RuleOrigin`, `StrategyRule` et `RuleOriginPolicy` absents.
- Implémentation: ajout de `StrategyRule`, `RuleExpression`, `RuleOrigin`, `RuleOriginType`, `CompilationDiagnostic`, `RuleOriginPolicy`, des événements `StrategyRuleAdded` et `RuleOriginAssigned`, des transitions versionnées d'ajout, d'attribution et de validation de compilation, et des commandes applicatives `AddStrategyRule` / `AssignRuleOrigin`.
- Ajustement de gate: enrôlement des tests T-004 dans `scripts/test.ps1` et exclusion explicite des exécutions imbriquées de précondition M-003 à M-010 pour conserver l'indépendance des préconditions amont.
- ADR: aucune nouvelle ADR; T-004 applique `ADR-010`, `DDD-ADR-005` et `DDD-ADR-010` sans changer leur décision.
- Validations ciblées GREEN: `tests/m010/validate_strategy_rule_origin_acceptance.ps1`, `tests/m010/validate_strategy_rule_origin_unit.ps1`, puis non-régression `tests/m010/validate_strategy_candidate_creation_acceptance.ps1` et `tests/m010/validate_strategy_candidate_creation_unit.ps1`.
- Gate global GREEN: `scripts/test.ps1` avec `19 validation(s), 206 test(s)`.

### T-005 - Paramètres à calibrer

- Précondition ciblée: les tests T-003 et T-004 restent GREEN avant extension de l'agrégat SD aux paramètres.
- Commit RED: `1273f698 test(m010): couvrir parametres calibration strategie`.
- RED utile: `tests/m010/validate_strategy_parameter_calibration_acceptance.ps1` échoue sur le cas d'usage de gestion des paramètres absent; `tests/m010/validate_strategy_parameter_calibration_unit.ps1` échoue sur `ParameterCalibrationPolicy` absent.
- Reprise main-agent: arrêt de l'arbre `scripts/test.ps1` laissé actif par le worker après plus de 60 minutes sans verdict exploitable, puis nettoyage des répertoires générés `.tmp` et `__pycache__`.
- Implémentation: ajout de `StrategyParameter`, `ParameterDomain`, `ValidationPlan`, `ParameterCalibrationPolicy`, des événements `StrategyParameterAdded` et `CalibrationPlanDefined`, des transitions versionnées d'ajout de paramètre et de définition de plan de calibration, et des commandes applicatives `DeclareStrategyParameter` / `DefineCalibrationPlan`.
- ADR: aucune nouvelle ADR; T-005 applique `ADR-010` et `DDD-ADR-010` sans changer leur décision.
- Validations ciblées GREEN: `tests/m010/validate_strategy_parameter_calibration_acceptance.ps1`, `tests/m010/validate_strategy_parameter_calibration_unit.ps1`, puis non-régression T-003/T-004.
- Gates GREEN: `python -m compileall app\strategy_design`, `scripts/lint.ps1` avec `19 validation(s), 0 test(s)`, `git diff --check`, et `scripts/test.ps1` avec `19 validation(s), 208 test(s)`.

### T-006 - Compatibilité de stratégie

- Précondition ciblée: `scripts/test.ps1` GREEN avec `19 validation(s), 208 test(s)` avant écriture des tests RED T-006.
- Commit RED: `682a6837 test(m010): couvrir compatibilite strategie`.
- RED utile: `tests/m010/validate_strategy_compatibility_acceptance.ps1` échoue sur `CompatibilityFindingCode` absent; `tests/m010/validate_strategy_compatibility_unit.ps1` échoue sur `CompatibilityFinding` absent.
- Reprise main-agent: le worker a été interrompu après plus de 60 minutes sans final exploitable; aucun fichier de production n'avait été modifié après le commit RED.
- Implémentation: ajout de findings de compatibilité typés, exigences et disponibilité de données, profil d'exécution, politiques point-in-time et faisabilité d'exécution, politique de compatibilité, analyseur SD et statut `INCONSISTENT` raccordé aux diagnostics de compilation.
- ADR: aucune nouvelle ADR; T-006 applique `ADR-010`, `DDD-ADR-007` et `DDD-ADR-010` sans changer leur décision.
- Ajustement de gate: enrôlement des tests T-006 dans `scripts/test.ps1` et mise à jour du volume imbriqué M-003 attendu à `148 test(s)`.
- Validations ciblées GREEN: `tests/m010/validate_strategy_compatibility_acceptance.ps1`, `tests/m010/validate_strategy_compatibility_unit.ps1`, puis non-régression T-004/T-005.
- Gates GREEN: `python -m compileall app\strategy_design`, `scripts/lint.ps1` avec `19 validation(s), 0 test(s)`, `git diff --check`, `tests/m003/validate_m003_precondition_acceptance.ps1`, et `scripts/test.ps1` avec `19 validation(s), 210 test(s)`.

### T-007 - Diagnostics de validation de stratégie candidate

- Précondition ciblée: `tests/m010/validate_strategy_compatibility_acceptance.ps1` et `tests/m010/validate_strategy_compatibility_unit.ps1` GREEN avant écriture des tests RED T-007.
- Commit RED: `c33bb852 test(m010): couvrir diagnostics strategie candidate`.
- RED utile: `tests/m010/validate_strategy_candidate_diagnostics_acceptance.ps1` échoue sur la commande applicative de validation absente; `tests/m010/validate_strategy_candidate_diagnostics_unit.ps1` échoue sur le type `CompilationDiagnosticCode` absent.
- Implémentation: ajout de diagnostics de compilation typés, du statut `COMPILABLE`, des conflits SD enregistrables et résolubles, de la politique `StrategyCompletenessPolicy`, des événements `StrategyConflictRecorded`, `StrategyConflictResolved`, `StrategyCandidateValidated`, et des commandes applicatives `ValidateStrategyCandidate`, `RecordStrategyConflict` et `ResolveStrategyConflict`.
- ADR: aucune nouvelle ADR; T-007 applique `ADR-010` et `DDD-ADR-010` sans changer leur décision.
- Ajustement de gate: enrôlement des tests T-007 dans `scripts/test.ps1` et mise à jour du volume imbriqué M-003 attendu à `150 test(s)`.
- Validations ciblées GREEN: `tests/m010/validate_strategy_candidate_diagnostics_acceptance.ps1`, `tests/m010/validate_strategy_candidate_diagnostics_unit.ps1`, `tests/m003/validate_m003_precondition_acceptance.ps1`, puis non-régression T-004/T-005/T-006.
- Gates GREEN: `python -m compileall app\strategy_design`, `scripts/lint.ps1` avec `19 validation(s), 0 test(s)`, `git diff --check`, et `scripts/test.ps1` avec `19 validation(s), 212 test(s)`.

### T-008 - Compilation déterministe de stratégie candidate

- Précondition ciblée: `tests/m010/validate_strategy_candidate_diagnostics_acceptance.ps1` et `tests/m010/validate_strategy_candidate_diagnostics_unit.ps1` GREEN avant écriture des tests RED T-008.
- Commit RED: `c2a03b91 test(m010): couvrir compilation strategie deterministe`.
- RED utile: `tests/m010/validate_strategy_compilation_acceptance.ps1` échoue sur le backend déterministe absent; `tests/m010/validate_strategy_compilation_unit.ps1` échoue sur `CompiledStrategyRepresentation` absent.
- Implémentation: ajout de `StrategyCompiler`, `StrategyCompilationPolicy`, `RuleExpressionValidation`, `CompiledStrategyRepresentation`, des événements `StrategyCompiled` / `StrategyCompilationRejected`, de la commande applicative `CompileStrategyCandidate`, et d'un backend SD déterministe interne sans appel EX.
- Garde-fous: compilation refusée si statut différent de `COMPILABLE`, expression invalide, règle non déterministe sans mécanisme et graine, paramètre bloquant ou plan de validation absent; aucun backend implicite; aucun import du bounded context EX.
- ADR: aucune nouvelle ADR; T-008 applique `ADR-010` et `DDD-ADR-009` sans changer leur décision.
- Ajustement de gate: enrôlement des tests T-008 dans `scripts/test.ps1` et mise à jour du volume imbriqué M-003 attendu à `152 test(s)`.
- Validations ciblées GREEN: `tests/m010/validate_strategy_compilation_acceptance.ps1`, `tests/m010/validate_strategy_compilation_unit.ps1`, puis non-régression T-005/T-006/T-007.
- Gates GREEN: `python -m compileall app\strategy_design`, `scripts/validate_architecture_boundaries.ps1 -AppRoot .\app -ContextRegistryPath .\app\context_registry.json -SpecificationPath .\docs\specs\m001_frontieres_ddd_contrats_publies.md`, `scripts/lint.ps1` avec `19 validation(s), 0 test(s)`, `git diff --check`, `tests/m003/validate_m003_precondition_acceptance.ps1`, et `scripts/test.ps1` avec `19 validation(s), 214 test(s)`.

### T-009 - Snapshot immuable de stratégie

- Précondition ciblée: `tests/m010/validate_strategy_compilation_acceptance.ps1` et `tests/m010/validate_strategy_compilation_unit.ps1` GREEN avant écriture des tests RED T-009.
- Commit RED: `68caeb11 test(m010): couvrir snapshot strategie immuable`.
- RED utile: `tests/m010/validate_strategy_snapshot_acceptance.ps1` et `tests/m010/validate_strategy_snapshot_unit.ps1` échouaient sur le store/application de snapshot absents.
- Implémentation: ajout de `StrategySnapshotPolicy`, `StrategySnapshotPublication`, du statut `SNAPSHOTTED`, des événements `StrategySnapshotCreated` et `StrategyVersionSuperseded`, du cas d'usage `CreateStrategySnapshot`, et du store mémoire append-only `InMemoryStrategySnapshotStore` avec outbox et idempotence par `snapshot_id`/`event_id`.
- Garde-fous: snapshot seulement depuis une stratégie `COMPILABLE` et une compilation disponible; payload sans `/current` ni `latest`; conservation des `ClaimId`, versions et `EvidenceRefs` par règle documentaire; hash déterministe; relation `supersedes`/`superseded_by` résoluble; aucun doublon de snapshot ni d'événement outbox lors d'une republication.
- ADR: aucune nouvelle ADR; T-009 applique `DDD-ADR-009` et `DDD-ADR-010` sans changer leur décision.
- Ajustement de gate: enrôlement des tests T-009 dans `scripts/test.ps1` et mise à jour du volume imbriqué M-003 attendu à `154 test(s)`.
- Validations ciblées GREEN: `tests/m010/validate_strategy_snapshot_acceptance.ps1`, `tests/m010/validate_strategy_snapshot_unit.ps1`, puis non-régression T-008 et `tests/m001/validate_strategy_experiment_contracts_acceptance.ps1`.
- Gates GREEN: `python -m compileall app\strategy_design`, `scripts/lint.ps1` avec `19 validation(s), 0 test(s)`, `git diff --check`, `tests/m003/validate_m003_precondition_acceptance.ps1`, et `scripts/test.ps1` avec `19 validation(s), 216 test(s)`.
- Commit GREEN: `feat(m010): creer snapshot strategie immuable`.

### T-010 - Endpoints publics de stratégie

- Précondition ciblée: `tests/m010/validate_strategy_snapshot_acceptance.ps1` et `tests/m010/validate_strategy_snapshot_unit.ps1` GREEN avant écriture des tests RED T-010.
- Commit RED: `c8e8dddf test(m010): couvrir contrat http strategies`.
- RED utile: `tests/m010/validate_strategy_http_contract_acceptance.ps1` et `tests/m010/validate_strategy_http_contract_unit.ps1` échouaient sur l'adaptateur `app.strategy_design.adapters.strategy_http` absent.
- Implémentation: ajout de l'adaptateur HTTP SD framework-free `StrategyHttpAdapter`, des DTO stricts de compilation, du routage explicite `POST /v1/strategies/compile` et `GET /v1/strategies/{id}`, de la lecture de snapshots via store fourni, et du mapping explicite des diagnostics vers `STRATEGY_RULE_ORIGIN_MISSING`, `STRATEGY_CONFLICT_UNRESOLVED` et `CURRENT_DATA_REQUIRED`.
- Garde-fous: aucun backtest ni import EX; aucun dépôt global caché; aucun GET créateur; rejet des champs inconnus, de stockage interne et de rentabilité; publication limitée aux diagnostics, origines, références de représentation et références de snapshot.
- ADR: aucune nouvelle ADR; T-010 applique `ADR-010`, `DDD-ADR-009` et `DDD-ADR-010` sans changer leur décision.
- Ajustement de gate: enrôlement des tests T-010 dans `scripts/test.ps1` et mise à jour du volume imbriqué M-003 attendu à `156 test(s)`.
- Validations ciblées GREEN: `tests/m010/validate_strategy_http_contract_acceptance.ps1`, `tests/m010/validate_strategy_http_contract_unit.ps1`, puis non-régression T-008/T-009 et `tests/m003/validate_m003_precondition_acceptance.ps1`.
- Gates GREEN: `python -m compileall app\strategy_design`, `scripts/validate_architecture_boundaries.ps1 -AppRoot .\app -ContextRegistryPath .\app\context_registry.json -SpecificationPath .\docs\specs\m001_frontieres_ddd_contrats_publies.md` avec `158 fichier(s), 954 import(s)`, `scripts/lint.ps1` avec `19 validation(s), 0 test(s)`, `git diff --check`, et `scripts/test.ps1` avec `19 validation(s), 218 test(s)`.
- Commit GREEN: `feat(m010): exposer endpoints strategies`.
