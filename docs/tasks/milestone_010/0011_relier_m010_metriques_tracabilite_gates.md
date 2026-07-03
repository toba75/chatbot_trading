# T-011 - Relier M-010 aux métriques, à la traçabilité et aux gates

## Milestone
- Nom: M-010 - Stratégie candidate attribuée.
- Source: M-010, sections observabilité, stratégie de tests, définition de terminé et matrice de traçabilité.
- Objectif métier: rendre la conception de stratégies candidates auditable et reliée aux exigences M-010.

## Contexte DDD
- Domaine: conception de stratégies candidates attribuées.
- Bounded context: SD, avec signaux de gouvernance transverses.
- Objectif métier: publier les preuves de couverture, diagnostics, refus de compilation, snapshots et contrats HTTP dans les gates du dépôt.
- Langage ubiquitaire: métrique SD, taux de stratégies compilables, raisons principales de rejet, proportion de règles par origine, paramètres sans plan de calibration, conflits de compatibilité par catégorie, nombre de versions par stratégie, traçabilité, gate.
- Invariants critiques: chaque exigence M-010 possède un test et un artefact de code ou de documentation; les métriques SD normatives sont toutes publiées; les métriques ne contiennent ni secret ni payload documentaire complet; les versions négatives restent consultables.
- Garde-fous: pas de métrique dérivée d'un fallback; pas de trace sans lien vers exigence; pas de log de prompt, secret ou texte source complet; pas de gate qui ignore M-010.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-010.
- Présence des milestones amont dans master: M-009 présent dans `master`.
- Décisions manquantes: aucune si les métriques restent descriptives et ne changent pas l'architecture.
- Risques: livrer le comportement sans preuve de traçabilité; compter les refus comme succès; oublier d'enrôler M-010 dans `scripts/test.ps1` et `scripts/lint.ps1`.

## Tâches
### T-011 - Relier M-010 aux métriques, à la traçabilité et aux gates
- But métier: prouver que M-010 est complet, auditable et régressable.
- Portée DDD: métriques SD normatives, matrice de traçabilité, définition d'achèvement, validateurs `test` et `lint`, rapport de couverture M-010 et absence de données sensibles dans les signaux.
- Scénario BDD:
  - Given M-010 a livré création, attribution, validation, compilation, snapshot et API stratégie.
  - When les gates transverses sont exécutés.
  - Then chaque exigence M-010 est reliée à un test GREEN, les six métriques SD normatives sont publiées et les validateurs globaux restent GREEN.
- Tests d'acceptation à écrire: `tests/m010/validate_m010_traceability_acceptance.ps1`, qui échoue tant que la matrice ne relie pas les exigences M-010 aux tests, scripts, specs et modules SD, tant que la concurrence optimiste, l'outbox de snapshot ou la supersession de version ne sont pas traçées, ou tant que le rapport de métriques ne publie pas les six métriques normatives.
- Tests unitaires à écrire: tests de `scripts/validate_m010_traceability.ps1` pour exigence sans test, test sans commande, métrique sensible, taux de stratégies compilables absent, raisons principales de rejet absentes, proportion de règles par origine absente, paramètres sans plan de calibration absents, conflits de compatibilité par catégorie absents, nombre de versions par stratégie absent, couverture de concurrence optimiste absente, couverture outbox `StrategySnapshotCreated` absente, couverture supersession absente et compteur incohérent.
- Implémentation attendue: créer les métriques SD exigées par la spec (`taux de stratégies compilables`, `raisons principales de rejet`, `proportion de règles par origine`, `paramètres sans plan de calibration`, `conflits de compatibilité par catégorie`, `nombre de versions par stratégie`), créer `scripts/validate_m010_traceability.ps1`, enrichir `docs/traceability/matrix.md` avec les exigences de concurrence optimiste, outbox de snapshot et supersession de version, enrôler tous les tests M-010 dans `scripts/test.ps1`, enrôler le validateur M-010 dans `scripts/lint.ps1`, puis documenter le résultat dans le journal M-010.
- Invariants et garde-fous: aucune métrique contenant un texte source complet; aucune métrique normative omise; aucun test M-010 hors gate; aucune exigence sans lien; aucun statut GREEN sans exécution des commandes globales; aucune exigence de concurrence, d'outbox ou de supersession hors matrice de traçabilité.
- Dépendances: T-010; `docs/traceability/matrix.md`; `scripts/test.ps1`; `scripts/lint.ps1`; `scripts/validate_definition_of_done.ps1`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_m010_traceability_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_m010_traceability_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m010_traceability.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m010): couvrir tracabilite metriques gates`
- Commit GREEN: `chore(m010): relier metriques tracabilite gates`
