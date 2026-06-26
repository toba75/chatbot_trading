# Rapport de précondition GREEN M-003

## Scénario BDD

- Given M-000, M-001 et M-002 sont présents dans `master`.
- When les gates de validation sont exécutées avant la première tâche métier M-003.
- Then M-003 peut commencer uniquement si `test`, `lint`, la traçabilité, les ADR et les frontières d'architecture sont GREEN.

## Résultat

- Statut: `GREEN`
- Branche attendue: `codex/milestone-m003-source-routee`

## Vérifications Git

| Élément | Commande | Date UTC | Résultat | Observation |
|---|---|---|---|---|
| `branche courante` | `git rev-parse --abbrev-ref HEAD` | `2026-06-26T14:11:59Z` | `GREEN` | Branche M-003 attendue active: codex/milestone-m003-source-routee |
| `master local` | `git rev-parse --verify master^{commit}` | `2026-06-26T14:11:59Z` | `GREEN` | Révision locale master: 1d3d4896a4bd89818d3457cdd0174b517d588b8e |
| `origin/master` | `git rev-parse --verify origin/master^{commit}` | `2026-06-26T14:11:59Z` | `GREEN` | Révision origin/master: 1d3d4896a4bd89818d3457cdd0174b517d588b8e |
| `master synchronisé` | `git rev-parse master origin/master` | `2026-06-26T14:11:59Z` | `GREEN` | master et origin/master pointent sur la même révision. |
| `branche contient master` | `git merge-base --is-ancestor master HEAD` | `2026-06-26T14:11:59Z` | `GREEN` | La branche courante contient la révision locale master. |
| `docs/tasks/milestone_000 dans master` | `git ls-tree -r --name-only master -- docs/tasks/milestone_000` | `2026-06-26T14:11:59Z` | `GREEN` | Milestone amont présent dans master: docs/tasks/milestone_000 |
| `docs/tasks/milestone_001 dans master` | `git ls-tree -r --name-only master -- docs/tasks/milestone_001` | `2026-06-26T14:11:59Z` | `GREEN` | Milestone amont présent dans master: docs/tasks/milestone_001 |
| `docs/tasks/milestone_002 dans master` | `git ls-tree -r --name-only master -- docs/tasks/milestone_002` | `2026-06-26T14:11:59Z` | `GREEN` | Milestone amont présent dans master: docs/tasks/milestone_002 |

## Gates exécutées

| Élément | Commande | Date UTC | Résultat | Observation |
|---|---|---|---|---|
| `test` | `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1` | `2026-06-26T14:14:09Z` | `GREEN` | Gate test GREEN. |
| `lint` | `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1` | `2026-06-26T14:14:15Z` | `GREEN` | Gate lint GREEN. |

## Sorties des gates

### test

~~~text
Validation requise: scripts/validate_m000_precondition_report.ps1
Rapport de précondition M-000 valide: 6 entrées contrôlées.
Validation GREEN: scripts/validate_m000_precondition_report.ps1
Validation requise: scripts/validate_adr_system.ps1
Système ADR valide: 22 ADR contrôlées, 19 décisions section 3 matérialisées.
Validation GREEN: scripts/validate_adr_system.ps1
Validation requise: scripts/validate_task_system.ps1
Système de tâches valide: 4 milestone(s), 37 tâche(s) contrôlée(s).
Validation GREEN: scripts/validate_task_system.ps1
Validation requise: scripts/validate_traceability.ps1
Matrice de traçabilité valide: 43 exigence(s) contrôlée(s).
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
Validation requise: scripts/validate_platform_topology.ps1
Topologie M-002 valide: 2 hôte(s), 19 service(s) contrôlé(s).
Validation GREEN: scripts/validate_platform_topology.ps1
Validation requise: scripts/validate_local_compose.ps1
Compose local M-002 valide: 13 service(s), 3 réseau(x), 3 secret(s) contrôlé(s).
Validation GREEN: scripts/validate_local_compose.ps1
Validation requise: scripts/validate_network_boundary.ps1
Frontière réseau M-002 valide: 13 service(s) Compose, 1 règle(s) Spark, TLS et egress contrôlés.
Validation GREEN: scripts/validate_network_boundary.ps1
Validation requise: scripts/validate_architecture_boundaries.ps1
Frontières d'import M-001 valides: 60 fichier(s), 196 import(s) contrôlé(s).
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
Gate test GREEN: 12 validation(s), 70 test(s).
~~~

### lint

~~~text
Validation requise: scripts/validate_m000_precondition_report.ps1
Rapport de précondition M-000 valide: 6 entrées contrôlées.
Validation GREEN: scripts/validate_m000_precondition_report.ps1
Validation requise: scripts/validate_adr_system.ps1
Système ADR valide: 22 ADR contrôlées, 19 décisions section 3 matérialisées.
Validation GREEN: scripts/validate_adr_system.ps1
Validation requise: scripts/validate_task_system.ps1
Système de tâches valide: 4 milestone(s), 37 tâche(s) contrôlée(s).
Validation GREEN: scripts/validate_task_system.ps1
Validation requise: scripts/validate_traceability.ps1
Matrice de traçabilité valide: 43 exigence(s) contrôlée(s).
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
Validation requise: scripts/validate_platform_topology.ps1
Topologie M-002 valide: 2 hôte(s), 19 service(s) contrôlé(s).
Validation GREEN: scripts/validate_platform_topology.ps1
Validation requise: scripts/validate_local_compose.ps1
Compose local M-002 valide: 13 service(s), 3 réseau(x), 3 secret(s) contrôlé(s).
Validation GREEN: scripts/validate_local_compose.ps1
Validation requise: scripts/validate_network_boundary.ps1
Frontière réseau M-002 valide: 13 service(s) Compose, 1 règle(s) Spark, TLS et egress contrôlés.
Validation GREEN: scripts/validate_network_boundary.ps1
Validation requise: scripts/validate_architecture_boundaries.ps1
Frontières d'import M-001 valides: 60 fichier(s), 196 import(s) contrôlé(s).
Validation GREEN: scripts/validate_architecture_boundaries.ps1
Gate lint GREEN: 12 validation(s), 0 test(s).
~~~
