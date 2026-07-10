# Rapport de précondition GREEN M-003

## Scénario BDD

- Given M-000, M-001 et M-002 sont présents dans `master`.
- When les gates de validation sont exécutées avant la première tâche métier M-003.
- Then M-003 peut commencer uniquement si `test`, `lint`, la traçabilité, les ADR et les frontières d'architecture sont GREEN.

## Résultat

- Statut: `GREEN`
- Branches autorisées: `codex/milestone-m003-source-routee; master; codex/milestone-m004-version-canonique-publiee; codex/milestone-m005-projection-connaissance; codex/milestone-m006-claims-verifiables; codex/milestone-m007-reponse-documentaire-verifiee; codex/milestone-m008-conversation-produit; codex/milestone-m009-recherche-approfondie; codex/milestone-m010-strategie-candidate-attribuee; codex/milestone-m011-experience-reproductible; codex/milestone-m012-evaluation-pilote-calibration; codex/milestone-m013-durcissement-acceptation-v1`

## Vérifications Git

| Élément | Commande | Date UTC | Résultat | Observation |
|---|---|---|---|---|
| `branche courante` | `git rev-parse --abbrev-ref HEAD` | `2026-07-08T16:51:10Z` | `GREEN` | Branche M-003 autorisée post-merge: codex/milestone-m013-durcissement-acceptation-v1 |
| `master local` | `git rev-parse --verify master^{commit}` | `2026-07-08T16:51:10Z` | `GREEN` | Révision locale master: 59781819e7a4d67b2fed2c048f95272505ecd2a8 |
| `origin/master` | `git rev-parse --verify origin/master^{commit}` | `2026-07-08T16:51:10Z` | `GREEN` | Révision origin/master: 59781819e7a4d67b2fed2c048f95272505ecd2a8 |
| `master contient origin/master` | `git merge-base --is-ancestor origin/master master` | `2026-07-08T16:51:10Z` | `GREEN` | La référence master contient origin/master. |
| `branche contient master` | `git merge-base --is-ancestor master HEAD` | `2026-07-08T16:51:10Z` | `GREEN` | La branche courante contient la révision locale master. |
| `docs/tasks/milestone_000 dans master` | `git ls-tree -r --name-only master -- docs/tasks/milestone_000` | `2026-07-08T16:51:10Z` | `GREEN` | Milestone amont présent dans master: docs/tasks/milestone_000 |
| `docs/tasks/milestone_001 dans master` | `git ls-tree -r --name-only master -- docs/tasks/milestone_001` | `2026-07-08T16:51:10Z` | `GREEN` | Milestone amont présent dans master: docs/tasks/milestone_001 |
| `docs/tasks/milestone_002 dans master` | `git ls-tree -r --name-only master -- docs/tasks/milestone_002` | `2026-07-08T16:51:10Z` | `GREEN` | Milestone amont présent dans master: docs/tasks/milestone_002 |

## Gates exécutées

| Élément | Commande | Date UTC | Résultat | Observation |
|---|---|---|---|---|
| `test` | `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1` | `2026-07-08T16:54:40Z` | `GREEN` | Gate test GREEN. |
| `lint` | `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1` | `2026-07-08T16:54:59Z` | `GREEN` | Gate lint GREEN. |

## Sorties des gates

### test

~~~text
Test d'acceptation de précondition M-003 exclu explicitement: exécution imbriquée du validateur de précondition.
Test d'acceptation de précondition M-004 exclu explicitement: M-003 reste indépendant du milestone aval.
Tests de précondition M-005 exclus explicitement: M-003 reste indépendant du milestone aval.
Tests de précondition M-006 exclus explicitement: M-003 reste indépendant du milestone aval.
Tests de précondition M-007 exclus explicitement: M-003 reste indépendant du milestone aval.
Tests de précondition M-008 exclus explicitement: M-003 reste indépendant du milestone aval.
Tests de précondition M-009 exclus explicitement: M-003 reste indépendant du milestone aval.
Tests de précondition M-010 exclus explicitement: M-003 reste indépendant du milestone aval.
Tests M-011 exclus explicitement: les préconditions amont restent indépendantes du milestone aval.
Tests M-012 exclus explicitement: les préconditions amont restent indépendantes du milestone aval.
Tests M-013 exclus explicitement: les préconditions amont restent indépendantes du milestone aval.
Validation requise: scripts/validate_m000_precondition_report.ps1
Rapport de précondition M-000 valide: 6 entrées contrôlées.
Validation GREEN: scripts/validate_m000_precondition_report.ps1
Validation requise: scripts/validate_adr_system.ps1
Système ADR valide: 26 ADR contrôlées, 19 décisions section 3 matérialisées.
Validation GREEN: scripts/validate_adr_system.ps1
Validation requise: scripts/validate_task_system.ps1
Système de tâches valide: 14 milestone(s), 146 tâche(s) contrôlée(s).
Validation GREEN: scripts/validate_task_system.ps1
Validation requise: scripts/validate_traceability.ps1
Matrice de traçabilité valide: 152 exigence(s) contrôlée(s).
Validation GREEN: scripts/validate_traceability.ps1
Validation requise: scripts/validate_definition_of_done.ps1
Définition d'achèvement transverse valide: 9 gates contrôlées.
Validation GREEN: scripts/validate_definition_of_done.ps1
Validation requise: scripts/validate_m001_specification.ps1
Spécification M-001 valide: 7 contexte(s), 12 relation(s) contrôlée(s).
Validation GREEN: scripts/validate_m001_specification.ps1
Validation requise: scripts/validate_m002_specification.ps1
Spécification M-002 valide: 8 règle(s), 6 placement(s) contrôlé(s).
Validation GREEN: scripts/validate_m002_specification.ps1
Validation requise: scripts/validate_m003_specification.ps1
Spécification M-003 valide: 8 comportement(s), 5 politique(s), 6 état(s) contrôlé(s).
Validation GREEN: scripts/validate_m003_specification.ps1
Validation requise: scripts/validate_m004_specification.ps1
Spécification M-004 valide: 9 comportement(s), 3 politique(s), 9 état(s) contrôlé(s).
Validation GREEN: scripts/validate_m004_specification.ps1
Validation requise: scripts/validate_m005_specification.ps1
Spécification M-005 valide: 9 comportement(s), 5 politique(s), 8 état(s) contrôlé(s).
Validation GREEN: scripts/validate_m005_specification.ps1
Validation requise: scripts/validate_m006_specification.ps1
Spécification M-006 valide: 9 comportement(s), 8 politique(s), 7 état(s) contrôlé(s).
Validation GREEN: scripts/validate_m006_specification.ps1
Validation requise: scripts/validate_m007_specification.ps1
Spécification M-007 valide: 9 comportement(s), 9 politique(s), 16 état(s) contrôlé(s).
Validation GREEN: scripts/validate_m007_specification.ps1
Validation requise: scripts/validate_m008_specification.ps1
Spécification M-008 valide: 10 comportement(s), 7 politique(s), 12 état(s) contrôlé(s).
Validation GREEN: scripts/validate_m008_specification.ps1
Validation requise: scripts/validate_m009_specification.ps1
Spécification M-009 valide: 10 comportement(s), 10 politique(s), 12 état(s) contrôlé(s).
Validation GREEN: scripts/validate_m009_specification.ps1
Validation requise: scripts/validate_m010_specification.ps1
Spécification M-010 valide: 10 comportement(s), 8 politique(s), 8 état(s) contrôlé(s).
Validation GREEN: scripts/validate_m010_specification.ps1
Validation requise: scripts/validate_m011_specification.ps1
Specification M-011 valide: 12 comportement(s), 6 metrique(s), 6 etat(s) controles.
Validation GREEN: scripts/validate_m011_specification.ps1
Validation requise: scripts/validate_m011_traceability.ps1
Tracabilite M-011 valide: 12 exigence(s), 6 metrique(s).
Validation GREEN: scripts/validate_m011_traceability.ps1
Validation requise: scripts/validate_m012_specification.ps1
Spécification M-012 valide: 11 comportement(s), 8 artefact(s), 7 contexte(s) métriques contrôlé(s).
Validation GREEN: scripts/validate_m012_specification.ps1
Validation requise: scripts/validate_m012_traceability.ps1
Traçabilité M-012 valide: 12 exigence(s), 8 écart(s) V1, 85 métrique(s).
Validation GREEN: scripts/validate_m012_traceability.ps1
Validation requise: scripts/validate_m013_specification.ps1
Spécification M-013 valide: 11 comportement(s), 8 objet(s), 8 écart(s) V1 contrôlé(s).
Validation GREEN: scripts/validate_m013_specification.ps1
Validation requise: scripts/validate_m013_v1_gap_decisions.ps1
Décisions d'écarts V1 M-013 valides: 8 écart(s), 5 écart(s) non accepté(s), acceptation V1 refusée.
Validation GREEN: scripts/validate_m013_v1_gap_decisions.ps1
Validation requise: scripts/validate_m013_regression.ps1
Suite de régression V1 M-013 valide: 8 critère(s), 10 parcours V1, 5 écart(s) non accepté(s).
Validation GREEN: scripts/validate_m013_regression.ps1
Validation requise: scripts/validate_m013_security.ps1
Audit sécurité réseau M-013 valide: 127.0.0.1 par défaut, llm-gateway -> spark-inference, 11 contrôle(s), ADR-014.
Validation GREEN: scripts/validate_m013_security.ps1
Validation requise: scripts/validate_m013_spark_failures.ps1
Pannes Spark M-013 valides: LLM_UNAVAILABLE, circuit breaker ouvrable et refermable, fonctions locales hors Gemma disponibles.
Validation GREEN: scripts/validate_m013_spark_failures.ps1
Validation requise: scripts/validate_m013_backup_restore.ps1
Sauvegarde restauration M-013 valide: restore_test_result, aucun secret en Git, aucune donnée métier sur Spark, projections régénérables non autorité, résultats négatifs et supersédés conservés.
Validation GREEN: scripts/validate_m013_backup_restore.ps1
Validation requise: scripts/validate_m013_retention.ps1
Rétention purge M-013 valide: 9 catégories durables, aucune purge ordinaire, conversation sans cascade, projection régénérable reconstruite, DDD-ADR-012.
Validation GREEN: scripts/validate_m013_retention.ps1
Validation requise: scripts/validate_m013_monitoring.ps1
Monitoring local M-013 valide: 11 métriques V1 critiques, aucun payload sensible, rétention courte, corrélation, aucun export externe, profil CPU/GPU/I/O docker-local, vLLM épinglée, modèle révisionné, concurrence sourcée par benchmark, longueur de contexte sourcée par benchmark.
Validation GREEN: scripts/validate_m013_monitoring.ps1
Validation requise: scripts/validate_m013_runbooks.ps1
Runbooks documentation utilisateur M-013 valides: 11 runbook(s), documentation utilisateur V1, commandes vérifiées, écarts V1 non acceptés visibles, aucun secret, aucun service interne publié, aucune promesse financière.
Validation GREEN: scripts/validate_m013_runbooks.ps1
Validation requise: scripts/validate_m013_antipatterns.ps1
Anti-patterns V1 M-013 valides: 17 anti-pattern(s), 14 question(s) ouverte(s) contrôlée(s), 9 contrôle(s) relié(s), aucune violation active.
Validation GREEN: scripts/validate_m013_antipatterns.ps1
Validation requise: scripts/validate_m013_acceptance.ps1
Rapport d'acceptation V1 M-013 valide: 8 critère(s), 5 écart(s) non accepté(s), 2 écart(s) bloquant(s), verdict V1 non acceptée.
Validation GREEN: scripts/validate_m013_acceptance.ps1
Validation requise: scripts/validate_platform_topology.ps1
Topologie M-002 valide: 2 hôte(s), 19 service(s) contrôlé(s).
Validation GREEN: scripts/validate_platform_topology.ps1
Validation requise: scripts/validate_local_compose.ps1
Compose local M-002 valide: 13 service(s), 3 réseau(x), 1 secret(s) contrôlé(s).
Validation GREEN: scripts/validate_local_compose.ps1
Validation requise: scripts/validate_network_boundary.ps1
Frontière réseau M-002 valide: 13 service(s) Compose, 1 règle(s) Spark, transport Spark et egress contrôlés.
Validation GREEN: scripts/validate_network_boundary.ps1
Validation requise: scripts/validate_architecture_boundaries.ps1
Frontières d'import M-001 valides: 183 fichier(s), 1111 import(s) contrôlé(s).
Validation GREEN: scripts/validate_architecture_boundaries.ps1
Test requis: tests/governance/validate_m000_precondition_report_acceptance.ps1
Test d'acceptation M-000 précondition GREEN: OK
Test GREEN: tests/governance/validate_m000_precondition_report_acceptance.ps1
Test requis: tests/governance/validate_m000_precondition_report_unit.ps1
Tests unitaires du validateur M-000 précondition: OK
Test GREEN: tests/governance/validate_m000_precondition_report_unit.ps1
Test requis: tests/governance/validate_adr_system_acceptance.ps1
Test d'acceptation du registre ADR canonique: OK
Test GREEN: tests/governance/validate_adr_system_acceptance.ps1
Test requis: tests/governance/validate_adr_system_unit.ps1
Tests unitaires du validateur ADR: OK
Test GREEN: tests/governance/validate_adr_system_unit.ps1
Test requis: tests/governance/validate_task_system_acceptance.ps1
Test d'acceptation de la convention des tâches: OK
Test GREEN: tests/governance/validate_task_system_acceptance.ps1
Test requis: tests/governance/validate_task_system_unit.ps1
Tests unitaires du validateur des tâches: OK
Test GREEN: tests/governance/validate_task_system_unit.ps1
Test requis: tests/governance/validate_traceability_acceptance.ps1
Test d'acceptation de la matrice de traçabilité: OK
Test GREEN: tests/governance/validate_traceability_acceptance.ps1
Test requis: tests/governance/validate_traceability_unit.ps1
Tests unitaires du validateur de traçabilité: OK
Test GREEN: tests/governance/validate_traceability_unit.ps1
Test requis: tests/governance/validate_definition_of_done_acceptance.ps1
Test d'acceptation de la définition d'achèvement transverse: OK
Test GREEN: tests/governance/validate_definition_of_done_acceptance.ps1
Test requis: tests/governance/validate_definition_of_done_unit.ps1
Tests unitaires du validateur de définition d'achèvement: OK
Test GREEN: tests/governance/validate_definition_of_done_unit.ps1
Test requis: tests/governance/validate_m000_validation_commands_unit.ps1
Tests unitaires des commandes de validation M-000: OK
Test GREEN: tests/governance/validate_m000_validation_commands_unit.ps1
Test requis: tests/m001/validate_m001_specification_acceptance.ps1
Test d'acceptation de la specification M-001: OK
Test GREEN: tests/m001/validate_m001_specification_acceptance.ps1
Test requis: tests/m001/validate_m001_specification_unit.ps1
Tests unitaires du validateur de spécification M-001: OK
Test GREEN: tests/m001/validate_m001_specification_unit.ps1
Test requis: tests/m001/validate_context_modules_acceptance.ps1
Test d'acceptation des modules de contexte M-001: OK
Test GREEN: tests/m001/validate_context_modules_acceptance.ps1
Test requis: tests/m001/validate_context_registry_unit.ps1
Tests unitaires du registre de contextes M-001: OK
Test GREEN: tests/m001/validate_context_registry_unit.ps1
Test requis: tests/m001/validate_contract_identity_acceptance.ps1
Test d'acceptation des identifiants de contrats M-001: OK
Test GREEN: tests/m001/validate_contract_identity_acceptance.ps1
Test requis: tests/m001/validate_contract_identity_unit.ps1
Tests unitaires des identifiants de contrats M-001: OK
Test GREEN: tests/m001/validate_contract_identity_unit.ps1
Test requis: tests/m001/validate_source_contracts_acceptance.ps1
Test d'acceptation des contrats source M-001: OK
Test GREEN: tests/m001/validate_source_contracts_acceptance.ps1
Test requis: tests/m001/validate_source_locator_unit.ps1
Tests unitaires SourceLocator M-001: OK
Test GREEN: tests/m001/validate_source_locator_unit.ps1
Test requis: tests/m001/validate_evidence_claim_contracts_acceptance.ps1
Test d'acceptation des contrats preuves et claims M-001: OK
Test GREEN: tests/m001/validate_evidence_claim_contracts_acceptance.ps1
Test requis: tests/m001/validate_evidence_claim_contracts_unit.ps1
Tests unitaires EvidenceRef et VerifiedClaimRef M-001: OK
Test GREEN: tests/m001/validate_evidence_claim_contracts_unit.ps1
Test requis: tests/m001/validate_research_outcome_contract_acceptance.ps1
Test d'acceptation du contrat VerifiedResearchOutcome M-001: OK
Test GREEN: tests/m001/validate_research_outcome_contract_acceptance.ps1
Test requis: tests/m001/validate_research_outcome_contract_unit.ps1
Tests unitaires VerifiedResearchOutcome M-001: OK
Test GREEN: tests/m001/validate_research_outcome_contract_unit.ps1
Test requis: tests/m001/validate_strategy_experiment_contracts_acceptance.ps1
Test d'acceptation des contrats StrategySnapshot et ExperimentResult M-001: OK
Test GREEN: tests/m001/validate_strategy_experiment_contracts_acceptance.ps1
Test requis: tests/m001/validate_strategy_experiment_contracts_unit.ps1
Tests unitaires StrategySnapshot et ExperimentResult M-001: OK
Test GREEN: tests/m001/validate_strategy_experiment_contracts_unit.ps1
Test requis: tests/m001/validate_event_envelope_acceptance.ps1
Test d'acceptation de l'enveloppe d'événement M-001: OK
Test GREEN: tests/m001/validate_event_envelope_acceptance.ps1
Test requis: tests/m001/validate_event_envelope_unit.ps1
Tests unitaires de l'enveloppe d'événement M-001: OK
Test GREEN: tests/m001/validate_event_envelope_unit.ps1
Test requis: tests/m001/validate_architecture_boundaries_acceptance.ps1
Test d'acceptation des frontières d'import M-001: OK
Test GREEN: tests/m001/validate_architecture_boundaries_acceptance.ps1
Test requis: tests/m001/validate_architecture_boundaries_unit.ps1
Tests unitaires des frontières d'import M-001: OK
Test GREEN: tests/m001/validate_architecture_boundaries_unit.ps1
Test requis: tests/m001/validate_m001_traceability_acceptance.ps1
Test d'acceptation de la traçabilité M-001: OK
Test GREEN: tests/m001/validate_m001_traceability_acceptance.ps1
Test requis: tests/m001/validate_m001_traceability_unit.ps1
Tests unitaires de traçabilité M-001: OK
Test GREEN: tests/m001/validate_m001_traceability_unit.ps1
Test requis: tests/m002/validate_m002_specification_acceptance.ps1
Test d'acceptation de la spécification M-002: OK
Test GREEN: tests/m002/validate_m002_specification_acceptance.ps1
Test requis: tests/m002/validate_m002_specification_unit.ps1
Tests unitaires du validateur de spécification M-002: OK
Test GREEN: tests/m002/validate_m002_specification_unit.ps1
Test requis: tests/m002/validate_platform_topology_acceptance.ps1
Test d'acceptation de topologie M-002: OK
Test GREEN: tests/m002/validate_platform_topology_acceptance.ps1
Test requis: tests/m002/validate_platform_topology_unit.ps1
Tests unitaires de topologie M-002: OK
Test GREEN: tests/m002/validate_platform_topology_unit.ps1
Test requis: tests/m002/validate_local_compose_acceptance.ps1
Test d'acceptation Compose local M-002: OK
Test GREEN: tests/m002/validate_local_compose_acceptance.ps1
Test requis: tests/m002/validate_local_compose_unit.ps1
Tests unitaires Compose local M-002: OK
Test GREEN: tests/m002/validate_local_compose_unit.ps1
Test requis: tests/m002/validate_network_boundary_acceptance.ps1
Test d'acceptation frontière réseau M-002: OK
Test GREEN: tests/m002/validate_network_boundary_acceptance.ps1
Test requis: tests/m002/validate_network_boundary_unit.ps1
Tests unitaires frontière réseau M-002: OK
Test GREEN: tests/m002/validate_network_boundary_unit.ps1
Test requis: tests/m002/validate_llm_gateway_contract_acceptance.ps1
Test d'acceptation contrat gateway LLM M-002: OK
Test GREEN: tests/m002/validate_llm_gateway_contract_acceptance.ps1
Test requis: tests/m002/validate_llm_gateway_contract_unit.ps1
Tests unitaires contrat gateway LLM M-002: OK
Test GREEN: tests/m002/validate_llm_gateway_contract_unit.ps1
Test requis: tests/m002/validate_llm_gateway_failures_acceptance.ps1
Test d'acceptation pannes gateway LLM M-002: OK
Test GREEN: tests/m002/validate_llm_gateway_failures_acceptance.ps1
Test requis: tests/m002/validate_llm_gateway_failures_unit.ps1
Tests unitaires pannes gateway LLM M-002: OK
Test GREEN: tests/m002/validate_llm_gateway_failures_unit.ps1
Test requis: tests/m002/validate_outbox_acceptance.ps1
Test d'acceptation outbox idempotente M-002: OK
Test GREEN: tests/m002/validate_outbox_acceptance.ps1
Test requis: tests/m002/validate_outbox_unit.ps1
Tests unitaires outbox idempotente M-002: OK
Test GREEN: tests/m002/validate_outbox_unit.ps1
Test requis: tests/m002/validate_job_runtime_acceptance.ps1
Test d'acceptation file de jobs idempotente M-002: OK
Test GREEN: tests/m002/validate_job_runtime_acceptance.ps1
Test requis: tests/m002/validate_job_runtime_unit.ps1
Tests unitaires file de jobs idempotente M-002: OK
Test GREEN: tests/m002/validate_job_runtime_unit.ps1
Test requis: tests/m002/validate_gateway_observability_acceptance.ps1
Test d'acceptation observabilité gateway M-002: OK
Test GREEN: tests/m002/validate_gateway_observability_acceptance.ps1
Test requis: tests/m002/validate_gateway_observability_unit.ps1
Tests unitaires observabilité gateway M-002: OK
Test GREEN: tests/m002/validate_gateway_observability_unit.ps1
Test requis: tests/m002/validate_m002_traceability_acceptance.ps1
Test d'acceptation de la traçabilité M-002: OK
Test GREEN: tests/m002/validate_m002_traceability_acceptance.ps1
Test requis: tests/m002/validate_m002_traceability_unit.ps1
Tests unitaires de traçabilité M-002: OK
Test GREEN: tests/m002/validate_m002_traceability_unit.ps1
Test requis: tests/m003/validate_m003_precondition_unit.ps1
Tests unitaires du validateur de précondition M-003: OK
Test GREEN: tests/m003/validate_m003_precondition_unit.ps1
Test requis: tests/m003/validate_m003_specification_acceptance.ps1
Test d'acceptation de la spécification M-003: OK
Test GREEN: tests/m003/validate_m003_specification_acceptance.ps1
Test requis: tests/m003/validate_m003_specification_unit.ps1
Tests unitaires du validateur de spécification M-003: OK
Test GREEN: tests/m003/validate_m003_specification_unit.ps1
Test requis: tests/m003/validate_source_registration_acceptance.ps1
Test d'acceptation T-003 enregistrement immuable des sources: OK
Test GREEN: tests/m003/validate_source_registration_acceptance.ps1
Test requis: tests/m003/validate_source_registration_unit.ps1
Tests unitaires T-003 enregistrement immuable des sources: OK
Test GREEN: tests/m003/validate_source_registration_unit.ps1
Test requis: tests/m003/validate_page_manifest_acceptance.ps1
Test d'acceptation T-004 manifeste complet des pages: OK
Test GREEN: tests/m003/validate_page_manifest_acceptance.ps1
Test requis: tests/m003/validate_page_manifest_unit.ps1
Tests unitaires T-004 manifeste complet des pages: OK
Test GREEN: tests/m003/validate_page_manifest_unit.ps1
Test requis: tests/m003/validate_page_diagnostics_acceptance.ps1
Test d'acceptation T-005 diagnostic page par page: OK
Test GREEN: tests/m003/validate_page_diagnostics_acceptance.ps1
Test requis: tests/m003/validate_page_diagnostics_unit.ps1
Tests unitaires T-005 diagnostic page par page: OK
Test GREEN: tests/m003/validate_page_diagnostics_unit.ps1
Test requis: tests/m003/validate_route_plan_acceptance.ps1
Test d'acceptation T-006 plan de routage explicite: OK
Test GREEN: tests/m003/validate_route_plan_acceptance.ps1
Test requis: tests/m003/validate_route_plan_unit.ps1
Tests unitaires T-006 plan de routage explicite: OK
Test GREEN: tests/m003/validate_route_plan_unit.ps1
Test requis: tests/m003/validate_review_quarantine_acceptance.ps1
Test d'acceptation T-007 blocages revue quarantaine: OK
Test GREEN: tests/m003/validate_review_quarantine_acceptance.ps1
Test requis: tests/m003/validate_review_quarantine_unit.ps1
Tests unitaires T-007 blocages revue quarantaine: OK
Test GREEN: tests/m003/validate_review_quarantine_unit.ps1
Test requis: tests/m003/validate_document_commands_acceptance.ps1
Test d'acceptation T-008 commandes documentaires SP: OK
Test GREEN: tests/m003/validate_document_commands_acceptance.ps1
Test requis: tests/m003/validate_document_commands_unit.ps1
Tests unitaires T-008 commandes documentaires SP: OK
Test GREEN: tests/m003/validate_document_commands_unit.ps1
Test requis: tests/m003/validate_document_http_contract_acceptance.ps1
Test d'acceptation T-008 contrat HTTP documentaire SP: OK
Test GREEN: tests/m003/validate_document_http_contract_acceptance.ps1
Test requis: tests/m003/validate_m003_audit_signals_acceptance.ps1
Test d'acceptation signaux d'audit M-003: OK
Test GREEN: tests/m003/validate_m003_audit_signals_acceptance.ps1
Test requis: tests/m003/validate_m003_traceability_acceptance.ps1
Test d'acceptation de la traçabilité M-003: OK
Test GREEN: tests/m003/validate_m003_traceability_acceptance.ps1
Test requis: tests/m003/validate_m003_traceability_unit.ps1
Tests unitaires de traçabilité M-003: OK
Test GREEN: tests/m003/validate_m003_traceability_unit.ps1
Test requis: tests/m004/validate_m004_precondition_unit.ps1
Tests unitaires du validateur de précondition M-004: OK
Test GREEN: tests/m004/validate_m004_precondition_unit.ps1
Test requis: tests/m004/validate_m004_specification_acceptance.ps1
Test d'acceptation de la spécification M-004: OK
Test GREEN: tests/m004/validate_m004_specification_acceptance.ps1
Test requis: tests/m004/validate_m004_specification_unit.ps1
Tests unitaires du validateur de spécification M-004: OK
Test GREEN: tests/m004/validate_m004_specification_unit.ps1
Test requis: tests/m004/validate_page_conversion_acceptance.ps1
Test d'acceptation T-003 conversion pagewise M-004: OK
Test GREEN: tests/m004/validate_page_conversion_acceptance.ps1
Test requis: tests/m004/validate_page_conversion_unit.ps1
Tests unitaires T-003 conversion pagewise M-004: OK
Test GREEN: tests/m004/validate_page_conversion_unit.ps1
Test requis: tests/m004/validate_text_authority_acceptance.ps1
Test d'acceptation T-004 autorité textuelle M-004: OK
Test GREEN: tests/m004/validate_text_authority_acceptance.ps1
Test requis: tests/m004/validate_text_authority_unit.ps1
Tests unitaires T-004 autorité textuelle M-004: OK
Test GREEN: tests/m004/validate_text_authority_unit.ps1
Test requis: tests/m004/validate_canonical_quality_acceptance.ps1
Test d'acceptation T-005 qualité canonique M-004: OK
Test GREEN: tests/m004/validate_canonical_quality_acceptance.ps1
Test requis: tests/m004/validate_canonical_quality_unit.ps1
Tests unitaires T-005 qualité canonique M-004: OK
Test GREEN: tests/m004/validate_canonical_quality_unit.ps1
Test requis: tests/m004/validate_canonical_publication_acceptance.ps1
Test d'acceptation T-006 publication canonique immuable M-004: OK
Test GREEN: tests/m004/validate_canonical_publication_acceptance.ps1
Test requis: tests/m004/validate_canonical_publication_unit.ps1
Tests unitaires T-006 publication canonique immuable M-004: OK
Test GREEN: tests/m004/validate_canonical_publication_unit.ps1
Test requis: tests/m004/validate_source_locator_resolution_acceptance.ps1
Test d'acceptation T-007 résolution SourceLocator M-004: OK
Test GREEN: tests/m004/validate_source_locator_resolution_acceptance.ps1
Test requis: tests/m004/validate_source_locator_resolution_unit.ps1
Tests unitaires T-007 résolution SourceLocator M-004: OK
Test GREEN: tests/m004/validate_source_locator_resolution_unit.ps1
Test requis: tests/m004/validate_canonical_publication_event_acceptance.ps1
Test d'acceptation T-008 événement CanonicalSourcePublished M-004: OK
Test GREEN: tests/m004/validate_canonical_publication_event_acceptance.ps1
Test requis: tests/m004/validate_canonical_publication_event_unit.ps1
Tests unitaires T-008 événement CanonicalSourcePublished M-004: OK
Test GREEN: tests/m004/validate_canonical_publication_event_unit.ps1
Test requis: tests/m004/validate_document_conversion_command_acceptance.ps1
Test d'acceptation T-009 commande de conversion documentaire M-004: OK
Test GREEN: tests/m004/validate_document_conversion_command_acceptance.ps1
Test requis: tests/m004/validate_document_conversion_command_unit.ps1
Tests unitaires T-009 commande de conversion documentaire M-004: OK
Test GREEN: tests/m004/validate_document_conversion_command_unit.ps1
Test requis: tests/m004/validate_m004_traceability_acceptance.ps1
Test d'acceptation de la traçabilité M-004: OK
Test GREEN: tests/m004/validate_m004_traceability_acceptance.ps1
Test requis: tests/m004/validate_m004_traceability_unit.ps1
Tests unitaires de traçabilité M-004: OK
Test GREEN: tests/m004/validate_m004_traceability_unit.ps1
Test requis: tests/m005/validate_m005_specification_acceptance.ps1
Test d'acceptation de la spécification M-005: OK
Test GREEN: tests/m005/validate_m005_specification_acceptance.ps1
Test requis: tests/m005/validate_m005_specification_unit.ps1
Tests unitaires du validateur de spécification M-005: OK
Test GREEN: tests/m005/validate_m005_specification_unit.ps1
Test requis: tests/m005/validate_knowledge_projection_acceptance.ps1
Test d'acceptation T-003 projection de connaissance M-005: OK
Test GREEN: tests/m005/validate_knowledge_projection_acceptance.ps1
Test requis: tests/m005/validate_knowledge_projection_unit.ps1
Tests unitaires T-003 projection de connaissance M-005: OK
Test GREEN: tests/m005/validate_knowledge_projection_unit.ps1
Test requis: tests/m005/validate_index_command_acceptance.ps1
Test d'acceptation T-003 contrat HTTP indexation KA M-005: OK
Test GREEN: tests/m005/validate_index_command_acceptance.ps1
Test requis: tests/m005/validate_hierarchical_chunking_acceptance.ps1
Test d'acceptation T-004 chunking hiérarchique traçable M-005: OK
Test GREEN: tests/m005/validate_hierarchical_chunking_acceptance.ps1
Test requis: tests/m005/validate_hierarchical_chunking_unit.ps1
Tests unitaires T-004 chunking hiérarchique traçable M-005: OK
Test GREEN: tests/m005/validate_hierarchical_chunking_unit.ps1
Test requis: tests/m005/validate_projection_metadata_filters_acceptance.ps1
Test d'acceptation T-005 métadonnées filtrables M-005: OK
Test GREEN: tests/m005/validate_projection_metadata_filters_acceptance.ps1
Test requis: tests/m005/validate_projection_metadata_filters_unit.ps1
Tests unitaires T-005 métadonnées filtrables M-005: OK
Test GREEN: tests/m005/validate_projection_metadata_filters_unit.ps1
Test requis: tests/m005/validate_projection_encoding_acceptance.ps1
Test d'acceptation T-006 encodage dense sparse M-005: OK
Test GREEN: tests/m005/validate_projection_encoding_acceptance.ps1
Test requis: tests/m005/validate_projection_encoding_unit.ps1
Tests unitaires T-006 encodage dense sparse M-005: OK
Test GREEN: tests/m005/validate_projection_encoding_unit.ps1
Test requis: tests/m005/validate_qdrant_projection_acceptance.ps1
Test d'acceptation T-007 index Qdrant régénérable M-005: OK
Test GREEN: tests/m005/validate_qdrant_projection_acceptance.ps1
Test requis: tests/m005/validate_qdrant_projection_unit.ps1
Tests unitaires T-007 index Qdrant régénérable M-005: OK
Test GREEN: tests/m005/validate_qdrant_projection_unit.ps1
Test requis: tests/m005/validate_knowledge_projection_events_acceptance.ps1
Test d'acceptation T-007 événements KnowledgeProjection M-005: OK
Test GREEN: tests/m005/validate_knowledge_projection_events_acceptance.ps1
Test requis: tests/m005/validate_hybrid_search_acceptance.ps1
Test d'acceptation T-008 recherche hybride traçable M-005: OK
Test GREEN: tests/m005/validate_hybrid_search_acceptance.ps1
Test requis: tests/m005/validate_hybrid_search_unit.ps1
Tests unitaires T-008 recherche hybride traçable M-005: OK
Test GREEN: tests/m005/validate_hybrid_search_unit.ps1
Test requis: tests/m005/validate_search_trace_acceptance.ps1
Test d'acceptation T-008 trace de recherche M-005: OK
Test GREEN: tests/m005/validate_search_trace_acceptance.ps1
Test requis: tests/m005/validate_search_command_acceptance.ps1
Test d'acceptation T-009 commande de recherche publique KA M-005: OK
Test GREEN: tests/m005/validate_search_command_acceptance.ps1
Test requis: tests/m005/validate_search_command_unit.ps1
Tests unitaires T-009 commande de recherche publique KA M-005: OK
Test GREEN: tests/m005/validate_search_command_unit.ps1
Test requis: tests/m005/validate_m005_traceability_acceptance.ps1
Test d'acceptation T-010 traçabilité et métriques M-005: OK
Test GREEN: tests/m005/validate_m005_traceability_acceptance.ps1
Test requis: tests/m005/validate_m005_traceability_unit.ps1
Tests unitaires T-010 traçabilité et métriques M-005: OK
Test GREEN: tests/m005/validate_m005_traceability_unit.ps1
Test requis: tests/m006/validate_m006_specification_acceptance.ps1
Test d'acceptation de la spécification M-006: OK
Test GREEN: tests/m006/validate_m006_specification_acceptance.ps1
Test requis: tests/m006/validate_m006_specification_unit.ps1
Tests unitaires du validateur de spécification M-006: OK
Test GREEN: tests/m006/validate_m006_specification_unit.ps1
Test requis: tests/m006/validate_claim_extraction_acceptance.ps1
Test d'acceptation T-003 extraction claims atomiques M-006: OK
Test GREEN: tests/m006/validate_claim_extraction_acceptance.ps1
Test requis: tests/m006/validate_claim_extraction_unit.ps1
Tests unitaires T-003 extraction claims atomiques M-006: OK
Test GREEN: tests/m006/validate_claim_extraction_unit.ps1
Test requis: tests/m006/validate_claim_evidence_attachment_acceptance.ps1
Test d'acceptation T-004 attachement preuve claim M-006: OK
Test GREEN: tests/m006/validate_claim_evidence_attachment_acceptance.ps1
Test requis: tests/m006/validate_claim_evidence_attachment_unit.ps1
Tests unitaires T-004 attachement preuve claim M-006: OK
Test GREEN: tests/m006/validate_claim_evidence_attachment_unit.ps1
Test requis: tests/m006/validate_claim_verification_acceptance.ps1
Test d'acceptation T-005 vérification claim preuve directe M-006: OK
Test GREEN: tests/m006/validate_claim_verification_acceptance.ps1
Test requis: tests/m006/validate_claim_verification_unit.ps1
Tests unitaires T-005 vérification claim preuve directe M-006: OK
Test GREEN: tests/m006/validate_claim_verification_unit.ps1
Test requis: tests/m006/validate_dependency_group_acceptance.ps1
Test d'acceptation T-006 confirmations indépendantes M-006: OK
Test GREEN: tests/m006/validate_dependency_group_acceptance.ps1
Test requis: tests/m006/validate_dependency_group_unit.ps1
Tests unitaires T-006 confirmations indépendantes M-006: OK
Test GREEN: tests/m006/validate_dependency_group_unit.ps1
Test requis: tests/m006/validate_claim_relation_acceptance.ps1
Test d'acceptation T-007 relations claims après comparaison de portée M-006: OK
Test GREEN: tests/m006/validate_claim_relation_acceptance.ps1
Test requis: tests/m006/validate_claim_relation_unit.ps1
Tests unitaires T-007 relations claims après comparaison de portée M-006: OK
Test GREEN: tests/m006/validate_claim_relation_unit.ps1
Test requis: tests/m006/validate_claim_retention_acceptance.ps1
Test d'acceptation T-008 conservation claims rejetés et supersédés M-006: OK
Test GREEN: tests/m006/validate_claim_retention_acceptance.ps1
Test requis: tests/m006/validate_claim_retention_unit.ps1
Tests unitaires T-008 conservation claims rejetés et supersédés M-006: OK
Test GREEN: tests/m006/validate_claim_retention_unit.ps1
Test requis: tests/m006/validate_claim_http_contract_acceptance.ps1
Test d'acceptation T-009 contrat HTTP claims evidence M-006: OK
Test GREEN: tests/m006/validate_claim_http_contract_acceptance.ps1
Test requis: tests/m006/validate_claim_http_contract_unit.ps1
Tests unitaires T-009 contrat HTTP claims evidence M-006: OK
Test GREEN: tests/m006/validate_claim_http_contract_unit.ps1
Test requis: tests/m006/validate_m006_traceability_acceptance.ps1
Test d'acceptation T-010 traçabilité et métriques M-006: OK
Test GREEN: tests/m006/validate_m006_traceability_acceptance.ps1
Test requis: tests/m006/validate_m006_traceability_unit.ps1
Tests unitaires T-010 traçabilité et métriques M-006: OK
Test GREEN: tests/m006/validate_m006_traceability_unit.ps1
Test requis: tests/m007/validate_m007_specification_acceptance.ps1
Test d'acceptation de la spécification M-007: OK
Test GREEN: tests/m007/validate_m007_specification_acceptance.ps1
Test requis: tests/m007/validate_m007_specification_unit.ps1
Tests unitaires du validateur de spécification M-007: OK
Test GREEN: tests/m007/validate_m007_specification_unit.ps1
Test requis: tests/m007/validate_research_case_mandate_acceptance.ps1
Test d'acceptation T-003 ResearchCase mandat explicite M-007: OK
Test GREEN: tests/m007/validate_research_case_mandate_acceptance.ps1
Test requis: tests/m007/validate_research_case_mandate_unit.ps1
Tests unitaires T-003 ResearchCase mandat explicite M-007: OK
Test GREEN: tests/m007/validate_research_case_mandate_unit.ps1
Test requis: tests/m007/validate_evidence_set_sealing_acceptance.ps1
Test d'acceptation T-004 EvidenceSet scellé M-007: OK
Test GREEN: tests/m007/validate_evidence_set_sealing_acceptance.ps1
Test requis: tests/m007/validate_evidence_set_sealing_unit.ps1
Tests unitaires T-004 EvidenceSet scellé M-007: OK
Test GREEN: tests/m007/validate_evidence_set_sealing_unit.ps1
Test requis: tests/m007/validate_contradiction_gap_acceptance.ps1
Test d'acceptation T-005 contradictions et lacunes M-007: OK
Test GREEN: tests/m007/validate_contradiction_gap_acceptance.ps1
Test requis: tests/m007/validate_contradiction_gap_unit.ps1
Tests unitaires T-005 contradictions et lacunes M-007: OK
Test GREEN: tests/m007/validate_contradiction_gap_unit.ps1
Test requis: tests/m007/validate_answer_assertion_extraction_acceptance.ps1
Test d'acceptation T-006 extraction assertions de réponse M-007: OK
Test GREEN: tests/m007/validate_answer_assertion_extraction_acceptance.ps1
Test requis: tests/m007/validate_answer_assertion_extraction_unit.ps1
Tests unitaires T-006 extraction assertions de réponse M-007: OK
Test GREEN: tests/m007/validate_answer_assertion_extraction_unit.ps1
Test requis: tests/m007/validate_answer_support_acceptance.ps1
Test d'acceptation T-007 support et citations de réponse M-007: OK
Test GREEN: tests/m007/validate_answer_support_acceptance.ps1
Test requis: tests/m007/validate_answer_support_unit.ps1
Tests unitaires T-007 support et citations de réponse M-007: OK
Test GREEN: tests/m007/validate_answer_support_unit.ps1
Test requis: tests/m007/validate_current_data_abstention_acceptance.ps1
Test d'acceptation T-008 abstention données actuelles M-007: OK
Test GREEN: tests/m007/validate_current_data_abstention_acceptance.ps1
Test requis: tests/m007/validate_current_data_abstention_unit.ps1
Tests unitaires T-008 abstention données actuelles M-007: OK
Test GREEN: tests/m007/validate_current_data_abstention_unit.ps1
Test requis: tests/m007/validate_answer_http_contract_acceptance.ps1
Test d'acceptation T-009 contrat HTTP réponse documentaire M-007: OK
Test GREEN: tests/m007/validate_answer_http_contract_acceptance.ps1
Test requis: tests/m007/validate_answer_http_contract_unit.ps1
Tests unitaires T-009 contrat HTTP réponse documentaire M-007: OK
Test GREEN: tests/m007/validate_answer_http_contract_unit.ps1
Test requis: tests/m007/validate_m007_traceability_acceptance.ps1
Test d'acceptation T-010 traçabilité et métriques M-007: OK
Test GREEN: tests/m007/validate_m007_traceability_acceptance.ps1
Test requis: tests/m007/validate_m007_traceability_unit.ps1
Tests unitaires T-010 traçabilité et métriques M-007: OK
Test GREEN: tests/m007/validate_m007_traceability_unit.ps1
Test requis: tests/m010/validate_strategy_compatibility_acceptance.ps1
Test d'acceptation de compatibilité de stratégie M-010: OK
Test GREEN: tests/m010/validate_strategy_compatibility_acceptance.ps1
Test requis: tests/m010/validate_strategy_compatibility_unit.ps1
Tests unitaires de compatibilité de stratégie M-010: OK
Test GREEN: tests/m010/validate_strategy_compatibility_unit.ps1
Test requis: tests/m010/validate_strategy_candidate_diagnostics_acceptance.ps1
Test d'acceptation des diagnostics de stratégie candidate M-010: OK
Test GREEN: tests/m010/validate_strategy_candidate_diagnostics_acceptance.ps1
Test requis: tests/m010/validate_strategy_candidate_diagnostics_unit.ps1
Tests unitaires des diagnostics de stratégie candidate M-010: OK
Test GREEN: tests/m010/validate_strategy_candidate_diagnostics_unit.ps1
Test requis: tests/m010/validate_strategy_compilation_acceptance.ps1
Test d'acceptation de compilation deterministe de strategie M-010: OK
Test GREEN: tests/m010/validate_strategy_compilation_acceptance.ps1
Test requis: tests/m010/validate_strategy_compilation_unit.ps1
Tests unitaires de compilation deterministe de strategie M-010: OK
Test GREEN: tests/m010/validate_strategy_compilation_unit.ps1
Test requis: tests/m010/validate_strategy_snapshot_acceptance.ps1
Test d'acceptation de snapshot immuable de strategie M-010: OK
Test GREEN: tests/m010/validate_strategy_snapshot_acceptance.ps1
Test requis: tests/m010/validate_strategy_snapshot_unit.ps1
Tests unitaires de snapshot immuable de strategie M-010: OK
Test GREEN: tests/m010/validate_strategy_snapshot_unit.ps1
Test requis: tests/m010/validate_strategy_http_contract_acceptance.ps1
Test d'acceptation du contrat HTTP strategies M-010: OK
Test GREEN: tests/m010/validate_strategy_http_contract_acceptance.ps1
Test requis: tests/m010/validate_strategy_http_contract_unit.ps1
Tests unitaires du contrat HTTP strategies M-010: OK
Test GREEN: tests/m010/validate_strategy_http_contract_unit.ps1
Test requis: tests/m010/validate_m010_traceability_acceptance.ps1
Test d'acceptation T-011 tracabilite, metriques et gates M-010: OK
Test GREEN: tests/m010/validate_m010_traceability_acceptance.ps1
Test requis: tests/m010/validate_m010_traceability_unit.ps1
Tests Python des metriques SD M-010: OK
Tests unitaires T-011 tracabilite, metriques et gates M-010: OK
Test GREEN: tests/m010/validate_m010_traceability_unit.ps1
Gate test GREEN: 34 validation(s), 158 test(s).
~~~

### lint

~~~text
Validation requise: scripts/validate_m000_precondition_report.ps1
Rapport de précondition M-000 valide: 6 entrées contrôlées.
Validation GREEN: scripts/validate_m000_precondition_report.ps1
Validation requise: scripts/validate_adr_system.ps1
Système ADR valide: 26 ADR contrôlées, 19 décisions section 3 matérialisées.
Validation GREEN: scripts/validate_adr_system.ps1
Validation requise: scripts/validate_task_system.ps1
Système de tâches valide: 14 milestone(s), 146 tâche(s) contrôlée(s).
Validation GREEN: scripts/validate_task_system.ps1
Validation requise: scripts/validate_traceability.ps1
Matrice de traçabilité valide: 152 exigence(s) contrôlée(s).
Validation GREEN: scripts/validate_traceability.ps1
Validation requise: scripts/validate_definition_of_done.ps1
Définition d'achèvement transverse valide: 9 gates contrôlées.
Validation GREEN: scripts/validate_definition_of_done.ps1
Validation requise: scripts/validate_m001_specification.ps1
Spécification M-001 valide: 7 contexte(s), 12 relation(s) contrôlée(s).
Validation GREEN: scripts/validate_m001_specification.ps1
Validation requise: scripts/validate_m002_specification.ps1
Spécification M-002 valide: 8 règle(s), 6 placement(s) contrôlé(s).
Validation GREEN: scripts/validate_m002_specification.ps1
Validation requise: scripts/validate_m003_specification.ps1
Spécification M-003 valide: 8 comportement(s), 5 politique(s), 6 état(s) contrôlé(s).
Validation GREEN: scripts/validate_m003_specification.ps1
Validation requise: scripts/validate_m004_specification.ps1
Spécification M-004 valide: 9 comportement(s), 3 politique(s), 9 état(s) contrôlé(s).
Validation GREEN: scripts/validate_m004_specification.ps1
Validation requise: scripts/validate_m005_specification.ps1
Spécification M-005 valide: 9 comportement(s), 5 politique(s), 8 état(s) contrôlé(s).
Validation GREEN: scripts/validate_m005_specification.ps1
Validation requise: scripts/validate_m006_specification.ps1
Spécification M-006 valide: 9 comportement(s), 8 politique(s), 7 état(s) contrôlé(s).
Validation GREEN: scripts/validate_m006_specification.ps1
Validation requise: scripts/validate_m007_specification.ps1
Spécification M-007 valide: 9 comportement(s), 9 politique(s), 16 état(s) contrôlé(s).
Validation GREEN: scripts/validate_m007_specification.ps1
Validation requise: scripts/validate_m008_specification.ps1
Spécification M-008 valide: 10 comportement(s), 7 politique(s), 12 état(s) contrôlé(s).
Validation GREEN: scripts/validate_m008_specification.ps1
Validation requise: scripts/validate_m009_specification.ps1
Spécification M-009 valide: 10 comportement(s), 10 politique(s), 12 état(s) contrôlé(s).
Validation GREEN: scripts/validate_m009_specification.ps1
Validation requise: scripts/validate_m010_specification.ps1
Spécification M-010 valide: 10 comportement(s), 8 politique(s), 8 état(s) contrôlé(s).
Validation GREEN: scripts/validate_m010_specification.ps1
Validation requise: scripts/validate_m010_traceability.ps1
Tracabilite M-010 valide: 11 exigence(s), 6 metrique(s).
Validation GREEN: scripts/validate_m010_traceability.ps1
Validation requise: scripts/validate_m011_specification.ps1
Specification M-011 valide: 12 comportement(s), 6 metrique(s), 6 etat(s) controles.
Validation GREEN: scripts/validate_m011_specification.ps1
Validation requise: scripts/validate_m011_traceability.ps1
Tracabilite M-011 valide: 12 exigence(s), 6 metrique(s).
Validation GREEN: scripts/validate_m011_traceability.ps1
Validation requise: scripts/validate_m012_specification.ps1
Spécification M-012 valide: 11 comportement(s), 8 artefact(s), 7 contexte(s) métriques contrôlé(s).
Validation GREEN: scripts/validate_m012_specification.ps1
Validation requise: scripts/validate_m012_traceability.ps1
Traçabilité M-012 valide: 12 exigence(s), 8 écart(s) V1, 85 métrique(s).
Validation GREEN: scripts/validate_m012_traceability.ps1
Validation requise: scripts/validate_m013_specification.ps1
Spécification M-013 valide: 11 comportement(s), 8 objet(s), 8 écart(s) V1 contrôlé(s).
Validation GREEN: scripts/validate_m013_specification.ps1
Validation requise: scripts/validate_m013_v1_gap_decisions.ps1
Décisions d'écarts V1 M-013 valides: 8 écart(s), 5 écart(s) non accepté(s), acceptation V1 refusée.
Validation GREEN: scripts/validate_m013_v1_gap_decisions.ps1
Validation requise: scripts/validate_m013_regression.ps1
Suite de régression V1 M-013 valide: 8 critère(s), 10 parcours V1, 5 écart(s) non accepté(s).
Validation GREEN: scripts/validate_m013_regression.ps1
Validation requise: scripts/validate_m013_security.ps1
Audit sécurité réseau M-013 valide: 127.0.0.1 par défaut, llm-gateway -> spark-inference, 11 contrôle(s), ADR-014.
Validation GREEN: scripts/validate_m013_security.ps1
Validation requise: scripts/validate_m013_spark_failures.ps1
Pannes Spark M-013 valides: LLM_UNAVAILABLE, circuit breaker ouvrable et refermable, fonctions locales hors Gemma disponibles.
Validation GREEN: scripts/validate_m013_spark_failures.ps1
Validation requise: scripts/validate_m013_backup_restore.ps1
Sauvegarde restauration M-013 valide: restore_test_result, aucun secret en Git, aucune donnée métier sur Spark, projections régénérables non autorité, résultats négatifs et supersédés conservés.
Validation GREEN: scripts/validate_m013_backup_restore.ps1
Validation requise: scripts/validate_m013_retention.ps1
Rétention purge M-013 valide: 9 catégories durables, aucune purge ordinaire, conversation sans cascade, projection régénérable reconstruite, DDD-ADR-012.
Validation GREEN: scripts/validate_m013_retention.ps1
Validation requise: scripts/validate_m013_monitoring.ps1
Monitoring local M-013 valide: 11 métriques V1 critiques, aucun payload sensible, rétention courte, corrélation, aucun export externe, profil CPU/GPU/I/O docker-local, vLLM épinglée, modèle révisionné, concurrence sourcée par benchmark, longueur de contexte sourcée par benchmark.
Validation GREEN: scripts/validate_m013_monitoring.ps1
Validation requise: scripts/validate_m013_runbooks.ps1
Runbooks documentation utilisateur M-013 valides: 11 runbook(s), documentation utilisateur V1, commandes vérifiées, écarts V1 non acceptés visibles, aucun secret, aucun service interne publié, aucune promesse financière.
Validation GREEN: scripts/validate_m013_runbooks.ps1
Validation requise: scripts/validate_m013_antipatterns.ps1
Anti-patterns V1 M-013 valides: 17 anti-pattern(s), 14 question(s) ouverte(s) contrôlée(s), 9 contrôle(s) relié(s), aucune violation active.
Validation GREEN: scripts/validate_m013_antipatterns.ps1
Validation requise: scripts/validate_m013_acceptance.ps1
Rapport d'acceptation V1 M-013 valide: 8 critère(s), 5 écart(s) non accepté(s), 2 écart(s) bloquant(s), verdict V1 non acceptée.
Validation GREEN: scripts/validate_m013_acceptance.ps1
Validation requise: scripts/validate_platform_topology.ps1
Topologie M-002 valide: 2 hôte(s), 19 service(s) contrôlé(s).
Validation GREEN: scripts/validate_platform_topology.ps1
Validation requise: scripts/validate_local_compose.ps1
Compose local M-002 valide: 13 service(s), 3 réseau(x), 1 secret(s) contrôlé(s).
Validation GREEN: scripts/validate_local_compose.ps1
Validation requise: scripts/validate_network_boundary.ps1
Frontière réseau M-002 valide: 13 service(s) Compose, 1 règle(s) Spark, transport Spark et egress contrôlés.
Validation GREEN: scripts/validate_network_boundary.ps1
Validation requise: scripts/validate_architecture_boundaries.ps1
Frontières d'import M-001 valides: 183 fichier(s), 1111 import(s) contrôlé(s).
Validation GREEN: scripts/validate_architecture_boundaries.ps1
Gate lint GREEN: 35 validation(s), 0 test(s).
~~~
