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
