# Journal M-001 - Frontières DDD et contrats publiés

## Branche
- Branche: `feature/milestone-m001-frontieres-contrats`.
- Base: `master`.
- Remote: `origin`.

## Précondition observée lors de la planification
- Date: 2026-06-25.
- `git fetch origin --prune`: GREEN.
- Présence de M-000 dans `master`: GREEN, `docs/tasks/milestone_000`, les scripts M-000, les ADR et les specs sont visibles.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`: RED sur `scripts/validate_task_system.ps1`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`: RED sur `scripts/validate_task_system.ps1`.
- Cause RED observée: `Titre de tâche invalide ou absent: 0001_verifier_precondition_green.md`.

## Tâches planifiées
- T-001 - Vérifier la précondition GREEN de M-001.
- T-002 - Publier la spécification des frontières DDD.
- T-003 - Déclarer les contextes et propriétaires de données.
- T-004 - Publier les identifiants opaques et versions de contrats.
- T-005 - Publier CanonicalSourceRef et SourceLocator.
- T-006 - Publier EvidenceRef et VerifiedClaimRef.
- T-007 - Publier VerifiedResearchOutcome vers la stratégie.
- T-008 - Publier StrategySnapshot et ExperimentResult.
- T-009 - Publier l'enveloppe d'événement versionnée.
- T-010 - Interdire les couplages intercontextes.
- T-011 - Relier M-001 à la traçabilité et aux gates.

## Suivi d'exécution
- Statut: T-001 à T-010 livrées en GREEN; T-011 relie la clôture M-001 à la traçabilité et aux gates.

| Tâche | Commit RED | Commit GREEN | ADR consultées | ADR créée | Validations GREEN déclarées |
|---|---|---|---|---|---|
| T-001 - Vérifier la précondition GREEN de M-001 | `3951614` | `0335a23` | ADR-010 | Aucune | `scripts/validate_task_system.ps1`; `scripts/test.ps1`; `scripts/lint.ps1` |
| T-002 - Publier la spécification des frontières DDD | `84fd395` | `8c94cb0` | DDD-ADR-001; DDD-ADR-002; DDD-ADR-003 | Aucune | `tests/m001/validate_m001_specification_acceptance.ps1`; `tests/m001/validate_m001_specification_unit.ps1`; `scripts/test.ps1`; `scripts/lint.ps1` |
| T-003 - Déclarer les contextes et propriétaires de données | `815eede` | `65de29f` | DDD-ADR-001 | Aucune | `tests/m001/validate_context_modules_acceptance.ps1`; `tests/m001/validate_context_registry_unit.ps1`; `scripts/test.ps1`; `scripts/lint.ps1` |
| T-004 - Publier les identifiants opaques et versions de contrats | `801a324` | `7efb405` | DDD-ADR-001; DDD-ADR-002; DDD-ADR-003; ADR-010 | Aucune | `tests/m001/validate_contract_identity_acceptance.ps1`; `tests/m001/validate_contract_identity_unit.ps1`; `scripts/test.ps1`; `scripts/lint.ps1` |
| T-005 - Publier CanonicalSourceRef et SourceLocator | `f971e23` | `0d3dc26` | DDD-ADR-003 | Aucune | `tests/m001/validate_source_contracts_acceptance.ps1`; `tests/m001/validate_source_locator_unit.ps1`; `scripts/test.ps1`; `scripts/lint.ps1` |
| T-006 - Publier EvidenceRef et VerifiedClaimRef | `fa8bee6` | `890604f` | DDD-ADR-005 | Aucune | `tests/m001/validate_evidence_claim_contracts_acceptance.ps1`; `tests/m001/validate_evidence_claim_contracts_unit.ps1`; `scripts/test.ps1`; `scripts/lint.ps1` |
| T-007 - Publier VerifiedResearchOutcome vers la stratégie | `177d4b7` | `630459e` | DDD-ADR-001; DDD-ADR-002; DDD-ADR-005; DDD-ADR-007 | Aucune | `tests/m001/validate_research_outcome_contract_acceptance.ps1`; `tests/m001/validate_research_outcome_contract_unit.ps1`; `scripts/test.ps1`; `scripts/lint.ps1` |
| T-008 - Publier StrategySnapshot et ExperimentResult | `885af82` | `84c924b` | DDD-ADR-009 | Aucune | `tests/m001/validate_strategy_experiment_contracts_acceptance.ps1`; `tests/m001/validate_strategy_experiment_contracts_unit.ps1`; `scripts/test.ps1`; `scripts/lint.ps1` |
| T-009 - Publier l'enveloppe d'événement versionnée | `f9fc133` | `2b39682` | DDD-ADR-006; DDD-ADR-008 | Aucune | `tests/m001/validate_event_envelope_acceptance.ps1`; `tests/m001/validate_event_envelope_unit.ps1`; `scripts/test.ps1`; `scripts/lint.ps1` |
| T-010 - Interdire les couplages intercontextes | `1acee47` | `dff4da5` | DDD-ADR-001; ADR-011 | ADR-011 | `tests/m001/validate_architecture_boundaries_acceptance.ps1`; `tests/m001/validate_architecture_boundaries_unit.ps1`; `scripts/validate_architecture_boundaries.ps1`; `scripts/test.ps1`; `scripts/lint.ps1` |
| T-011 - Relier M-001 à la traçabilité et aux gates | `d5c6fdd` | `ab2c523` | ADR-010; DDD-ADR-001; DDD-ADR-002; DDD-ADR-003; DDD-ADR-005; DDD-ADR-006; DDD-ADR-007; DDD-ADR-008; DDD-ADR-009 | Aucune | `tests/m001/validate_m001_traceability_acceptance.ps1`; `tests/m001/validate_m001_traceability_unit.ps1`; `scripts/validate_traceability.ps1`; `scripts/validate_definition_of_done.ps1`; `scripts/test.ps1`; `scripts/lint.ps1` |

## Clôture T-011
- Scénario BDD: Given les contrats publiés et tests d'architecture M-001 sont implémentés; When les gates de clôture sont exécutées; Then chaque exigence M-001 est reliée à une preuve vérifiable et la clôture est refusée si une preuve manque.
- RED T-011 confirmé: `tests/m001/validate_m001_traceability_acceptance.ps1` et `tests/m001/validate_m001_traceability_unit.ps1` échouaient car `scripts/validate_traceability.ps1` acceptait une matrice sans exigence M-001 livrée.
- ADR: aucune ADR créée; T-011 applique ADR-010 et réutilise les ADR DDD existantes des contrats tracés sans changer leur sens.
- Risque de clôture traité: aucune ligne `Couvert` M-001 ne peut rester sans test, commande PowerShell vérifiable, code existant et ADR ou justification d'absence d'ADR.
