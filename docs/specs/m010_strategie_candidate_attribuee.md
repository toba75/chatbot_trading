# M-010 - Stratégie candidate attribuée

## Statut

- Statut: Publiée.
- Milestone: M-010.
- Tâche source: `docs/tasks/milestone_010/0002_publier_specification_strategie_candidate.md`.
- Bounded context propriétaire: SD.
- ADR applicables: ADR-010; DDD-ADR-009; DDD-ADR-010.

## Scénario BDD

- Given la mission M-010 est de formaliser une hypothèse de stratégie attribuée et vérifiable.
- When la spécification de stratégie candidate est publiée.
- Then chaque comportement M-010 nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.

## Mission SD

`SD` transforme un `VerifiedResearchOutcome`, un mandat utilisateur et des choix de conception explicites en `StrategyCandidate` déterministe, attribuée et compilable ou en diagnostic bloquant. Une stratégie n'est pas une promesse de rentabilité: elle reste une hypothèse vérifiable, versionnée et auditée.

`SD` ne lit pas les stockages internes de `RA`, `EG`, `KA` ou `SP`. Les conclusions `RA` sont traduites explicitement dans le langage `SD` avant de devenir règle, paramètre, contrainte ou diagnostic. `SD` ne lance aucun backtest dans M-010.

## Contexte DDD

- Domaine: conception de stratégies candidates attribuées.
- Sous-domaine: formalisation de stratégie avant expérimentation.
- Bounded context: SD.
- Contextes amont: RA expose `VerifiedResearchOutcome`; EG expose `VerifiedClaimRef`; CV transmet le mandat produit.
- Contexte aval: EX consommera uniquement un `StrategySnapshot` immuable.
- Objectif métier: éviter qu'un texte de recherche ou une réponse modèle devienne une stratégie sans origine, paramètre, compatibilité ni diagnostic.
- Invariants critiques: origine obligatoire par règle, calibration explicite des paramètres, snapshot complet et hashé, conservation des versions invalides ou supersédées.

## Langage ubiquitaire SD

| Terme | Sens M-010 |
|---|---|
| StrategyCandidate | Agrégat SD qui porte mandat, règles, paramètres, contraintes, diagnostics, statut de compilation et version. |
| StrategyRule | Entité SD qui décrit une règle déterministe de sélection, signal, entrée, sortie, sizing, risque, exécution ou construction de portefeuille. |
| StrategyParameter | Entité SD qui porte valeur fixe, domaine de calibration ou raison explicite de non-résolution. |
| RuleOrigin | Objet-valeur qui attribue chaque règle à SOURCE, DEDUCTION, DESIGN_CHOICE, PARAMETER_TO_CALIBRATE ou USER_CONSTRAINT. |
| RuleExpression | Expression déterministe validable par SD avant compilation. |
| ParameterDomain | Domaine admissible d'un paramètre à calibrer avec protocole anti-surajustement. |
| CompatibilityFinding | Diagnostic de compatibilité entre horizon, données, calendrier, coûts, liquidité, levier et mandat. |
| CompilationDiagnostic | Diagnostic bloquant ou non bloquant produit par validation ou compilation. |
| StrategySnapshot | Contrat publié complet, hashé et immuable transmis plus tard à EX. |
| StrategyCompiler | Service de domaine qui compile une stratégie validée sans lancer de backtest. |

## Agrégats et entités SD

| Agrégat | Responsabilité M-010 | Invariants | Événements |
|---|---|---|---|
| StrategyCandidate | Porter le mandat, les règles, les paramètres, les contraintes, les diagnostics, le plan de validation, le statut et la version. | Mandat obligatoire; aucune règle compilable sans origine; aucun conflit bloquant non résolu; modification de règle créant une nouvelle version. | StrategyCandidateCreated; StrategyCandidateValidated; StrategyCompilationRejected; StrategyCompiled; StrategyVersionSuperseded |
| StrategyRule | Décrire une règle déterministe rattachée à une catégorie SD et à son origine. | Origine autorisée obligatoire; expression déterministe ou mécanisme aléatoire explicite; preuve obligatoire pour SOURCE. | StrategyRuleAdded; RuleOriginAssigned |
| StrategyParameter | Décrire une valeur fixe, un domaine de calibration ou une raison de non-résolution. | PARAMETER_TO_CALIBRATE exige domaine et protocole; valeur inventée interdite; statut bloquant explicite. | StrategyParameterAdded; CalibrationPlanDefined |

## Objets-valeur SD

| Objet-valeur | Sens M-010 | Invariants |
|---|---|---|
| RuleOrigin | Provenance métier d'une règle ou d'un paramètre. | Valeur dans SOURCE, DEDUCTION, DESIGN_CHOICE, PARAMETER_TO_CALIBRATE ou USER_CONSTRAINT. |
| RuleExpression | Expression validable et compilable. | Déterministe ou aléatoire avec graine et mécanisme explicités. |
| ExecutionTiming | Fréquence d'évaluation, calendrier et délai d'exécution. | Compatible avec les données et le moment de décision. |
| DataRequirement | Données nécessaires à la règle. | Disponibilité point-in-time obligatoire avant compilation. |
| ParameterDomain | Domaine admissible d'un paramètre. | Bornes, unité et protocole anti-surajustement requis. |
| RiskConstraint | Contrainte de risque issue du mandat ou d'un choix de conception. | Levier, liquidité, marge et perte admissible explicites. |
| ValidationPlan | Plan de validation préalable au snapshot. | Présent avant StrategySnapshot et sans résultat de backtest M-011. |
| CompatibilityFinding | Résultat d'analyse de compatibilité. | Bloquant ou non bloquant, jamais ignoré silencieusement. |
| CompilationDiagnostic | Diagnostic public de validation ou compilation. | Code stable, règle ou paramètre concerné, raison explicite. |
| StrategySnapshot | Vue publiée immuable d'une version compilable. | Complet, hashé, versionné et non modifiable après création. |

## Origines autorisées

| Origine | Exigence | Diagnostic si absente |
|---|---|---|
| SOURCE | Référence à `EvidenceRef` ou `VerifiedClaimRef` avec version. | SOURCE_EVIDENCE_REQUIRED |
| DEDUCTION | Prémisses explicites, règle de transformation et séparation d'une citation directe. | RULE_ORIGIN_REQUIRED |
| DESIGN_CHOICE | Justification opérationnelle et impact sur le mandat. | DESIGN_CHOICE_JUSTIFICATION_REQUIRED |
| PARAMETER_TO_CALIBRATE | `ParameterDomain` et protocole anti-surajustement. | PARAMETER_CALIBRATION_REQUIRED |
| USER_CONSTRAINT | Référence au mandat ou à l'instruction explicite. | STRATEGY_MANDATE_REQUIRED |

## Politiques normatives M-010

| Politique | Décision | Invariants | ADR |
|---|---|---|---|
| RuleOriginPolicy | Refuse toute règle sans RuleOrigin autorisée. | Origine obligatoire; SOURCE avec preuve; DEDUCTION jamais présentée comme citation directe. | ADR-010; DDD-ADR-010 |
| StrategyCompletenessPolicy | Décide si la stratégie est complète avant validation. | Mandat, règles, paramètres, contraintes et plan de validation présents. | ADR-010 |
| StrategyCompatibilityPolicy | Analyse compatibilité des horizons, données, exécution, coûts, risque et mandat. | Incompatibilité bloquante conservée comme diagnostic. | ADR-010; DDD-ADR-010 |
| PointInTimeDataPolicy | Vérifie que les données sont disponibles au moment de décision. | Aucun look-ahead implicite; aucune valeur de marché inventée. | ADR-010 |
| ExecutionFeasibilityPolicy | Vérifie faisabilité de fréquence, calendrier, liquidité, marge et coûts. | Une règle irréalisable bloque la compilation. | ADR-010 |
| ParameterCalibrationPolicy | Exige domaine et protocole pour tout PARAMETER_TO_CALIBRATE. | Aucun paramètre à calibrer sans bornes ni protocole anti-surajustement. | ADR-010 |
| StrategyCompilationPolicy | Compile seulement une stratégie complète et compatible. | Aucun backtest; diagnostic bloquant si règle, paramètre ou conflit non résolu. | ADR-010; DDD-ADR-009; DDD-ADR-010 |
| StrategySnapshotPolicy | Crée un StrategySnapshot complet, hashé et immuable. | EX ne lit jamais l'état mutable de StrategyCandidate. | DDD-ADR-009; DDD-ADR-010 |

## Machine d'états M-010

| État | Portée | Sens M-010 | Transition autorisée |
|---|---|---|---|
| DRAFT | StrategyCandidate | Brouillon ouvert depuis un résultat vérifié et un mandat. | Vers SPECIFIED ou INCOMPLETE. |
| SPECIFIED | StrategyCandidate | Règles, paramètres et contraintes formalisés. | Vers VALIDATING. |
| VALIDATING | StrategyCandidate | Politiques de complétude, origine, compatibilité et calibration exécutées. | Vers COMPILABLE, INCOMPLETE ou INCONSISTENT. |
| INCOMPLETE | StrategyCandidate | Une origine, un mandat, un paramètre ou une preuve manque. | Terminal pour cette version ou vers SPECIFIED par nouvelle version. |
| INCONSISTENT | StrategyCandidate | Un conflit bloquant ou une incompatibilité empêche la compilation. | Terminal pour cette version ou vers SPECIFIED par nouvelle version. |
| COMPILABLE | StrategyCandidate | Stratégie validée et compilable sans backtest. | Vers SNAPSHOTTED ou SUPERSEDED. |
| SNAPSHOTTED | StrategySnapshot | Snapshot publié, hashé et immuable. | Terminal pour ce snapshot. |
| SUPERSEDED | StrategyCandidate | Version remplacée par une version plus récente. | Terminal pour cette version conservée. |

## Ports et adaptateurs SD

| Port | Responsabilité | Interdiction |
|---|---|---|
| VerifiedResearchReader | Lire le contrat public RA `VerifiedResearchOutcome`. | Aucun accès au stockage interne RA. |
| VerifiedClaimReader | Lire `VerifiedClaimRef` et preuves publiées par EG. | Aucune lecture du registre EG interne. |
| StrategyRepository | Persister l'état SD local d'une StrategyCandidate. | Ne persiste pas d'état RA, EG, KA ou EX propriétaire. |
| StrategyCompilerBackend | Produire une représentation intermédiaire exécutable depuis une stratégie validée. | Ne lance pas de backtest et ne crée pas de résultat EX. |
| RuleExpressionValidator | Valider expression, déterminisme et références de données. | Ne complète pas une expression ambiguë. |
| MarketCalendarCatalog | Fournir les calendriers nécessaires à ExecutionTiming. | N'invente pas de calendrier absent. |
| DataAvailabilityCatalog | Vérifier disponibilité point-in-time des DataRequirement. | Ne remplace pas une donnée absente par une valeur actuelle. |
| StrategySnapshotStore | Publier un StrategySnapshot immuable et hashé. | Ne modifie jamais un snapshot existant. |
| StrategyMetricsPublisher | Publier métriques et traces SD agrégées. | Ne publie pas prompt, texte RA complet, payload EG interne ou stratégie mutable complète. |

## Événements SD

| Événement | Déclencheur | Payload publié |
|---|---|---|
| StrategyCandidateCreated | Mandat et résultat vérifié acceptés. | strategy_id; strategy_version; mandate_hash; verified_research_ref |
| StrategyRuleAdded | Règle formalisée. | strategy_id; strategy_version; rule_id; rule_kind |
| RuleOriginAssigned | Origine attribuée à une règle. | strategy_id; rule_id; origin_type; evidence_ref_count |
| StrategyParameterAdded | Paramètre déclaré. | strategy_id; parameter_id; origin_type; blocking_status |
| CalibrationPlanDefined | Domaine et protocole de calibration définis. | strategy_id; parameter_id; domain_hash; protocol_version |
| StrategyConflictRecorded | Conflit ou incompatibilité enregistré. | strategy_id; diagnostic_code; blocking_status |
| StrategyConflictResolved | Conflit résolu dans une nouvelle version. | strategy_id; previous_version; new_version; resolution_summary_hash |
| StrategyCandidateValidated | Politiques SD exécutées. | strategy_id; strategy_version; status; diagnostic_count |
| StrategyCompilationRejected | Compilation refusée. | strategy_id; strategy_version; public_error_code; diagnostic_count |
| StrategyCompiled | Représentation intermédiaire produite. | strategy_id; strategy_version; compiler_version; representation_hash |
| StrategySnapshotCreated | Snapshot publié. | strategy_id; strategy_version; snapshot_id; snapshot_hash |
| StrategyVersionSuperseded | Version remplacée. | strategy_id; old_version; new_version; reason_code |

## API publique SD

| Endpoint | Succès | Erreurs publiques | Corps public |
|---|---|---|---|
| POST /v1/strategies/compile | 202 ou 200 avec strategy_id, strategy_version, compilation_status, diagnostics, representation_ref ou snapshot_ref si demandé explicitement. | HTTP_REQUEST_INVALID; STRATEGY_MANDATE_REQUIRED; RULE_ORIGIN_REQUIRED; SOURCE_EVIDENCE_REQUIRED; PARAMETER_CALIBRATION_REQUIRED; STRATEGY_CONFLICT_BLOCKING; STRATEGY_COMPATIBILITY_FAILED; STRATEGY_NOT_COMPILABLE; BACKTEST_OUT_OF_SCOPE; PUBLIC_STORAGE_FIELD_FORBIDDEN | verified_research_ref; mandate; rules; parameters; constraints; validation_plan; idempotency_key; occurred_at |
| GET /v1/strategies/{id} | 200 avec strategy_id, latest_version, compilation_status, diagnostics publics, rule_origin_summary et snapshot_refs. | ENDPOINT_NOT_FOUND; STRATEGY_NOT_FOUND; PUBLIC_STORAGE_FIELD_FORBIDDEN | strategy_id; include_versions; include_diagnostics |

### Champs publics interdits

| Endpoint | Champs interdits |
|---|---|
| POST /v1/strategies/compile | ra_repository_table; eg_registry_table; qdrant_collection; prompt_override; profitability_claim; backtest_result_override; market_price_override; mutable_snapshot_payload |
| GET /v1/strategies/{id} | ra_repository_table; eg_registry_table; internal_strategy_table; prompt_text; raw_research_payload; mutable_strategy_state |

## Erreurs publiques

| Code | Statut HTTP | Sens public |
|---|---|---|
| HTTP_REQUEST_INVALID | 400 | Requête invalide ou champ public interdit. |
| ENDPOINT_NOT_FOUND | 404 | Endpoint SD inconnu. |
| STRATEGY_NOT_FOUND | 404 | Stratégie inconnue. |
| STRATEGY_MANDATE_REQUIRED | 422 | Mandat ou contrainte utilisateur absent. |
| RULE_ORIGIN_REQUIRED | 422 | Règle sans origine autorisée. |
| SOURCE_EVIDENCE_REQUIRED | 422 | Origine SOURCE sans preuve ou claim vérifié versionné. |
| DESIGN_CHOICE_JUSTIFICATION_REQUIRED | 422 | Choix de conception sans justification opérationnelle. |
| PARAMETER_CALIBRATION_REQUIRED | 422 | Paramètre à calibrer sans domaine ou protocole. |
| STRATEGY_CONFLICT_BLOCKING | 409 | Conflit bloquant non résolu. |
| STRATEGY_COMPATIBILITY_FAILED | 409 | Incompatibilité bloquante entre données, calendrier, coût, risque ou mandat. |
| STRATEGY_NOT_COMPILABLE | 409 | Stratégie incomplète ou inconsistante. |
| STRATEGY_SNAPSHOT_IMMUTABLE | 409 | Tentative de modifier un StrategySnapshot existant. |
| BACKTEST_OUT_OF_SCOPE | 422 | Demande de backtest hors périmètre M-010. |
| PUBLIC_STORAGE_FIELD_FORBIDDEN | 400 | Champ de stockage interne exposé dans le contrat public. |

## Métriques et traces

| Signal | Type | Invariant |
|---|---|---|
| strategy_candidate_created_total | Métrique | Compte les candidates ouvertes avec mandat explicite. |
| strategy_rule_origin_assigned_total | Métrique | Compte les origines attribuées par type sans payload de preuve complet. |
| strategy_parameter_calibration_required_total | Métrique | Compte les paramètres à calibrer avec domaine et protocole. |
| strategy_candidate_validation_failed_total | Métrique | Compte les validations INCOMPLETE ou INCONSISTENT par code public. |
| strategy_candidate_compilation_rejected_total | Métrique | Compte les refus de compilation par diagnostic bloquant. |
| strategy_candidate_compiled_total | Métrique | Compte les stratégies compilées par version de compilateur. |
| strategy_snapshot_created_total | Métrique | Compte les StrategySnapshot créés avec hash et version. |
| strategy_public_error_total | Métrique | Compte les erreurs publiques par code. |
| strategy_compatibility_finding_total | Trace | Compte les CompatibilityFinding par type sans payload de marché complet. |
| strategy_version_superseded_total | Trace | Compte les versions remplacées et conservées. |

## Comportements vérifiables M-010

| Comportement | Invariant | Scénario BDD | Test RED | ADR | Commande |
|---|---|---|---|---|---|
| SD-001 - Spécification exécutable M-010 | La spécification nomme mission SD, agrégat, origines, paramètres, compatibilité, snapshot, API, erreurs, métriques, exclusions et garde-fous. | Given la mission M-010 est de formaliser une hypothèse de stratégie attribuée et vérifiable; When la spécification de stratégie candidate est publiée; Then elle est validée par commande PowerShell. | T-002 | ADR-010; DDD-ADR-009; DDD-ADR-010 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m010_specification.ps1 |
| SD-002 - Ouverture depuis résultat vérifié | Une StrategyCandidate s'ouvre depuis VerifiedResearchOutcome et mandat explicite. | Given un résultat vérifié RA et un mandat utilisateur; When SD ouvre la stratégie candidate; Then la candidate porte les références publiques sans lire RA interne. | T-003 | ADR-010; DDD-ADR-010 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_strategy_candidate_opening_acceptance.ps1 |
| SD-003 - Origines de règles attribuées | Chaque StrategyRule possède une RuleOrigin autorisée. | Given une règle d'entrée sans RuleOrigin; When la validation de compilation est demandée; Then la stratégie passe à INCOMPLETE avec diagnostic bloquant. | T-004 | ADR-010; DDD-ADR-010 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_strategy_rule_origin_acceptance.ps1 |
| SD-004 - Paramètres à calibrer cadrés | Un PARAMETER_TO_CALIBRATE possède ParameterDomain et protocole. | Given un lookback à calibrer sans domaine; When la compilation est demandée; Then PARAMETER_CALIBRATION_REQUIRED bloque la compilation. | T-005 | ADR-010 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_strategy_parameter_calibration_acceptance.ps1 |
| SD-005 - Compatibilité analysée | Les horizons, données, coûts, liquidité, levier et mandat sont compatibles avant compilation. | Given un signal quotidien appliqué à une donnée mensuelle tardive; When SD analyse la compatibilité; Then StrategyCompatibilityPolicy produit un diagnostic bloquant. | T-006 | ADR-010; DDD-ADR-010 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_strategy_compatibility_acceptance.ps1 |
| SD-006 - Diagnostics bloquants de validation | INCOMPLETE et INCONSISTENT conservent les diagnostics publics. | Given une candidate avec conflit bloquant; When la validation est demandée; Then aucun fallback ne rend la stratégie COMPILABLE. | T-007 | ADR-010; DDD-ADR-010 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_strategy_candidate_diagnostics_acceptance.ps1 |
| SD-007 - Compilation déterministe sans backtest | StrategyCompiler produit une représentation intermédiaire sans lancer EX. | Given une candidate complète et compatible; When la compilation est demandée; Then StrategyCompiled est publié sans résultat de backtest. | T-008 | ADR-010; DDD-ADR-009 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_strategy_compilation_acceptance.ps1 |
| SD-008 - Snapshot immuable hashé | StrategySnapshot est complet, versionné, hashé et non modifiable. | Given une stratégie compilable; When le snapshot est créé; Then EX ne recevra qu'un StrategySnapshot immuable. | T-009 | DDD-ADR-009; DDD-ADR-010 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_strategy_snapshot_acceptance.ps1 |
| SD-009 - Endpoints stratégies sans stockage interne | Les endpoints SD exposent seulement le contrat public. | Given une requête de compilation; When l'API SD répond; Then aucun champ RA, EG, KA ou stockage SD interne n'est exposé. | T-010 | ADR-010; DDD-ADR-009 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_strategy_http_contract_acceptance.ps1 |
| SD-010 - Traçabilité et métriques M-010 | Chaque exigence M-010 possède test, commande, ADR et métriques sans payload sensible. | Given les comportements M-010 sont implémentés; When les gates s'exécutent; Then traceability, test, lint et validate_m010_specification sont enrôlés. | T-011 | ADR-010; DDD-ADR-009; DDD-ADR-010 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_m010_traceability_acceptance.ps1 |

## Commandes de validation

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_m010_specification_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_m010_specification_unit.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m010_specification.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1
```

## Exclusions M-010

- M-010 ne lance aucun backtest et ne produit aucun résultat d'expérience M-011.
- M-010 ne déclare aucune rentabilité attendue ou réalisée.
- M-010 ne lit aucun stockage interne RA, EG, KA, SP, SD ou EX par contrat public.
- M-010 ne fabrique aucune valeur de marché actuelle.
- M-010 ne transforme pas une conclusion RA en règle SD sans traduction explicite.
- M-010 ne modifie jamais un `StrategySnapshot` existant.
