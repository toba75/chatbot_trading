# Journal M-006

## Clôture T-001

- Scénario BDD: Given M-004 et M-005 sont présents dans `master`; When les gates de précondition M-006 sont exécutées; Then M-006 ne peut commencer que si les validations, la traçabilité, les ADR, les frontières d'architecture et les preuves M-005 sont GREEN.
- Commit RED: `719977eef41061d13c0b430c5c03bcd6ab40619b` (`test(m006): couvrir la precondition green des claims`).
- Commit GREEN: `test(m006): etablir la precondition green des claims`.
- Implémentation: `scripts/validate_m006_precondition.ps1` vérifie la branche autorisée, l'alignement `origin/master`, la présence des artefacts M-004/M-005 dans `master`, l'exécution conclue de `scripts/test.ps1` et `scripts/lint.ps1`, puis publie `docs/governance/m006_precondition_green.md`.
- Garde-fous livrés: timeout de gate explicite et non silencieux; rapport hors dépôt refusé; statut GREEN impossible sans preuve de commande; branche M-006 autorisée sans accepter une branche amont non fusionnée comme preuve; corrections de récursion M-003/M-004 pour éviter que les préconditions imbriquées relancent indéfiniment la gate globale.
- Traçabilité et gates: `scripts/test.ps1` enrôle les tests `tests/m006/validate_m006_precondition_acceptance.ps1` et `tests/m006/validate_m006_precondition_unit.ps1`; les préconditions M-003, M-004, M-005 et M-006 disposent chacune d'une garde d'exécution imbriquée.
- ADR: non requise; T-001 applique ADR-010 et les décisions existantes de gouvernance des gates sans changer leur sens.
- Validations GREEN: `tests/m003/validate_m003_precondition_unit.ps1`; `tests/m004/validate_m004_precondition_unit.ps1`; `tests/m005/validate_m005_precondition_unit.ps1`; `tests/m006/validate_m006_precondition_unit.ps1`; `tests/m003/validate_m003_precondition_acceptance.ps1`; `tests/m004/validate_m004_precondition_acceptance.ps1`; `tests/m005/validate_m005_precondition_acceptance.ps1`; `tests/m006/validate_m006_precondition_acceptance.ps1`; `scripts/validate_m006_precondition.ps1 -Path .\docs\governance\m006_precondition_green.md` (`2 gate(s), 7 artefact(s) amont vérifié(s)`); `git diff --check`; `scripts/lint.ps1` (`14 validation(s), 0 test(s)`); `scripts/test.ps1` (`14 validation(s), 116 test(s)`).
- Risques résiduels: la gate globale reste longue parce qu'elle réexécute les préconditions amont; aucun risque fonctionnel bloquant identifié pour démarrer T-002.
