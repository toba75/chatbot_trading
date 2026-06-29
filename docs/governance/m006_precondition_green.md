# Rapport de précondition GREEN M-006

## Scénario BDD

- Given M-004 et M-005 sont présents dans `master`.
- When les gates de précondition M-006 sont exécutées.
- Then M-006 ne peut commencer que si les validations, la traçabilité, les ADR, les frontières d'architecture et les preuves M-005 sont GREEN ou si le blocage exact est isolé.

## Résultat

- Statut: `GREEN`
- Branches autorisées: `master; codex/milestone-m006-claims-verifiables`
- M-006 s'appuie sur les preuves amont M-004 et M-005 publiées dans master.

## Vérifications Git

| Élément | Commande | Date UTC | Résultat | Observation |
|---|---|---|---|---|
| `branche courante` | `git rev-parse --abbrev-ref HEAD` | `2026-06-29T11:36:29Z` | `GREEN` | Branche M-006 autorisée: codex/milestone-m006-claims-verifiables |
| `master local` | `git rev-parse --verify master^{commit}` | `2026-06-29T11:36:29Z` | `GREEN` | Révision locale master: f91e99f2febf1aea6e7bd378d3fe937ce6076313 |
| `origin/master` | `git rev-parse --verify origin/master^{commit}` | `2026-06-29T11:36:29Z` | `GREEN` | Révision origin/master: f91e99f2febf1aea6e7bd378d3fe937ce6076313 |
| `master contient origin/master` | `git merge-base --is-ancestor origin/master master` | `2026-06-29T11:36:29Z` | `GREEN` | La référence master contient origin/master. |
| `branche contient master` | `git merge-base --is-ancestor master HEAD` | `2026-06-29T11:36:29Z` | `GREEN` | La branche courante contient la révision locale master. |
| `docs/tasks/milestone_004 dans master` | `git ls-tree -r --name-only master -- docs/tasks/milestone_004` | `2026-06-29T11:36:29Z` | `GREEN` | Milestone ou preuve amont présent dans master: docs/tasks/milestone_004 |
| `docs/tasks/milestone_005 dans master` | `git ls-tree -r --name-only master -- docs/tasks/milestone_005` | `2026-06-29T11:36:29Z` | `GREEN` | Milestone ou preuve amont présent dans master: docs/tasks/milestone_005 |
| `docs/specs/m005_projection_connaissance_recherchable.md dans master` | `git ls-tree -r --name-only master -- docs/specs/m005_projection_connaissance_recherchable.md` | `2026-06-29T11:36:29Z` | `GREEN` | Milestone ou preuve amont présent dans master: docs/specs/m005_projection_connaissance_recherchable.md |
| `tests/m005 dans master` | `git ls-tree -r --name-only master -- tests/m005` | `2026-06-29T11:36:29Z` | `GREEN` | Milestone ou preuve amont présent dans master: tests/m005 |
| `docs/governance/m005_precondition_green.md dans master` | `git ls-tree -r --name-only master -- docs/governance/m005_precondition_green.md` | `2026-06-29T11:36:29Z` | `GREEN` | Milestone ou preuve amont présent dans master: docs/governance/m005_precondition_green.md |
| `scripts/test.ps1 dans master` | `git ls-tree -r --name-only master -- scripts/test.ps1` | `2026-06-29T11:36:29Z` | `GREEN` | Milestone ou preuve amont présent dans master: scripts/test.ps1 |
| `scripts/lint.ps1 dans master` | `git ls-tree -r --name-only master -- scripts/lint.ps1` | `2026-06-29T11:36:29Z` | `GREEN` | Milestone ou preuve amont présent dans master: scripts/lint.ps1 |

## Gates exécutées

| Élément | Commande | Date UTC | Résultat | Observation |
|---|---|---|---|---|
| `test` | `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1` | `2026-06-29T11:40:25Z` | `GREEN` | Gate test GREEN. |
| `lint` | `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1` | `2026-06-29T11:40:34Z` | `GREEN` | Gate lint GREEN. |

## Sorties des gates

### test

~~~text
Test d'acceptation de précondition M-003 exclu explicitement: M-006 s'appuie sur les preuves amont publiées dans master.
Test d'acceptation de précondition M-004 exclu explicitement: M-006 s'appuie sur les preuves amont publiées dans master.
Test d'acceptation de précondition M-005 exclu explicitement: M-006 s'appuie sur les preuves amont publiées dans master.
Test d'acceptation de précondition M-006 exclu explicitement: exécution imbriquée du validateur de précondition.
Validation requise: scripts/validate_m000_precondition_report.ps1
Rapport de précondition M-000 valide: 6 entrées contrôlées.
Validation GREEN: scripts/validate_m000_precondition_report.ps1
Validation requise: scripts/validate_adr_system.ps1
Système ADR valide: 22 ADR contrôlées, 19 décisions section 3 matérialisées.
Validation GREEN: scripts/validate_adr_system.ps1
Validation requise: scripts/validate_task_system.ps1
Système de tâches valide: 7 milestone(s), 67 tâche(s) contrôlée(s).
Validation GREEN: scripts/validate_task_system.ps1
Validation requise: scripts/validate_traceability.ps1
Matrice de traçabilité valide: 63 exigence(s) contrôlée(s).
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
Frontières d'import M-001 valides: 88 fichier(s), 435 import(s) contrôlé(s).
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
Test d'acceptation T-004 autoritÃ© textuelle M-004: OK
Test GREEN: tests/m004/validate_text_authority_acceptance.ps1
Test requis: tests/m004/validate_text_authority_unit.ps1
Tests unitaires T-004 autoritÃ© textuelle M-004: OK
Test GREEN: tests/m004/validate_text_authority_unit.ps1
Test requis: tests/m004/validate_canonical_quality_acceptance.ps1
Test d'acceptation T-005 qualitÃ© canonique M-004: OK
Test GREEN: tests/m004/validate_canonical_quality_acceptance.ps1
Test requis: tests/m004/validate_canonical_quality_unit.ps1
Tests unitaires T-005 qualitÃ© canonique M-004: OK
Test GREEN: tests/m004/validate_canonical_quality_unit.ps1
Test requis: tests/m004/validate_canonical_publication_acceptance.ps1
Test d'acceptation T-006 publication canonique immuable M-004: OK
Test GREEN: tests/m004/validate_canonical_publication_acceptance.ps1
Test requis: tests/m004/validate_canonical_publication_unit.ps1
Tests unitaires T-006 publication canonique immuable M-004: OK
Test GREEN: tests/m004/validate_canonical_publication_unit.ps1
Test requis: tests/m004/validate_source_locator_resolution_acceptance.ps1
Test d'acceptation T-007 rÃ©solution SourceLocator M-004: OK
Test GREEN: tests/m004/validate_source_locator_resolution_acceptance.ps1
Test requis: tests/m004/validate_source_locator_resolution_unit.ps1
Tests unitaires T-007 rÃ©solution SourceLocator M-004: OK
Test GREEN: tests/m004/validate_source_locator_resolution_unit.ps1
Test requis: tests/m004/validate_canonical_publication_event_acceptance.ps1
Test d'acceptation T-008 Ã©vÃ©nement CanonicalSourcePublished M-004: OK
Test GREEN: tests/m004/validate_canonical_publication_event_acceptance.ps1
Test requis: tests/m004/validate_canonical_publication_event_unit.ps1
Tests unitaires T-008 Ã©vÃ©nement CanonicalSourcePublished M-004: OK
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
Test requis: tests/m005/validate_m005_precondition_unit.ps1
Tests unitaires du validateur de précondition M-005: OK
Test GREEN: tests/m005/validate_m005_precondition_unit.ps1
Test requis: tests/m005/validate_m005_specification_acceptance.ps1
Test d'acceptation de la spÃ©cification M-005: OK
Test GREEN: tests/m005/validate_m005_specification_acceptance.ps1
Test requis: tests/m005/validate_m005_specification_unit.ps1
Tests unitaires du validateur de spÃ©cification M-005: OK
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
Test d'acceptation T-004 chunking hiÃ©rarchique traÃ§able M-005: OK
Test GREEN: tests/m005/validate_hierarchical_chunking_acceptance.ps1
Test requis: tests/m005/validate_hierarchical_chunking_unit.ps1
Tests unitaires T-004 chunking hiÃ©rarchique traÃ§able M-005: OK
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
Test d'acceptation T-007 index Qdrant rÃ©gÃ©nÃ©rable M-005: OK
Test GREEN: tests/m005/validate_qdrant_projection_acceptance.ps1
Test requis: tests/m005/validate_qdrant_projection_unit.ps1
Tests unitaires T-007 index Qdrant rÃ©gÃ©nÃ©rable M-005: OK
Test GREEN: tests/m005/validate_qdrant_projection_unit.ps1
Test requis: tests/m005/validate_knowledge_projection_events_acceptance.ps1
Test d'acceptation T-007 Ã©vÃ©nements KnowledgeProjection M-005: OK
Test GREEN: tests/m005/validate_knowledge_projection_events_acceptance.ps1
Test requis: tests/m005/validate_hybrid_search_acceptance.ps1
Test d'acceptation T-008 recherche hybride traÃ§able M-005: OK
Test GREEN: tests/m005/validate_hybrid_search_acceptance.ps1
Test requis: tests/m005/validate_hybrid_search_unit.ps1
Tests unitaires T-008 recherche hybride traÃ§able M-005: OK
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
Test d'acceptation T-010 traÃ§abilitÃ© et mÃ©triques M-005: OK
Test GREEN: tests/m005/validate_m005_traceability_acceptance.ps1
Test requis: tests/m005/validate_m005_traceability_unit.ps1
Tests unitaires T-010 traÃ§abilitÃ© et mÃ©triques M-005: OK
Test GREEN: tests/m005/validate_m005_traceability_unit.ps1
Test requis: tests/m006/validate_m006_precondition_unit.ps1
Tests unitaires du validateur de précondition M-006: OK
Test GREEN: tests/m006/validate_m006_precondition_unit.ps1
Gate test GREEN: 14 validation(s), 112 test(s).
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
Système de tâches valide: 7 milestone(s), 67 tâche(s) contrôlée(s).
Validation GREEN: scripts/validate_task_system.ps1
Validation requise: scripts/validate_traceability.ps1
Matrice de traçabilité valide: 63 exigence(s) contrôlée(s).
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
Frontières d'import M-001 valides: 88 fichier(s), 435 import(s) contrôlé(s).
Validation GREEN: scripts/validate_architecture_boundaries.ps1
Gate lint GREEN: 14 validation(s), 0 test(s).
~~~
