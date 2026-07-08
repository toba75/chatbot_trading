# Rapport de prÃ©condition GREEN M-013

## ScÃ©nario BDD

- Given M-012 est prÃ©sent dans `master` avec ses tÃ¢ches, sa spÃ©cification, ses validateurs, ses tests, son contexte EV et son rapport d'Ã©carts V1.
- When les gates de prÃ©condition M-013 sont exÃ©cutÃ©es sur une branche M-013 crÃ©Ã©e depuis `master`.
- Then M-013 ne peut commencer que si la prÃ©sence M-012, les Ã©carts V1, la branche de travail et les gates amont ont un verdict explicite.

## RÃ©sultat

- Statut: `GREEN`
- Branches autorisÃ©es: `master; codex/milestone-m013-durcissement-acceptation-v1`
- M-013 consomme le rapport d'Ã©carts V1 M-012 sans requalifier les statuts scientifiques ni masquer les tests RED conservÃ©s.

## VÃ©rifications Git Et V1

| Ã‰lÃ©ment | Commande | Date UTC | RÃ©sultat | Observation |
|---|---|---|---|---|
| `branche courante` | `git rev-parse --abbrev-ref HEAD` | `2026-07-07T00:09:13Z` | `GREEN` | Branche M-013 autorisÃ©e: codex/milestone-m013-durcissement-acceptation-v1 |
| `master local` | `git rev-parse --verify master^{commit}` | `2026-07-07T00:09:13Z` | `GREEN` | RÃ©vision locale master: 9f3e7185110ee3dae586d624301caca1ca09ea4c |
| `origin/master` | `git rev-parse --verify origin/master^{commit}` | `2026-07-07T00:09:13Z` | `GREEN` | RÃ©vision origin/master: 9f3e7185110ee3dae586d624301caca1ca09ea4c |
| `master contient origin/master` | `git merge-base --is-ancestor origin/master master` | `2026-07-07T00:09:13Z` | `GREEN` | La rÃ©fÃ©rence master contient origin/master. |
| `branche contient master` | `git merge-base --is-ancestor master HEAD` | `2026-07-07T00:09:13Z` | `GREEN` | La branche courante contient la rÃ©vision locale master. |
| `scripts/validate_m003_precondition.ps1 accepte M-013` | `Select-String -Path scripts/validate_m003_precondition.ps1 -Pattern codex/milestone-m013-durcissement-acceptation-v1` | `2026-07-07T00:09:13Z` | `GREEN` | Validateur amont M-003 autorise explicitement la branche M-013. |
| `scripts/validate_m004_precondition.ps1 accepte M-013` | `Select-String -Path scripts/validate_m004_precondition.ps1 -Pattern codex/milestone-m013-durcissement-acceptation-v1` | `2026-07-07T00:09:13Z` | `GREEN` | Validateur amont M-004 autorise explicitement la branche M-013. |
| `scripts/validate_m005_precondition.ps1 accepte M-013` | `Select-String -Path scripts/validate_m005_precondition.ps1 -Pattern codex/milestone-m013-durcissement-acceptation-v1` | `2026-07-07T00:09:13Z` | `GREEN` | Validateur amont M-005 autorise explicitement la branche M-013. |
| `scripts/validate_m006_precondition.ps1 accepte M-013` | `Select-String -Path scripts/validate_m006_precondition.ps1 -Pattern codex/milestone-m013-durcissement-acceptation-v1` | `2026-07-07T00:09:13Z` | `GREEN` | Validateur amont M-006 autorise explicitement la branche M-013. |
| `scripts/validate_m007_precondition.ps1 accepte M-013` | `Select-String -Path scripts/validate_m007_precondition.ps1 -Pattern codex/milestone-m013-durcissement-acceptation-v1` | `2026-07-07T00:09:13Z` | `GREEN` | Validateur amont M-007 autorise explicitement la branche M-013. |
| `scripts/validate_m008_precondition.ps1 accepte M-013` | `Select-String -Path scripts/validate_m008_precondition.ps1 -Pattern codex/milestone-m013-durcissement-acceptation-v1` | `2026-07-07T00:09:13Z` | `GREEN` | Validateur amont M-008 autorise explicitement la branche M-013. |
| `scripts/validate_m009_precondition.ps1 accepte M-013` | `Select-String -Path scripts/validate_m009_precondition.ps1 -Pattern codex/milestone-m013-durcissement-acceptation-v1` | `2026-07-07T00:09:13Z` | `GREEN` | Validateur amont M-009 autorise explicitement la branche M-013. |
| `scripts/validate_m010_precondition.ps1 accepte M-013` | `Select-String -Path scripts/validate_m010_precondition.ps1 -Pattern codex/milestone-m013-durcissement-acceptation-v1` | `2026-07-07T00:09:13Z` | `GREEN` | Validateur amont M-010 autorise explicitement la branche M-013. |
| `scripts/validate_m011_precondition.ps1 accepte M-013` | `Select-String -Path scripts/validate_m011_precondition.ps1 -Pattern codex/milestone-m013-durcissement-acceptation-v1` | `2026-07-07T00:09:13Z` | `GREEN` | Validateur amont M-011 autorise explicitement la branche M-013. |
| `scripts/validate_m012_precondition.ps1 accepte M-013` | `Select-String -Path scripts/validate_m012_precondition.ps1 -Pattern codex/milestone-m013-durcissement-acceptation-v1` | `2026-07-07T00:09:13Z` | `GREEN` | Validateur amont M-012 autorise explicitement la branche M-013. |
| `docs/tasks/milestone_012 dans master` | `git ls-tree -r --name-only master -- docs/tasks/milestone_012` | `2026-07-07T00:09:13Z` | `GREEN` | Milestone ou preuve amont prÃ©sent dans master: docs/tasks/milestone_012 |
| `docs/specs/m012_evaluation_pilote_calibration.md dans master` | `git ls-tree -r --name-only master -- docs/specs/m012_evaluation_pilote_calibration.md` | `2026-07-07T00:09:13Z` | `GREEN` | Milestone ou preuve amont prÃ©sent dans master: docs/specs/m012_evaluation_pilote_calibration.md |
| `scripts/validate_m012_precondition.ps1 dans master` | `git ls-tree -r --name-only master -- scripts/validate_m012_precondition.ps1` | `2026-07-07T00:09:13Z` | `GREEN` | Milestone ou preuve amont prÃ©sent dans master: scripts/validate_m012_precondition.ps1 |
| `scripts/validate_m012_specification.ps1 dans master` | `git ls-tree -r --name-only master -- scripts/validate_m012_specification.ps1` | `2026-07-07T00:09:13Z` | `GREEN` | Milestone ou preuve amont prÃ©sent dans master: scripts/validate_m012_specification.ps1 |
| `scripts/validate_m012_traceability.ps1 dans master` | `git ls-tree -r --name-only master -- scripts/validate_m012_traceability.ps1` | `2026-07-07T00:09:13Z` | `GREEN` | Milestone ou preuve amont prÃ©sent dans master: scripts/validate_m012_traceability.ps1 |
| `tests/m012 dans master` | `git ls-tree -r --name-only master -- tests/m012` | `2026-07-07T00:09:13Z` | `GREEN` | Milestone ou preuve amont prÃ©sent dans master: tests/m012 |
| `app/evaluation dans master` | `git ls-tree -r --name-only master -- app/evaluation` | `2026-07-07T00:09:13Z` | `GREEN` | Milestone ou preuve amont prÃ©sent dans master: app/evaluation |
| `docs/governance/m012_v1_gap_report.md dans master` | `git ls-tree -r --name-only master -- docs/governance/m012_v1_gap_report.md` | `2026-07-07T00:09:13Z` | `GREEN` | Milestone ou preuve amont prÃ©sent dans master: docs/governance/m012_v1_gap_report.md |
| `docs/traceability/matrix.md dans master` | `git ls-tree -r --name-only master -- docs/traceability/matrix.md` | `2026-07-07T00:09:13Z` | `GREEN` | Milestone ou preuve amont prÃ©sent dans master: docs/traceability/matrix.md |
| `scripts/test.ps1 dans master` | `git ls-tree -r --name-only master -- scripts/test.ps1` | `2026-07-07T00:09:14Z` | `GREEN` | Milestone ou preuve amont prÃ©sent dans master: scripts/test.ps1 |
| `scripts/lint.ps1 dans master` | `git ls-tree -r --name-only master -- scripts/lint.ps1` | `2026-07-07T00:09:14Z` | `GREEN` | Milestone ou preuve amont prÃ©sent dans master: scripts/lint.ps1 |
| `scripts/validate_task_system.ps1 dans master` | `git ls-tree -r --name-only master -- scripts/validate_task_system.ps1` | `2026-07-07T00:09:14Z` | `GREEN` | Milestone ou preuve amont prÃ©sent dans master: scripts/validate_task_system.ps1 |
| `Ã‰cart V1 SP statutÃ©` | `git show master:docs/governance/m012_v1_gap_report.md` | `2026-07-07T00:09:14Z` | `GREEN` | Ã‰cart V1 SP statutÃ©: différé |
| `Ã‰cart V1 KA statutÃ©` | `git show master:docs/governance/m012_v1_gap_report.md` | `2026-07-07T00:09:14Z` | `GREEN` | Ã‰cart V1 KA statutÃ©: différé |
| `Ã‰cart V1 EG statutÃ©` | `git show master:docs/governance/m012_v1_gap_report.md` | `2026-07-07T00:09:14Z` | `GREEN` | Ã‰cart V1 EG statutÃ©: satisfait |
| `Ã‰cart V1 RA statutÃ©` | `git show master:docs/governance/m012_v1_gap_report.md` | `2026-07-07T00:09:14Z` | `GREEN` | Ã‰cart V1 RA statutÃ©: différé |
| `Ã‰cart V1 CV statutÃ©` | `git show master:docs/governance/m012_v1_gap_report.md` | `2026-07-07T00:09:14Z` | `GREEN` | Ã‰cart V1 CV statutÃ©: satisfait |
| `Ã‰cart V1 SD statutÃ©` | `git show master:docs/governance/m012_v1_gap_report.md` | `2026-07-07T00:09:14Z` | `GREEN` | Ã‰cart V1 SD statutÃ©: bloquant |
| `Ã‰cart V1 LLM statutÃ©` | `git show master:docs/governance/m012_v1_gap_report.md` | `2026-07-07T00:09:14Z` | `GREEN` | Ã‰cart V1 LLM statutÃ©: bloquant |
| `Ã‰cart V1 EX statutÃ©` | `git show master:docs/governance/m012_v1_gap_report.md` | `2026-07-07T00:09:14Z` | `GREEN` | Ã‰cart V1 EX statutÃ©: satisfait |
| `Tests scientifiques RED conservÃ©s` | `git show master:docs/governance/m012_v1_gap_report.md` | `2026-07-07T00:09:14Z` | `GREEN` | Test scientifique RED conservÃ© dans le rapport V1 M-012. |

## Gates exÃ©cutÃ©es

| Ã‰lÃ©ment | Commande | Date UTC | RÃ©sultat | Observation |
|---|---|---|---|---|
| `test` | `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1` | `2026-07-07T00:16:48Z` | `GREEN` | Gate test GREEN. |
| `lint` | `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1` | `2026-07-07T00:17:02Z` | `GREEN` | Gate lint GREEN. |

## Sorties des gates

### test

~~~text
Test d'acceptation de précondition M-003 exclu explicitement: M-013 vérifie les validateurs amont sans récursion.
Test d'acceptation de précondition M-004 exclu explicitement: M-013 vérifie les validateurs amont sans récursion.
Test d'acceptation de précondition M-005 exclu explicitement: M-013 vérifie les validateurs amont sans récursion.
Test d'acceptation de précondition M-006 exclu explicitement: M-013 vérifie les validateurs amont sans récursion.
Test d'acceptation de précondition M-007 exclu explicitement: M-013 vérifie les validateurs amont sans récursion.
Test d'acceptation de précondition M-008 exclu explicitement: M-013 vérifie les validateurs amont sans récursion.
Test d'acceptation de précondition M-009 exclu explicitement: M-013 vérifie les validateurs amont sans récursion.
Test d'acceptation de précondition M-010 exclu explicitement: M-013 vérifie les validateurs amont sans récursion.
Test d'acceptation de précondition M-011 exclu explicitement: M-013 vérifie les validateurs amont sans récursion.
Test d'acceptation de précondition M-012 exclu explicitement: M-013 vérifie les validateurs amont sans récursion.
Test d'acceptation de précondition M-013 exclu explicitement: exécution imbriquée du validateur de précondition.
Validation requise: scripts/validate_m000_precondition_report.ps1
Rapport de précondition M-000 valide: 6 entrées contrôlées.
Validation GREEN: scripts/validate_m000_precondition_report.ps1
Validation requise: scripts/validate_adr_system.ps1
Système ADR valide: 23 ADR contrôlées, 19 décisions section 3 matérialisées.
Validation GREEN: scripts/validate_adr_system.ps1
Validation requise: scripts/validate_task_system.ps1
Système de tâches valide: 14 milestone(s), 146 tâche(s) contrôlée(s).
Validation GREEN: scripts/validate_task_system.ps1
Validation requise: scripts/validate_traceability.ps1
Matrice de traçabilité valide: 140 exigence(s) contrôlée(s).
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
Frontières d'import M-001 valides: 178 fichier(s), 1081 import(s) contrôlé(s).
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
Test requis: tests/m006/validate_m006_specification_acceptance.ps1
Test d'acceptation de la spÃ©cification M-006: OK
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
Test d'acceptation T-005 vÃ©rification claim preuve directe M-006: OK
Test GREEN: tests/m006/validate_claim_verification_acceptance.ps1
Test requis: tests/m006/validate_claim_verification_unit.ps1
Tests unitaires T-005 vÃ©rification claim preuve directe M-006: OK
Test GREEN: tests/m006/validate_claim_verification_unit.ps1
Test requis: tests/m006/validate_dependency_group_acceptance.ps1
Test d'acceptation T-006 confirmations indÃ©pendantes M-006: OK
Test GREEN: tests/m006/validate_dependency_group_acceptance.ps1
Test requis: tests/m006/validate_dependency_group_unit.ps1
Tests unitaires T-006 confirmations indÃ©pendantes M-006: OK
Test GREEN: tests/m006/validate_dependency_group_unit.ps1
Test requis: tests/m006/validate_claim_relation_acceptance.ps1
Test d'acceptation T-007 relations claims aprÃ¨s comparaison de portÃ©e M-006: OK
Test GREEN: tests/m006/validate_claim_relation_acceptance.ps1
Test requis: tests/m006/validate_claim_relation_unit.ps1
Tests unitaires T-007 relations claims aprÃ¨s comparaison de portÃ©e M-006: OK
Test GREEN: tests/m006/validate_claim_relation_unit.ps1
Test requis: tests/m006/validate_claim_retention_acceptance.ps1
Test d'acceptation T-008 conservation claims rejetÃ©s et supersÃ©dÃ©s M-006: OK
Test GREEN: tests/m006/validate_claim_retention_acceptance.ps1
Test requis: tests/m006/validate_claim_retention_unit.ps1
Tests unitaires T-008 conservation claims rejetÃ©s et supersÃ©dÃ©s M-006: OK
Test GREEN: tests/m006/validate_claim_retention_unit.ps1
Test requis: tests/m006/validate_claim_http_contract_acceptance.ps1
Test d'acceptation T-009 contrat HTTP claims evidence M-006: OK
Test GREEN: tests/m006/validate_claim_http_contract_acceptance.ps1
Test requis: tests/m006/validate_claim_http_contract_unit.ps1
Tests unitaires T-009 contrat HTTP claims evidence M-006: OK
Test GREEN: tests/m006/validate_claim_http_contract_unit.ps1
Test requis: tests/m006/validate_m006_traceability_acceptance.ps1
Test d'acceptation T-010 traÃ§abilitÃ© et mÃ©triques M-006: OK
Test GREEN: tests/m006/validate_m006_traceability_acceptance.ps1
Test requis: tests/m006/validate_m006_traceability_unit.ps1
Tests unitaires T-010 traÃ§abilitÃ© et mÃ©triques M-006: OK
Test GREEN: tests/m006/validate_m006_traceability_unit.ps1
Test requis: tests/m007/validate_m007_precondition_unit.ps1
Tests unitaires du validateur de précondition M-007: OK
Test GREEN: tests/m007/validate_m007_precondition_unit.ps1
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
Test d'acceptation T-004 EvidenceSet scellÃ© M-007: OK
Test GREEN: tests/m007/validate_evidence_set_sealing_acceptance.ps1
Test requis: tests/m007/validate_evidence_set_sealing_unit.ps1
Tests unitaires T-004 EvidenceSet scellÃ© M-007: OK
Test GREEN: tests/m007/validate_evidence_set_sealing_unit.ps1
Test requis: tests/m007/validate_contradiction_gap_acceptance.ps1
Test d'acceptation T-005 contradictions et lacunes M-007: OK
Test GREEN: tests/m007/validate_contradiction_gap_acceptance.ps1
Test requis: tests/m007/validate_contradiction_gap_unit.ps1
Tests unitaires T-005 contradictions et lacunes M-007: OK
Test GREEN: tests/m007/validate_contradiction_gap_unit.ps1
Test requis: tests/m007/validate_answer_assertion_extraction_acceptance.ps1
Test d'acceptation T-006 extraction assertions de rÃ©ponse M-007: OK
Test GREEN: tests/m007/validate_answer_assertion_extraction_acceptance.ps1
Test requis: tests/m007/validate_answer_assertion_extraction_unit.ps1
Tests unitaires T-006 extraction assertions de rÃ©ponse M-007: OK
Test GREEN: tests/m007/validate_answer_assertion_extraction_unit.ps1
Test requis: tests/m007/validate_answer_support_acceptance.ps1
Test d'acceptation T-007 support et citations de rÃ©ponse M-007: OK
Test GREEN: tests/m007/validate_answer_support_acceptance.ps1
Test requis: tests/m007/validate_answer_support_unit.ps1
Tests unitaires T-007 support et citations de rÃ©ponse M-007: OK
Test GREEN: tests/m007/validate_answer_support_unit.ps1
Test requis: tests/m007/validate_current_data_abstention_acceptance.ps1
Test d'acceptation T-008 abstention donnÃ©es actuelles M-007: OK
Test GREEN: tests/m007/validate_current_data_abstention_acceptance.ps1
Test requis: tests/m007/validate_current_data_abstention_unit.ps1
Tests unitaires T-008 abstention donnÃ©es actuelles M-007: OK
Test GREEN: tests/m007/validate_current_data_abstention_unit.ps1
Test requis: tests/m007/validate_answer_http_contract_acceptance.ps1
Test d'acceptation T-009 contrat HTTP rÃ©ponse documentaire M-007: OK
Test GREEN: tests/m007/validate_answer_http_contract_acceptance.ps1
Test requis: tests/m007/validate_answer_http_contract_unit.ps1
Tests unitaires T-009 contrat HTTP rÃ©ponse documentaire M-007: OK
Test GREEN: tests/m007/validate_answer_http_contract_unit.ps1
Test requis: tests/m007/validate_m007_traceability_acceptance.ps1
Test d'acceptation T-010 traÃ§abilitÃ© et mÃ©triques M-007: OK
Test GREEN: tests/m007/validate_m007_traceability_acceptance.ps1
Test requis: tests/m007/validate_m007_traceability_unit.ps1
Tests unitaires T-010 traÃ§abilitÃ© et mÃ©triques M-007: OK
Test GREEN: tests/m007/validate_m007_traceability_unit.ps1
Test requis: tests/m008/validate_m008_precondition_unit.ps1
Tests unitaires du validateur de précondition M-008: OK
Test GREEN: tests/m008/validate_m008_precondition_unit.ps1
Test requis: tests/m008/validate_m008_specification_acceptance.ps1
Test d'acceptation de la spécification M-008: OK
Test GREEN: tests/m008/validate_m008_specification_acceptance.ps1
Test requis: tests/m008/validate_m008_specification_unit.ps1
Tests unitaires du validateur de spécification M-008: OK
Test GREEN: tests/m008/validate_m008_specification_unit.ps1
Test requis: tests/m008/validate_conversation_turn_append_only_acceptance.ps1
Test d'acceptation T-003 conversations append-only M-008: OK
Test GREEN: tests/m008/validate_conversation_turn_append_only_acceptance.ps1
Test requis: tests/m008/validate_conversation_turn_append_only_unit.ps1
Tests unitaires T-003 conversations append-only M-008: OK
Test GREEN: tests/m008/validate_conversation_turn_append_only_unit.ps1
Test requis: tests/m008/validate_conversation_context_snapshot_acceptance.ps1
Test d'acceptation T-004 snapshot contexte M-008: OK
Test GREEN: tests/m008/validate_conversation_context_snapshot_acceptance.ps1
Test requis: tests/m008/validate_conversation_context_snapshot_unit.ps1
Tests unitaires T-004 snapshot contexte M-008: OK
Test GREEN: tests/m008/validate_conversation_context_snapshot_unit.ps1
Test requis: tests/m008/validate_followup_question_resolution_acceptance.ps1
Test d'acceptation T-005 resolution reference suivi M-008: OK
Test GREEN: tests/m008/validate_followup_question_resolution_acceptance.ps1
Test requis: tests/m008/validate_followup_question_resolution_unit.ps1
Tests unitaires T-005 resolution reference suivi M-008: OK
Test GREEN: tests/m008/validate_followup_question_resolution_unit.ps1
Test requis: tests/m008/validate_conversation_mode_routing_acceptance.ps1
Test d'acceptation T-006 routage modes conversation M-008: OK
Test GREEN: tests/m008/validate_conversation_mode_routing_acceptance.ps1
Test requis: tests/m008/validate_conversation_mode_routing_unit.ps1
Tests unitaires T-006 routage modes conversation M-008: OK
Test GREEN: tests/m008/validate_conversation_mode_routing_unit.ps1
Test requis: tests/m008/validate_verified_result_reuse_acceptance.ps1
Test d'acceptation T-007 revalidation historique M-008: OK
Test GREEN: tests/m008/validate_verified_result_reuse_acceptance.ps1
Test requis: tests/m008/validate_verified_answer_attachment_unit.ps1
Tests unitaires T-007 rattachement reponse verifiee M-008: OK
Test GREEN: tests/m008/validate_verified_answer_attachment_unit.ps1
Test requis: tests/m008/validate_chat_answer_presentation_acceptance.ps1
Test d'acceptation T-008 presentation citations statuts M-008: OK
Test GREEN: tests/m008/validate_chat_answer_presentation_acceptance.ps1
Test requis: tests/m008/validate_chat_answer_presentation_unit.ps1
Tests unitaires T-008 presentation citations statuts M-008: OK
Test GREEN: tests/m008/validate_chat_answer_presentation_unit.ps1
Test requis: tests/m008/validate_conversation_http_contract_acceptance.ps1
Test d'acceptation T-009 contrat HTTP conversation M-008: OK
Test GREEN: tests/m008/validate_conversation_http_contract_acceptance.ps1
Test requis: tests/m008/validate_conversation_http_contract_unit.ps1
Tests unitaires T-009 contrat HTTP conversation M-008: OK
Test GREEN: tests/m008/validate_conversation_http_contract_unit.ps1
Test requis: tests/m008/validate_chat_completions_contract_acceptance.ps1
Test d'acceptation T-010 contrat chat completions M-008: OK
Test GREEN: tests/m008/validate_chat_completions_contract_acceptance.ps1
Test requis: tests/m008/validate_chat_completions_contract_unit.ps1
Tests unitaires T-010 contrat chat completions M-008: OK
Test GREEN: tests/m008/validate_chat_completions_contract_unit.ps1
Test requis: tests/m008/validate_m008_traceability_acceptance.ps1
Test d'acceptation T-011 traÃ§abilitÃ© et mÃ©triques M-008: OK
Test GREEN: tests/m008/validate_m008_traceability_acceptance.ps1
Test requis: tests/m008/validate_m008_traceability_unit.ps1
Tests unitaires T-011 traÃ§abilitÃ© et mÃ©triques M-008: OK
Test GREEN: tests/m008/validate_m008_traceability_unit.ps1
Test requis: tests/m009/validate_m009_precondition_unit.ps1
Tests unitaires du validateur de précondition M-009: OK
Test GREEN: tests/m009/validate_m009_precondition_unit.ps1
Test requis: tests/m010/validate_m010_precondition_unit.ps1
Tests unitaires du validateur de précondition M-010: OK
Test GREEN: tests/m010/validate_m010_precondition_unit.ps1
Test requis: tests/m010/validate_m010_specification_acceptance.ps1
Test d'acceptation de spécification M-010: OK
Test GREEN: tests/m010/validate_m010_specification_acceptance.ps1
Test requis: tests/m010/validate_m010_specification_unit.ps1
Tests unitaires du validateur de spécification M-010: OK
Test GREEN: tests/m010/validate_m010_specification_unit.ps1
Test requis: tests/m010/validate_strategy_candidate_creation_acceptance.ps1
Test d'acceptation de crÃ©ation de stratÃ©gie candidate M-010: OK
Test GREEN: tests/m010/validate_strategy_candidate_creation_acceptance.ps1
Test requis: tests/m010/validate_strategy_candidate_creation_unit.ps1
Tests unitaires de crÃ©ation de stratÃ©gie candidate M-010: OK
Test GREEN: tests/m010/validate_strategy_candidate_creation_unit.ps1
Test requis: tests/m010/validate_strategy_rule_origin_acceptance.ps1
Test d'acceptation des origines de regles de strategie M-010: OK
Test GREEN: tests/m010/validate_strategy_rule_origin_acceptance.ps1
Test requis: tests/m010/validate_strategy_rule_origin_unit.ps1
Tests unitaires des origines de regles de strategie M-010: OK
Test GREEN: tests/m010/validate_strategy_rule_origin_unit.ps1
Test requis: tests/m010/validate_strategy_parameter_calibration_acceptance.ps1
Test d'acceptation des parametres de calibration de strategie M-010: OK
Test GREEN: tests/m010/validate_strategy_parameter_calibration_acceptance.ps1
Test requis: tests/m010/validate_strategy_parameter_calibration_unit.ps1
Tests unitaires des parametres de calibration de strategie M-010: OK
Test GREEN: tests/m010/validate_strategy_parameter_calibration_unit.ps1
Test requis: tests/m010/validate_strategy_compatibility_acceptance.ps1
Test d'acceptation de compatibilitÃ© de stratÃ©gie M-010: OK
Test GREEN: tests/m010/validate_strategy_compatibility_acceptance.ps1
Test requis: tests/m010/validate_strategy_compatibility_unit.ps1
Tests unitaires de compatibilitÃ© de stratÃ©gie M-010: OK
Test GREEN: tests/m010/validate_strategy_compatibility_unit.ps1
Test requis: tests/m010/validate_strategy_candidate_diagnostics_acceptance.ps1
Test d'acceptation des diagnostics de stratÃ©gie candidate M-010: OK
Test GREEN: tests/m010/validate_strategy_candidate_diagnostics_acceptance.ps1
Test requis: tests/m010/validate_strategy_candidate_diagnostics_unit.ps1
Tests unitaires des diagnostics de stratÃ©gie candidate M-010: OK
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
Test requis: tests/m011/validate_m011_precondition_unit.ps1
Tests unitaires de precondition M-011: OK
Test GREEN: tests/m011/validate_m011_precondition_unit.ps1
Test requis: tests/m011/validate_m011_specification_acceptance.ps1
Test d'acceptation de specification M-011: OK
Test GREEN: tests/m011/validate_m011_specification_acceptance.ps1
Test requis: tests/m011/validate_m011_specification_unit.ps1
Tests unitaires de specification M-011: OK
Test GREEN: tests/m011/validate_m011_specification_unit.ps1
Test requis: tests/m011/validate_experiment_planning_acceptance.ps1
Test d'acceptation de planification d'experience M-011: OK
Test GREEN: tests/m011/validate_experiment_planning_acceptance.ps1
Test requis: tests/m011/validate_experiment_planning_unit.ps1
Tests unitaires de planification d'experience M-011: OK
Test GREEN: tests/m011/validate_experiment_planning_unit.ps1
Test requis: tests/m011/validate_data_snapshot_freeze_acceptance.ps1
Test d'acceptation de gel du snapshot de donnees M-011: OK
Test GREEN: tests/m011/validate_data_snapshot_freeze_acceptance.ps1
Test requis: tests/m011/validate_data_snapshot_freeze_unit.ps1
Tests unitaires de gel du snapshot de donnees M-011: OK
Test GREEN: tests/m011/validate_data_snapshot_freeze_unit.ps1
Test requis: tests/m011/validate_cost_environment_freeze_acceptance.ps1
Test d'acceptation de gel couts environnement M-011: OK
Test GREEN: tests/m011/validate_cost_environment_freeze_acceptance.ps1
Test requis: tests/m011/validate_cost_environment_freeze_unit.ps1
Tests unitaires de gel couts environnement M-011: OK
Test GREEN: tests/m011/validate_cost_environment_freeze_unit.ps1
Test requis: tests/m011/validate_experiment_start_lock_acceptance.ps1
Test d'acceptation de demarrage verrouille M-011: OK
Test GREEN: tests/m011/validate_experiment_start_lock_acceptance.ps1
Test requis: tests/m011/validate_experiment_start_lock_unit.ps1
Tests unitaires de demarrage verrouille M-011: OK
Test GREEN: tests/m011/validate_experiment_start_lock_unit.ps1
Test requis: tests/m011/validate_deterministic_backtest_acceptance.ps1
Test d'acceptation de backtest deterministe M-011: OK
Test GREEN: tests/m011/validate_deterministic_backtest_acceptance.ps1
Test requis: tests/m011/validate_deterministic_backtest_unit.ps1
Tests unitaires de backtest deterministe M-011: OK
Test GREEN: tests/m011/validate_deterministic_backtest_unit.ps1
Test requis: tests/m011/validate_experiment_result_acceptance.ps1
Test d'acceptation d'enregistrement de resultat M-011: OK
Test GREEN: tests/m011/validate_experiment_result_acceptance.ps1
Test requis: tests/m011/validate_experiment_result_unit.ps1
Tests unitaires d'enregistrement de resultat M-011: OK
Test GREEN: tests/m011/validate_experiment_result_unit.ps1
Test requis: tests/m011/validate_experiment_retention_acceptance.ps1
Test d'acceptation de conservation resultats negatifs M-011: OK
Test GREEN: tests/m011/validate_experiment_retention_acceptance.ps1
Test requis: tests/m011/validate_experiment_retention_unit.ps1
Tests unitaires de conservation resultats negatifs M-011: OK
Test GREEN: tests/m011/validate_experiment_retention_unit.ps1
Test requis: tests/m011/validate_experiment_reproducibility_acceptance.ps1
Test d'acceptation de reproductibilite M-011: OK
Test GREEN: tests/m011/validate_experiment_reproducibility_acceptance.ps1
Test requis: tests/m011/validate_experiment_reproducibility_unit.ps1
Tests unitaires de reproductibilite M-011: OK
Test GREEN: tests/m011/validate_experiment_reproducibility_unit.ps1
Test requis: tests/m011/validate_experiment_http_contract_acceptance.ps1
Test d'acceptation de contrat HTTP experiences M-011: OK
Test GREEN: tests/m011/validate_experiment_http_contract_acceptance.ps1
Test requis: tests/m011/validate_experiment_http_contract_unit.ps1
Tests unitaires de contrat HTTP experiences M-011: OK
Test GREEN: tests/m011/validate_experiment_http_contract_unit.ps1
Test requis: tests/m011/validate_m011_traceability_acceptance.ps1
Test d'acceptation de tracabilite M-011: OK
Test GREEN: tests/m011/validate_m011_traceability_acceptance.ps1
Test requis: tests/m011/validate_m011_traceability_unit.ps1
Tests unitaires de tracabilite M-011: OK
Test GREEN: tests/m011/validate_m011_traceability_unit.ps1
Test requis: tests/m012/validate_m012_precondition_unit.ps1
Tests unitaires du validateur de précondition M-012: OK
Test GREEN: tests/m012/validate_m012_precondition_unit.ps1
Test requis: tests/m012/validate_m012_specification_acceptance.ps1
Test d'acceptation de spécification M-012: OK
Test GREEN: tests/m012/validate_m012_specification_acceptance.ps1
Test requis: tests/m012/validate_m012_specification_unit.ps1
Tests unitaires du validateur de spécification M-012: OK
Test GREEN: tests/m012/validate_m012_specification_unit.ps1
Test requis: tests/m012/validate_pilot_corpus_acceptance.ps1
Test d'acceptation du corpus pilote reprÃ©sentatif M-012: OK
Test GREEN: tests/m012/validate_pilot_corpus_acceptance.ps1
Test requis: tests/m012/validate_pilot_corpus_unit.ps1
Tests unitaires PilotCoveragePolicy M-012: OK
Test GREEN: tests/m012/validate_pilot_corpus_unit.ps1
Test requis: tests/m012/validate_page_annotation_set_acceptance.ps1
Test d'acceptation du jeu annotÃ© page par page M-012: OK
Test GREEN: tests/m012/validate_page_annotation_set_acceptance.ps1
Test requis: tests/m012/validate_page_annotation_set_unit.ps1
Tests unitaires AnnotationCompletenessPolicy M-012: OK
Test GREEN: tests/m012/validate_page_annotation_set_unit.ps1
Test requis: tests/m012/validate_document_route_benchmark_acceptance.ps1
Test d'acceptation T-005 benchmarks de routes documentaires M-012: OK
Test GREEN: tests/m012/validate_document_route_benchmark_acceptance.ps1
Test requis: tests/m012/validate_document_route_benchmark_unit.ps1
Tests unitaires T-005 benchmarks de routes documentaires M-012: OK
Test GREEN: tests/m012/validate_document_route_benchmark_unit.ps1
Test requis: tests/m012/validate_document_quality_calibration_acceptance.ps1
Test d'acceptation T-006 calibration documentaire M-012: OK
Test GREEN: tests/m012/validate_document_quality_calibration_acceptance.ps1
Test requis: tests/m012/validate_document_quality_calibration_unit.ps1
Tests unitaires T-006 calibration documentaire M-012: OK
Test GREEN: tests/m012/validate_document_quality_calibration_unit.ps1
Test requis: tests/m012/validate_knowledge_search_benchmark_acceptance.ps1
Test d'acceptation T-007 benchmark recherche de connaissances M-012: OK
Test GREEN: tests/m012/validate_knowledge_search_benchmark_acceptance.ps1
Test requis: tests/m012/validate_knowledge_search_benchmark_unit.ps1
Tests unitaires T-007 benchmark recherche de connaissances M-012: OK
Test GREEN: tests/m012/validate_knowledge_search_benchmark_unit.ps1
Test requis: tests/m012/validate_verified_answer_benchmark_acceptance.ps1
Test d'acceptation T-008 benchmark réponses vérifiées M-012: OK
Test GREEN: tests/m012/validate_verified_answer_benchmark_acceptance.ps1
Test requis: tests/m012/validate_verified_answer_benchmark_unit.ps1
Tests unitaires T-008 benchmark réponses vérifiées M-012: OK
Test GREEN: tests/m012/validate_verified_answer_benchmark_unit.ps1
Test requis: tests/m012/validate_llm_benchmark_real_path_acceptance.ps1
Test d'acceptation T-009 benchmark LLM chemin réel M-012: OK
Test GREEN: tests/m012/validate_llm_benchmark_real_path_acceptance.ps1
Test requis: tests/m012/validate_llm_benchmark_real_path_unit.ps1
Tests unitaires T-009 benchmark LLM chemin réel M-012: OK
Test GREEN: tests/m012/validate_llm_benchmark_real_path_unit.ps1
Test requis: tests/m012/validate_strategy_backtest_benchmark_acceptance.ps1
Test d'acceptation T-010 benchmark stratégies et backtests M-012: OK
Test GREEN: tests/m012/validate_strategy_backtest_benchmark_acceptance.ps1
Test requis: tests/m012/validate_strategy_backtest_benchmark_unit.ps1
Tests unitaires T-010 benchmark stratégies et backtests M-012: OK
Test GREEN: tests/m012/validate_strategy_backtest_benchmark_unit.ps1
Test requis: tests/m012/validate_calibration_decisions_acceptance.ps1
Test d'acceptation T-011 decisions calibration promotion M-012: OK
Test GREEN: tests/m012/validate_calibration_decisions_acceptance.ps1
Test requis: tests/m012/validate_calibration_decisions_unit.ps1
Tests unitaires T-011 decisions calibration promotion M-012: OK
Test GREEN: tests/m012/validate_calibration_decisions_unit.ps1
Test requis: tests/m012/validate_m012_traceability_acceptance.ps1
Test d'acceptation T-012 traçabilité M-012: OK
Test GREEN: tests/m012/validate_m012_traceability_acceptance.ps1
Test requis: tests/m012/validate_m012_traceability_unit.ps1
Tests unitaires T-012 traçabilité M-012: OK
Test GREEN: tests/m012/validate_m012_traceability_unit.ps1
Test requis: tests/m013/validate_m013_precondition_unit.ps1
Tests unitaires du validateur de prÃ©condition M-013: OK
Test GREEN: tests/m013/validate_m013_precondition_unit.ps1
Test requis: tests/m009/validate_m009_specification_acceptance.ps1
Test d'acceptation de la spécification M-009: OK
Test GREEN: tests/m009/validate_m009_specification_acceptance.ps1
Test requis: tests/m009/validate_m009_specification_unit.ps1
Tests unitaires du validateur de spécification M-009: OK
Test GREEN: tests/m009/validate_m009_specification_unit.ps1
Test requis: tests/m009/validate_deep_research_planning_acceptance.ps1
Test d'acceptation T-003 planification recherche approfondie M-009: OK
Test GREEN: tests/m009/validate_deep_research_planning_acceptance.ps1
Test requis: tests/m009/validate_deep_research_planning_unit.ps1
Tests unitaires T-003 planification recherche approfondie M-009: OK
Test GREEN: tests/m009/validate_deep_research_planning_unit.ps1
Test requis: tests/m009/validate_multi_query_evidence_collection_acceptance.ps1
Test d'acceptation T-004 collecte multi-requÃªtes diversifiÃ©e M-009: OK
Test GREEN: tests/m009/validate_multi_query_evidence_collection_acceptance.ps1
Test requis: tests/m009/validate_multi_query_evidence_collection_unit.ps1
Tests unitaires T-004 collecte multi-requÃªtes diversifiÃ©e M-009: OK
Test GREEN: tests/m009/validate_multi_query_evidence_collection_unit.ps1
Test requis: tests/m009/validate_verified_claim_dependency_resolution_acceptance.ps1
Test d'acceptation T-005 dÃ©pendances de claims vÃ©rifiÃ©s M-009: OK
Test GREEN: tests/m009/validate_verified_claim_dependency_resolution_acceptance.ps1
Test requis: tests/m009/validate_verified_claim_dependency_resolution_unit.ps1
Tests unitaires T-005 dÃ©pendances de claims vÃ©rifiÃ©s M-009: OK
Test GREEN: tests/m009/validate_verified_claim_dependency_resolution_unit.ps1
Test requis: tests/m009/validate_deep_contradiction_classification_acceptance.ps1
Test d'acceptation T-006 classification de contradictions conditionnelles M-009: OK
Test GREEN: tests/m009/validate_deep_contradiction_classification_acceptance.ps1
Test requis: tests/m009/validate_deep_contradiction_classification_unit.ps1
Tests unitaires T-006 classification de contradictions conditionnelles M-009: OK
Test GREEN: tests/m009/validate_deep_contradiction_classification_unit.ps1
Test requis: tests/m009/validate_insufficient_deep_coverage_acceptance.ps1
Test d'acceptation T-007 couverture approfondie insuffisante M-009: OK
Test GREEN: tests/m009/validate_insufficient_deep_coverage_acceptance.ps1
Test requis: tests/m009/validate_insufficient_deep_coverage_unit.ps1
Tests unitaires T-007 couverture approfondie insuffisante M-009: OK
Test GREEN: tests/m009/validate_insufficient_deep_coverage_unit.ps1
Test requis: tests/m009/validate_multi_source_synthesis_acceptance.ps1
Test d'acceptation T-008 synthÃ¨se multi-sources traÃ§able M-009: OK
Test GREEN: tests/m009/validate_multi_source_synthesis_acceptance.ps1
Test requis: tests/m009/validate_multi_source_synthesis_unit.ps1
Tests unitaires T-008 synthÃ¨se multi-sources traÃ§able M-009: OK
Test GREEN: tests/m009/validate_multi_source_synthesis_unit.ps1
Test requis: tests/m009/validate_deep_research_http_contract_acceptance.ps1
Test d'acceptation T-009 endpoint recherche approfondie M-009: OK
Test GREEN: tests/m009/validate_deep_research_http_contract_acceptance.ps1
Test requis: tests/m009/validate_deep_research_http_contract_unit.ps1
Tests unitaires T-009 endpoint recherche approfondie M-009: OK
Test GREEN: tests/m009/validate_deep_research_http_contract_unit.ps1
Test requis: tests/m009/validate_deep_research_metrics_acceptance.ps1
Test d'acceptation T-010 mÃ©triques recherche approfondie M-009: OK
Test GREEN: tests/m009/validate_deep_research_metrics_acceptance.ps1
Test requis: tests/m009/validate_deep_research_metrics_unit.ps1
Tests unitaires T-010 mÃ©triques recherche approfondie M-009: OK
Test GREEN: tests/m009/validate_deep_research_metrics_unit.ps1
Test requis: tests/m009/validate_m009_traceability_acceptance.ps1
Test d'acceptation T-011 traÃ§abilitÃ© et gates M-009: OK
Test GREEN: tests/m009/validate_m009_traceability_acceptance.ps1
Test requis: tests/m009/validate_m009_traceability_unit.ps1
Tests unitaires T-011 traÃ§abilitÃ© et gates M-009: OK
Test GREEN: tests/m009/validate_m009_traceability_unit.ps1
Gate test GREEN: 23 validation(s), 259 test(s).
~~~

### lint

~~~text
Validation requise: scripts/validate_m000_precondition_report.ps1
Rapport de précondition M-000 valide: 6 entrées contrôlées.
Validation GREEN: scripts/validate_m000_precondition_report.ps1
Validation requise: scripts/validate_adr_system.ps1
Système ADR valide: 23 ADR contrôlées, 19 décisions section 3 matérialisées.
Validation GREEN: scripts/validate_adr_system.ps1
Validation requise: scripts/validate_task_system.ps1
Système de tâches valide: 14 milestone(s), 146 tâche(s) contrôlée(s).
Validation GREEN: scripts/validate_task_system.ps1
Validation requise: scripts/validate_traceability.ps1
Matrice de traçabilité valide: 140 exigence(s) contrôlée(s).
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
Frontières d'import M-001 valides: 178 fichier(s), 1081 import(s) contrôlé(s).
Validation GREEN: scripts/validate_architecture_boundaries.ps1
Gate lint GREEN: 24 validation(s), 0 test(s).
~~~
