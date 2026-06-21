# Matrice de traçabilité initiale M-000

## Scénario BDD

- Given une exigence normative issue de la spécification v4.1 ou du plan de milestones.
- When la matrice de traçabilité est contrôlée.
- Then l'exigence possède un statut, une preuve de test, un artefact cible et une référence ADR explicite ou une justification d'absence d'ADR.

## Statuts autorisés

- `Couvert`: exigence reliée à une commande de validation vérifiable.
- `Partiel`: exigence tracée mais couverture volontairement incomplète.
- `Planifié`: exigence visible et rattachée à une tâche non exécutée.
- `Hors périmètre M-000`: exigence explicitement exclue du milestone courant.

## Matrice

| Exigence | Source | Statut | Test | Commande | Code | ADR | Justification ADR |
|---|---|---|---|---|---|---|---|
| REQ-M000-001 | docs/specs/plan_implementation_milestones_workstreams.md | Couvert | tests/governance/validate_m000_precondition_report_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m000_precondition_report.ps1 -Path .\docs\governance\m000_precondition_green_initiale.md | scripts/validate_m000_precondition_report.ps1 | Non requise | Aucune décision structurante nouvelle: la ligne versionne une preuve de précondition locale. |
| REQ-M000-002 | docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md | Couvert | tests/governance/validate_adr_system_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_adr_system.ps1 | scripts/validate_adr_system.ps1 | ADR-001; ADR-002; ADR-003; ADR-004; ADR-005; ADR-006; ADR-007; ADR-008; ADR-009; DDD-ADR-001; DDD-ADR-002; DDD-ADR-003; DDD-ADR-004; DDD-ADR-005; DDD-ADR-006; DDD-ADR-007; DDD-ADR-008; DDD-ADR-009; DDD-ADR-010 | Le registre ADR canonique matérialise les décisions structurantes existantes sans en changer le sens. |
| REQ-M000-003 | docs/specs/plan_implementation_milestones_workstreams.md | Couvert | tests/governance/validate_task_system_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_task_system.ps1 | scripts/validate_task_system.ps1 | Non requise | Aucune décision structurante nouvelle: la convention de tâches applique le processus M-000. |
| REQ-M000-004 | docs/tasks/milestone_000/0004_publier_matrice_tracabilite_initiale.md | Couvert | tests/governance/validate_traceability_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1 | scripts/validate_traceability.ps1 | Non requise | Aucune décision structurante nouvelle: le validateur rend exécutable la tâche T-004. |
| REQ-M000-005 | docs/tasks/milestone_000/0004_publier_matrice_tracabilite_initiale.md | Couvert | tests/governance/validate_traceability_unit.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\governance\validate_traceability_unit.ps1 | scripts/validate_traceability.ps1 | Non requise | Aucune décision structurante nouvelle: les invariants de matrice sont des contrôles de gouvernance locale. |
| REQ-M000-006 | docs/tasks/milestone_000/0005_definir_achevement_transverse_verifiable.md | Couvert | tests/governance/validate_definition_of_done_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_definition_of_done.ps1 | scripts/validate_definition_of_done.ps1 | Non requise | Aucune décision structurante nouvelle: la définition d'achèvement rend exécutables les règles BDD/TDD et critères de terminé déjà présents. |
| REQ-M000-007 | docs/tasks/milestone_000/0006_assembler_commandes_validation_initiales.md | Couvert | tests/governance/validate_m000_validation_commands_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1 | scripts/test.ps1 | Non requise | Aucune décision structurante nouvelle: la gate de test orchestre les validateurs M-000 existants et les tests de gouvernance sans changer l'architecture. |
| REQ-M000-008 | docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md | Hors périmètre M-000 | docs/tasks/milestone_000/0004_publier_matrice_tracabilite_initiale.md | Non applicable: M-000 ne livre pas de code métier. | docs/tasks/milestone_000/0004_publier_matrice_tracabilite_initiale.md | Non requise | Aucune décision structurante nouvelle: l'absence de code métier est explicite pour ce milestone de gouvernance. |
| REQ-M000-009 | docs/tasks/milestone_000/0005_definir_achevement_transverse_verifiable.md | Couvert | tests/governance/validate_definition_of_done_unit.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\governance\validate_definition_of_done_unit.ps1 | scripts/validate_definition_of_done.ps1 | Non requise | Aucune décision structurante nouvelle: les tests unitaires contrôlent les invariants du validateur local. |
| REQ-M000-010 | docs/governance/m000_validation_commands.md | Couvert | tests/governance/validate_m000_validation_commands_unit.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1 | scripts/lint.ps1 | Non requise | Aucune décision structurante nouvelle: la gate de lint exécute les validateurs M-000 requis sans introduire de politique d'architecture applicative. |
