# T-007 - Valider la stratégie candidate avec diagnostics

## Milestone
- Nom: M-010 - Stratégie candidate attribuée.
- Source: M-010, machine d'états `DRAFT -> SPECIFIED -> VALIDATING -> COMPILABLE|INCOMPLETE|INCONSISTENT` et politiques de complétude.
- Objectif métier: donner un verdict explicite et auditable avant compilation.

## Contexte DDD
- Domaine: conception de stratégies candidates attribuées.
- Bounded context: SD.
- Objectif métier: qualifier une stratégie comme complète, incomplète ou incohérente en conservant chaque diagnostic bloquant.
- Langage ubiquitaire: validation de stratégie, complétude, incohérence, diagnostic bloquant, conflit non résolu, paramètre non résolu, règle non attribuée.
- Invariants critiques: une stratégie sans règle requise ne devient pas compilable; un conflit bloquant non résolu interdit `COMPILABLE`; une stratégie `INCOMPLETE` ou `INCONSISTENT` est conservée avec ses diagnostics.
- Garde-fous: pas de succès partiel silencieux; pas de suppression de versions négatives; pas de diagnostic textuel non typé; pas de passage direct de `DRAFT` à `COMPILABLE`.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-004, T-005 et T-006.
- Présence des milestones amont dans master: M-009 présent dans `master`.
- Décisions manquantes: DDD-ADR-010 couvre la conservation des versions négatives et supersédées.
- Risques: compiler malgré un paramètre bloquant; perdre les diagnostics lors d'une nouvelle validation; traiter une stratégie incohérente comme simple brouillon.

## Tâches
### T-007 - Valider la stratégie candidate avec diagnostics
- But métier: produire un verdict SD explicite qui indique si la stratégie peut être compilée ou pourquoi elle reste bloquée.
- Portée DDD: politique `StrategyCompletenessPolicy`, diagnostics de compilation, transitions d'état, commandes `ValidateStrategyCandidate`, `RecordStrategyConflict` et `ResolveStrategyConflict`, événements de validation et rejet.
- Scénario BDD:
  - Given une stratégie candidate contient une règle attribuée, un paramètre bloquant non résolu et un conflit documentaire bloquant.
  - When la validation de stratégie est demandée.
  - Then la stratégie passe à `INCOMPLETE` avec deux diagnostics bloquants conservés.
- Tests d'acceptation à écrire: `tests/m010/validate_strategy_candidate_diagnostics_acceptance.ps1`, qui échoue tant qu'un verdict `COMPILABLE` peut être obtenu avec un diagnostic bloquant.
- Tests unitaires à écrire: tests de transitions d'état, diagnostic typé, conflit bloquant, conflit résolu, paramètre bloquant, règle manquante, version négative conservée et refus de transition illégale.
- Implémentation attendue: créer la politique de complétude, le modèle `CompilationDiagnostic`, la validation de l'agrégat et la conservation des versions `INCOMPLETE` ou `INCONSISTENT` dans le dépôt.
- Invariants et garde-fous: aucun diagnostic effacé sans résolution explicite; aucune transition illégale; aucun verdict `COMPILABLE` avec blocage; aucune réécriture silencieuse d'une version négative.
- Dépendances: T-006; DDD-ADR-010; `StrategyRepository`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_strategy_candidate_diagnostics_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_strategy_candidate_diagnostics_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m010): couvrir diagnostics strategie candidate`
- Commit GREEN: `feat(m010): valider strategie candidate avec diagnostics`
