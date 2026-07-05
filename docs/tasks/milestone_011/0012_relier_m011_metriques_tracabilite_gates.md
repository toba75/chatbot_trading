# T-012 - Relier M-011 aux métriques, à la traçabilité et aux gates

## Milestone
- Nom: M-011 - Expérience reproductible.
- Source: M-011, sections observabilité, stratégie de tests, définition de terminé et matrice de traçabilité.
- Objectif métier: rendre les expériences reproductibles auditables et régressables dans les gates du dépôt.

## Contexte DDD
- Domaine: expérimentation quantitative reproductible.
- Bounded context: EX, avec signaux de gouvernance transverses.
- Objectif métier: publier les preuves de couverture, reproductibilité, conservation, comparaison et contrats HTTP M-011.
- Langage ubiquitaire: métrique EX, taux d'expériences reproductibles, échec par cause, résultats négatifs conservés, modèle de coûts incomplet, répétitions cohérentes, comparaisons explicites, résultats invalidés, traçabilité, gate.
- Invariants critiques: chaque exigence M-011 possède un test et un artefact; les métriques EX normatives sont publiées; les métriques ne contiennent ni secret ni données de marché complètes; le registre append-only des expériences est tracé; les contrôles minimaux de backtest sont tracés; les résultats négatifs restent consultables.
- Garde-fous: pas de métrique dérivée d'un fallback; pas de trace sans lien vers exigence; pas de log de données de marché complètes, secret ou payload moteur brut; pas de gate qui ignore M-011.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-011.
- Présence des milestones amont dans master: M-010 présent dans `master`.
- Décisions manquantes: aucune si les métriques restent descriptives et ne changent pas l'architecture.
- Risques: livrer le comportement sans preuve de traçabilité; compter un échec masqué comme succès; oublier d'enrôler M-011 dans `scripts/test.ps1` et `scripts/lint.ps1`.

## Tâches
### T-012 - Relier M-011 aux métriques, à la traçabilité et aux gates
- But métier: prouver que M-011 est complet, auditable et régressable.
- Portée DDD: métriques EX normatives, matrice de traçabilité, définition d'achèvement, validateurs `test` et `lint`, rapport de couverture M-011 et absence de données sensibles dans les signaux.
- Scénario BDD:
  - Given M-011 a livré planification, entrées figées, exécution déterministe, résultats immuables, registre append-only, conservation, répétition, comparaison et API.
  - When les gates transverses sont exécutés.
  - Then chaque exigence M-011 est reliée à un test GREEN, les six métriques EX normatives sont publiées et les validateurs globaux restent GREEN.
- Tests d'acceptation à écrire: `tests/m011/validate_m011_traceability_acceptance.ps1`, qui échoue tant que la matrice ne relie pas les exigences M-011 aux tests, scripts, specs et modules EX, tant que le registre append-only, la conservation négative, l'invalidation, la correction par nouvelle expérience liée, la répétition, `CompareExperiments`, les contrôles minimaux de backtest ou les endpoints ne sont pas tracés, ou tant que le rapport de métriques ne publie pas les six métriques normatives.
- Tests unitaires à écrire: tests de `scripts/validate_m011_traceability.ps1` pour exigence sans test, test sans commande, métrique sensible, registre append-only absent, correction sans nouvelle expérience liée, contrôle minimal de backtest absent, `CompareExperiments` absent, taux d'expériences reproductibles absent, taux d'échec par cause absent, proportion d'expériences négatives conservées absente, expériences sans modèle de coûts complet absentes, répétitions cohérentes absentes, résultats invalidés après audit absents et compteur incohérent.
- Implémentation attendue: créer les métriques EX exigées par la spec (`taux d'expériences reproductibles`, `taux d'échec par cause`, `proportion d'expériences négatives conservées`, `expériences sans modèle de coûts complet`, `nombre de répétitions cohérentes`, `proportion de résultats invalidés après audit`), créer `scripts/validate_m011_traceability.ps1`, enrichir `docs/traceability/matrix.md` avec `ExperimentRepository`, registre append-only, `RepeatExperiment`, `CompareExperiments`, `ExperimentComparisonCompleted`, relation de correction vers expérience invalidée, contrôles minimaux de backtest, endpoints et métriques, enrôler tous les tests M-011 dans `scripts/test.ps1`, enrôler le validateur M-011 dans `scripts/lint.ps1`, puis documenter le résultat dans le journal M-011.
- Invariants et garde-fous: aucune métrique contenant données de marché complètes, prompt, secret ou payload moteur brut; aucune métrique normative omise; aucun contrôle minimal de backtest omis sans diagnostic explicite; aucun test M-011 hors gate; aucune exigence sans lien, y compris registre append-only, correction liée et comparaison EX; aucun statut GREEN sans exécution des commandes globales.
- Dépendances: T-011; `docs/traceability/matrix.md`; `scripts/test.ps1`; `scripts/lint.ps1`; `scripts/validate_definition_of_done.ps1`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_m011_traceability_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_m011_traceability_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m011_traceability.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m011): couvrir tracabilite metriques gates`
- Commit GREEN: `chore(m011): relier metriques tracabilite gates`
