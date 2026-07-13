# T-008 - Compiler une stratégie candidate déterministe

## Milestone
- Nom: M-010 - Stratégie candidate attribuée.
- Source: M-010, service `StrategyCompiler`, commande `CompileStrategyCandidate` et invariant de déterminisme.
- Objectif métier: transformer une stratégie validée en représentation intermédiaire exécutable sans lancer de backtest.

## Contexte DDD
- Domaine: conception de stratégies candidates attribuées.
- Bounded context: SD.
- Objectif métier: produire une forme compilée stable à partir de règles déterministes, d'origines vérifiées et de paramètres résolus.
- Langage ubiquitaire: compilation, représentation intermédiaire, règle déterministe, graine explicite, statut `COMPILABLE`, backend de compilation, refus de compilation.
- Invariants critiques: une stratégie compilée ne contient aucun paramètre bloquant non résolu; toute règle compilée est déterministe ou déclare son mécanisme aléatoire et sa graine; le compilateur ne lance pas le backtest.
- Garde-fous: pas de backend implicite; pas de correction automatique d'expression; pas d'exécution de marché; pas de compilation si le statut n'est pas `COMPILABLE`.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-007.
- Présence des milestones amont dans master: M-009 présent dans `master`.
- Décisions manquantes: aucune si la représentation intermédiaire reste un contrat SD interne.
- Risques: confondre compiler et expérimenter; accepter une expression non déterministe; faire dépendre le domaine d'une bibliothèque de backtest.

## Tâches
### T-008 - Compiler une stratégie candidate déterministe
- But métier: rendre une stratégie candidate prête pour snapshot sans déclencher l'expérimentation.
- Portée DDD: `StrategyCompiler`, port `StrategyCompilerBackend`, port `RuleExpressionValidator`, représentation intermédiaire compilée, événement `StrategyCompiled` et diagnostic `StrategyCompilationRejected`.
- Scénario BDD:
  - Given une stratégie candidate `COMPILABLE` contient des règles déterministes, des paramètres résolus et un plan de validation.
  - When la compilation est demandée.
  - Then SD produit une représentation intermédiaire hashable sans exécuter de backtest.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue tant qu'une stratégie non compilable ou non déterministe peut produire une représentation compilée.
- Tests unitaires à écrire: tests du compilateur pour statut invalide, règle non déterministe sans graine, expression invalide, backend absent, paramètre bloquant, plan de validation absent, hash stable et absence d'appel EX.
- Implémentation attendue: créer le service de compilation, les ports abstraits, un backend déterministe de test, la validation d'expression et la production d'un artefact compilé hashable dans SD.
- Invariants et garde-fous: aucun backtest; aucun import EX dans le domaine SD; aucune correction silencieuse d'expression; aucun backend par défaut.
- Dépendances: T-007; `RuleExpressionValidator`; `StrategyCompilerBackend`; DDD-ADR-009.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m010): couvrir compilation strategie deterministe`
- Commit GREEN: `feat(m010): compiler strategie candidate deterministe`
