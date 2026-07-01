# Journal M-008

## Planification initiale

- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, milestone `M-008 - Conversation produit`.
- Dépendance amont: M-007, présent dans `master` au commit `e211a7ea27050a1226203cec2529c217f9f7cfc4` après `git fetch origin --prune` et réalignement de `master` par `git fetch origin master:master`.
- Précondition observée pendant la planification: `scripts/test.ps1` est RED sur `tests/m003/validate_m003_precondition_acceptance.ps1`, car `scripts/validate_m003_precondition.ps1` refuse la branche `codex/plan-milestone-m008-conversation-produit`; `scripts/lint.ps1` est GREEN avec `16 validation(s), 0 test(s)`; `scripts/validate_task_system.ps1` est GREEN avec `8 milestone(s), 77 tâche(s) contrôlée(s)` avant création de M-008; `git diff --check` est GREEN.
- Découpage retenu: précondition, spécification CV, conversations et tours append-only, snapshot de contexte sans preuve factuelle, résolution des références de suivi, routage de mode justifié, revalidation RA des assertions historiques réutilisées et rattachement des réponses vérifiées, présentation produit des citations et statuts depuis un DTO public RA distinct de `VerifiedResearchOutcome`, endpoints internes de conversation, endpoint compatible `/v1/chat/completions`, puis traçabilité et métriques.
- ADR: aucune nouvelle ADR planifiée à ce stade; les tâches appliquent les ADR existantes et exigent une nouvelle ADR si une décision structurante change la politique de branche et préconditions, la rétention conversationnelle, la compatibilité chat publique, le contrat `VerifiedResearchOutcome` ou l'observabilité persistante.

## T-001 - Précondition GREEN M-008

- Scénario BDD: Given M-007 est présent dans `master`; When les gates de précondition M-008 sont exécutées sur une branche M-008; Then M-008 ne peut commencer que si les validateurs amont acceptent explicitement la branche aval et si `test`, `lint`, traçabilité, ADR et frontières d'architecture sont GREEN.
- Vérification initiale: `git fetch origin --prune` GREEN; `git ls-tree -r --name-only master -- docs/tasks/milestone_007 docs/specs/m007_reponse_documentaire_verifiee.md scripts tests/m007` GREEN; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1` RED sur `tests/m003/validate_m003_precondition_acceptance.ps1`, car la branche M-008 courante n'est pas encore autorisée par les validateurs amont.
- ADR: non requise. La tâche n'introduit pas une nouvelle politique durable; elle applique la politique existante de précondition explicite au jalon aval M-008.
- RED: `a148e192 test(m008): couvrir la precondition green conversation`.
- GREEN: `tests/m008/validate_m008_precondition_unit.ps1` GREEN; `tests/m008/validate_m008_precondition_acceptance.ps1` GREEN; `scripts/validate_m008_precondition.ps1 -Path .\docs\governance\m008_precondition_green.md` GREEN avec `Gate test GREEN: 16 validation(s), 150 test(s).` et `Gate lint GREEN: 16 validation(s), 0 test(s).`
- Rapport produit: `docs/governance/m008_precondition_green.md`.
