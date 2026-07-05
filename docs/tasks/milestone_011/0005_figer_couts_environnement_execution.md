# T-005 - Figer le modèle de coûts et l'environnement d'exécution

## Milestone
- Nom: M-011 - Expérience reproductible.
- Source: M-011, invariants EX de modèle de coûts figé, versions de code, dépendances et environnement enregistrés.
- Objectif métier: empêcher qu'un backtest change de coût, de version de code ou d'environnement sans nouvelle expérience.

## Contexte DDD
- Domaine: expérimentation quantitative reproductible.
- Bounded context: EX, avec plateforme locale comme fournisseur d'empreinte d'environnement.
- Objectif métier: compléter l'expérience planifiée avec un `CostModelSnapshot` et une empreinte d'exécution avant toute planification de run.
- Langage ubiquitaire: modèle de coûts, frais, slippage, latence, devise, environnement d'exécution, version de code, version de dépendances, graine, hash.
- Invariants critiques: le modèle de coûts est complet et figé avant l'exécution; le code, les dépendances et l'environnement sont enregistrés; toute source d'aléa possède une graine explicite lorsque nécessaire.
- Garde-fous: pas de coût par défaut; pas de version de code vide; pas d'environnement implicite; pas de graine inventée après résultat.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-004.
- Présence des milestones amont dans master: M-010 présent dans `master`.
- Décisions manquantes: aucune si l'inspection d'environnement reste un port EX et non une nouvelle architecture.
- Risques: masquer un coût manquant sous zéro; accepter un slippage implicite; produire un résultat non reproductible faute de versions.

## Tâches
### T-005 - Figer le modèle de coûts et l'environnement d'exécution
- But métier: rendre les hypothèses d'exécution explicites avant le backtest.
- Portée DDD: objet-valeur `CostModelSnapshot`, objet-valeur `ExecutionEnvironment`, port `ExecutionEnvironmentInspector`, politique `CostModelCompletenessPolicy`, graine explicite et hash d'entrées gelées.
- Scénario BDD:
  - Given une expérience `PLANNED` possède un `StrategySnapshot` et un snapshot de données.
  - When le modèle de coûts et l'environnement sont figés.
  - Then EX conserve les hypothèses de coût, les versions de code et de dépendances, la graine requise et les hash correspondants avant toute exécution.
- Tests d'acceptation à écrire: `tests/m011/validate_cost_environment_freeze_acceptance.ps1`, qui échoue tant qu'un coût absent devient zéro, qu'une version de code est vide, qu'une dépendance n'est pas enregistrée, qu'une graine requise manque ou que l'environnement est recalculé après démarrage.
- Tests unitaires à écrire: tests de `CostModelSnapshot`, `ExecutionEnvironment`, `CostModelCompletenessPolicy`, `ExecutionEnvironmentInspector` et hash d'entrées pour frais absents, devise absente, slippage absent, code version vide, dépendance vide, graine manquante et mutation après gel.
- Implémentation attendue: créer les objets-valeur de coûts et d'environnement, l'inspecteur strict pour les tests, la politique de complétude et l'attachement au `Experiment` sans valeur par défaut.
- Invariants et garde-fous: aucun coût implicite; aucune chaîne vide; aucun recalcul silencieux; aucun accès au Spark; aucun remplacement automatique d'une dépendance inconnue.
- Dépendances: T-004; `app/platform` pour l'empreinte locale si nécessaire; DDD-ADR-009.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_cost_environment_freeze_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_cost_environment_freeze_unit.ps1`; `python -m compileall app\experimentation`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m011): couvrir gel couts environnement`
- Commit GREEN: `feat(m011): figer couts environnement execution`
