# T-002 - Publier la spécification de stratégie candidate attribuée

## Milestone
- Nom: M-010 - Stratégie candidate attribuée.
- Source: plan M-010 et spécification v4.1, sections SD, contrats publiés, processus produit, API, persistance logique, observabilité, tests et définition de terminé.
- Objectif métier: publier le contrat exécutable du bounded context SD avant d'implémenter une stratégie candidate.

## Contexte DDD
- Domaine: conception de stratégies candidates attribuées.
- Bounded context: SD, avec RA et EG en amont, CV comme façade produit et EX comme consommateur futur de `StrategySnapshot`.
- Objectif métier: définir comment SD transforme un résultat vérifié, un mandat et des choix explicites en stratégie déterministe, compilable ou bloquée par diagnostic.
- Langage ubiquitaire: stratégie candidate, règle de stratégie, paramètre, origine, mandat, contrainte utilisateur, diagnostic bloquant, compatibilité, compilation, snapshot.
- Invariants critiques: une stratégie n'est pas une promesse de rentabilité; chaque règle possède une origine autorisée; un paramètre à calibrer possède un domaine et un protocole; le snapshot est immuable et hashé.
- Garde-fous: aucun accès direct de SD au stockage interne RA ou EG; aucune génération de règle depuis un texte RA sans traduction explicite; aucun backtest dans M-010; aucune valeur de marché inventée.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-001; la spécification détaillée M-010 n'existe pas encore sous `docs/specs`.
- Présence des milestones amont dans master: M-009 présent dans `master`.
- Décisions manquantes: DDD-ADR-009 couvre déjà le snapshot immuable; ADR nouvelle requise seulement si M-010 change cette décision ou introduit une nouvelle frontière SD durable.
- Risques: spécification trop centrée sur HTTP; confusion entre règle SD et conclusion RA; oubli de l'exclusion explicite du backtest M-011.

## Tâches
### T-002 - Publier la spécification de stratégie candidate attribuée
- But métier: rendre M-010 implémentable par comportements SD vérifiables.
- Portée DDD: mission SD, agrégat `StrategyCandidate`, entités `StrategyRule` et `StrategyParameter`, objets-valeur d'origine, politiques de complétude, compatibilité, calibration, compilation et snapshot, commandes, événements, ports, API publiques, erreurs publiques, métriques et exclusions EX.
- Scénario BDD:
  - Given la mission M-010 est de formaliser une hypothèse de stratégie attribuée et vérifiable.
  - When la spécification de stratégie candidate est publiée.
  - Then chaque comportement M-010 nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.
- Tests d'acceptation à écrire: `tests/m010/validate_m010_specification_acceptance.ps1`, qui échoue tant que `docs/specs/m010_strategie_candidate_attribuee.md` et son validateur n'existent pas.
- Tests unitaires à écrire: tests de `scripts/validate_m010_specification.ps1` pour mission absente, agrégat absent, origines absentes, paramètre à calibrer absent, compatibilité absente, snapshot absent, endpoints absents, erreurs publiques absentes, métriques absentes, exclusion du backtest absente et ADR manquantes.
- Implémentation attendue: créer `docs/specs/m010_strategie_candidate_attribuee.md`, créer `scripts/validate_m010_specification.ps1`, enrôler la validation dans `scripts/test.ps1` et `scripts/lint.ps1`, puis relier les exigences M-010 à `docs/traceability/matrix.md`.
- Invariants et garde-fous: aucune décision structurante implicite; aucune déclaration de rentabilité; aucun contrat mutable vers EX; aucune exposition de stockage interne RA, EG ou SD.
- Dépendances: T-001; DDD-ADR-009; DDD-ADR-010; `docs/tasks/README.md`; `docs/specs/plan_implementation_milestones_workstreams.md`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_m010_specification_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m010_specification.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m010): couvrir la specification strategie candidate`
- Commit GREEN: `docs(m010): publier la specification strategie candidate`
