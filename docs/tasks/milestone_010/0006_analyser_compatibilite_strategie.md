# T-006 - Analyser la compatibilité de stratégie

## Milestone
- Nom: M-010 - Stratégie candidate attribuée.
- Source: M-010, service `StrategyCompatibilityAnalyzer`, politiques `PointInTimeDataPolicy`, `ExecutionFeasibilityPolicy` et `StrategyCompatibilityPolicy`.
- Objectif métier: rendre visibles les incompatibilités entre preuves, mandat, données, signal, exécution et risque avant compilation.

## Contexte DDD
- Domaine: conception de stratégies candidates attribuées.
- Bounded context: SD.
- Objectif métier: empêcher qu'une stratégie soit compilable si ses règles utilisent des données indisponibles, un horizon incompatible ou une contrainte de risque non respectée.
- Langage ubiquitaire: compatibilité, horizon du signal, horizon de détention, disponibilité point-in-time, modèle de coûts, liquidité, levier, contrainte de mandat, portée des preuves.
- Invariants critiques: le signal n'utilise pas une information indisponible au moment de la décision; l'univers reste compatible avec la portée des preuves; le sizing et le risque respectent levier, liquidité, marge et distribution.
- Garde-fous: pas de look-ahead bias silencieux; pas de coût implicite; pas de mandat ignoré; pas de compatibilité déclarée sans finding auditable.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-004 et T-005.
- Présence des milestones amont dans master: M-009 présent dans `master`.
- Décisions manquantes: aucune tant que l'analyse ne lance pas d'expérience EX.
- Risques: mélanger contrôle logiciel et validation scientifique; transformer un warning en succès; ignorer la contrainte utilisateur au profit d'une règle documentaire.

## Tâches
### T-006 - Analyser la compatibilité de stratégie
- But métier: produire des findings de compatibilité qui bloquent la compilation quand les règles ne respectent pas les contraintes documentaires, temporelles ou opérationnelles.
- Portée DDD: `StrategyCompatibilityAnalyzer`, `CompatibilityFinding`, politiques de données point-in-time, faisabilité d'exécution, mandat, coûts, liquidité et portée des preuves.
- Scénario BDD:
  - Given une règle de signal utilise des données publiées après le moment de décision.
  - When l'analyse de compatibilité est exécutée.
  - Then un finding bloquant `POINT_IN_TIME_VIOLATION` est enregistré et la stratégie ne peut pas devenir `COMPILABLE`.
- Tests d'acceptation à écrire: `tests/m010/validate_strategy_compatibility_acceptance.ps1`, qui échoue tant qu'une violation point-in-time ou une contrainte de mandat ignorée ne bloque pas la stratégie.
- Tests unitaires à écrire: tests de `StrategyCompatibilityAnalyzer` pour horizon signal/détention, fréquence de données/décision, disponibilité point-in-time, coûts, turnover, liquidité, levier, contraintes du mandat et portée des preuves.
- Implémentation attendue: créer les objets `CompatibilityFinding`, les politiques de compatibilité, les ports `MarketCalendarCatalog` et `DataAvailabilityCatalog` abstraits, puis rattacher les findings au cycle de validation de `StrategyCandidate`.
- Invariants et garde-fous: aucun finding non typé; aucun accès à données de marché réelles; aucun fallback de calendrier; aucune contrainte de mandat ignorée.
- Dépendances: T-005; `StrategyMandate`; `DataRequirement`; DDD-ADR-007.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_strategy_compatibility_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_strategy_compatibility_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m010): couvrir compatibilite strategie`
- Commit GREEN: `feat(m010): analyser compatibilite strategie`
