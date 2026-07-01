# Journal M-008

## Planification initiale

- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, milestone `M-008 - Conversation produit`.
- Dépendance amont: M-007, présent dans `master` au commit `e211a7ea27050a1226203cec2529c217f9f7cfc4` après `git fetch origin --prune` et réalignement de `master` par `git fetch origin master:master`.
- Précondition observée pendant la planification: `scripts/test.ps1` est RED sur `tests/m003/validate_m003_precondition_acceptance.ps1`, car `scripts/validate_m003_precondition.ps1` refuse la branche `codex/plan-milestone-m008-conversation-produit`; `scripts/lint.ps1` est GREEN avec `16 validation(s), 0 test(s)`; `scripts/validate_task_system.ps1` est GREEN avec `8 milestone(s), 77 tâche(s) contrôlée(s)` avant création de M-008; `git diff --check` est GREEN.
- Découpage retenu: précondition, spécification CV, conversations et tours append-only, snapshot de contexte sans preuve factuelle, résolution des références de suivi, routage de mode justifié, revalidation RA des assertions historiques réutilisées et rattachement des réponses vérifiées, présentation produit des citations et statuts depuis un DTO public RA distinct de `VerifiedResearchOutcome`, endpoints internes de conversation, endpoint compatible `/v1/chat/completions`, puis traçabilité et métriques.
- ADR: aucune nouvelle ADR planifiée à ce stade; les tâches appliquent les ADR existantes et exigent une nouvelle ADR si une décision structurante change la politique de branche et préconditions, la rétention conversationnelle, la compatibilité chat publique, le contrat `VerifiedResearchOutcome` ou l'observabilité persistante.
