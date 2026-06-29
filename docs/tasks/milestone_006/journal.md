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

## Clôture T-002

- Scénario BDD: Given des preuves candidates KA avec `SourceLocator` résolvable; When la spécification M-006 est publiée; Then chaque comportement de claim nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.
- Commit RED: `9a04d2b` (`test(m006): couvrir la specification des claims verifiables`).
- RED T-002 confirmé: `tests/m006/validate_m006_specification_acceptance.ps1` et `tests/m006/validate_m006_specification_unit.ps1` échouaient tant que `scripts/validate_m006_specification.ps1` et `docs/specs/m006_claims_verifiables.md` étaient absents.
- Implémentation: `docs/specs/m006_claims_verifiables.md` publie la mission EG, les agrégats `Claim`, `VerificationCase` et `DependencyGroup`, les objets-valeur, politiques, états, ports, événements EG, API publiques, erreurs, métriques, exclusions et comportements exécutables EG-001 à EG-009.
- Garde-fous publiés: `VERIFIED` exige une preuve directe admissible; la portée du claim ne dépasse pas la portée commune des preuves; le LLM propose et la politique décide; aucun claim EG n'est stocké dans l'index documentaire; EG consomme `KnowledgeSearchPort` sans accès direct à Qdrant; aucun score n'est traité comme verdict métier.
- Traçabilité et gates: `scripts/validate_m006_specification.ps1` est enrôlé dans `scripts/lint.ps1` et `scripts/test.ps1`; `REQ-M006-001` et `REQ-M006-002` sont présents dans `docs/traceability/matrix.md`; les compteurs de gates impactés sont alignés sur `15 validation(s)`, `118 test(s)` en gate globale et `112 test(s)` en précondition M-003 imbriquée.
- ADR: non requise; T-002 applique ADR-006, ADR-010, DDD-ADR-003, DDD-ADR-005, DDD-ADR-007 et DDD-ADR-010 sans changer leur sens.
- Validations GREEN: `tests/m006/validate_m006_specification_acceptance.ps1`; `tests/m006/validate_m006_specification_unit.ps1`; `scripts/validate_m006_specification.ps1`; `scripts/validate_traceability.ps1` (`65 exigence(s)`); `tests/m004/validate_m004_traceability_acceptance.ps1`; `tests/m003/validate_m003_precondition_acceptance.ps1`; `scripts/lint.ps1` (`15 validation(s), 0 test(s)`); `scripts/test.ps1` (`15 validation(s), 118 test(s)`).
- Risques résiduels: aucun risque résiduel identifié pour la publication de spécification; l'implémentation applicative des claims reste portée par T-003 à T-009, puis reliée aux métriques finales par T-010.
