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

## Exécution

### T-001 - Précondition GREEN M-010

- Commit RED: `938ec5d5 test(m010): couvrir la precondition green strategie candidate`.
- Reprise main-agent: arrêt de l'ancien arbre `scripts/test.ps1` lancé par le worker après plus de 60 minutes sans verdict exploitable.
- Implémentation: création de `scripts/validate_m010_precondition.ps1`, création de `docs/governance/m010_precondition_green.md`, enrôlement des tests M-010 et autorisation explicite de la branche `codex/milestone-m010-strategie-candidate-attribuee` dans les validateurs de précondition M-003 à M-009.
- Validations GREEN: `tests/m010/validate_m010_precondition_unit.ps1`, `scripts/validate_m010_precondition.ps1 -Path .\docs\governance\m010_precondition_green.md`, `tests/m010/validate_m010_precondition_acceptance.ps1`.
- Gate M-010: le rapport canonique `docs/governance/m010_precondition_green.md` consigne `scripts/test.ps1` GREEN avec `18 validation(s), 192 test(s)` et `scripts/lint.ps1` GREEN avec `18 validation(s), 0 test(s)`.
- Contrôle de propreté: `git diff --check` GREEN après retrait des lignes vides finales ajoutées par le worker.

### T-002 - Spécification de stratégie candidate attribuée

- Précondition ciblée: `tests/m010/validate_m010_precondition_acceptance.ps1` GREEN et `tests/m010/validate_m010_precondition_unit.ps1` GREEN.
- Commit RED: `159db19c test(m010): couvrir la specification strategie candidate`.
- RED utile: `tests/m010/validate_m010_specification_acceptance.ps1` échoue sur le contrat exécutable absent; `tests/m010/validate_m010_specification_unit.ps1` échoue sur le validateur absent.
- ADR: aucune nouvelle ADR; T-002 applique `ADR-010`, `DDD-ADR-009` et `DDD-ADR-010` sans changer leur décision.
- Implémentation: publication de `docs/specs/m010_strategie_candidate_attribuee.md`, création de `scripts/validate_m010_specification.ps1`, enrôlement dans `scripts/test.ps1` et `scripts/lint.ps1`, et rattachement `REQ-M010-002` dans `docs/traceability/matrix.md`.
- Validations ciblées GREEN: `tests/m010/validate_m010_specification_acceptance.ps1`, `tests/m010/validate_m010_specification_unit.ps1`, `scripts/validate_m010_specification.ps1`, `scripts/validate_traceability.ps1` avec `106 exigence(s) contrôlée(s)`, et `scripts/lint.ps1` avec `19 validation(s), 0 test(s)`.
