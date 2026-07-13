# T-012 - Relier M-012 aux écarts V1, à la traçabilité et aux gates

## Milestone
- Nom: M-012 - Évaluation pilote et calibration.
- Source: M-012, livrable `rapport des écarts V1`, sections 19, 20, 21 et 22 de la spécification v4.1, et convention des tâches de milestone.
- Objectif métier: rendre M-012 auditable, régressable et exploitable par M-013.

## Contexte DDD
- Domaine: évaluation scientifique et calibration des seuils.
- Bounded context: transverse d'évaluation, avec signaux de gouvernance vers M-013.
- Objectif métier: publier les preuves de couverture, les métriques, les décisions, les écarts V1 et l'enrôlement des gates.
- Langage ubiquitaire: rapport d'écarts V1, traçabilité, gate, exigence, métrique, benchmark, décision, écart accepté, écart bloquant, test scientifique.
- Invariants critiques: chaque exigence M-012 possède un test et un artefact; chaque métrique de benchmark est reliée à son corpus et sa décision; chaque écart V1 a un statut explicite; M-013 ne peut pas accepter V1 sans lire les écarts M-012.
- Garde-fous: pas de métrique contenant prompts, preuves complètes, secrets ou données de marché complètes; pas d'exigence sans lien; pas de gate qui ignore M-012; pas de rapport V1 qui efface les tests scientifiques RED.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-011.
- Présence des milestones amont dans master: M-011 présent dans `master`.
- Décisions manquantes: aucune si le rapport d'écarts se limite à publier l'état M-012; ADR requise si M-012 redéfinit un critère d'acceptation V1.
- Risques: livrer les benchmarks sans traçabilité; oublier d'enrôler M-012 dans `uv run --locked gate` et `uv run --locked gate`; produire un rapport d'écarts non actionnable pour M-013.

## Tâches
### T-012 - Relier M-012 aux écarts V1, à la traçabilité et aux gates
- But métier: prouver que M-012 est complet, auditable et prêt pour le durcissement M-013.
- Portée DDD: matrice de traçabilité M-012, rapport `V1GapReport`, validateurs `test` et `lint`, métriques de benchmarks SP, KA, EG, RA, SD et EX, critères CV, décisions de calibration, écarts bloquants, écarts acceptés, absence de données sensibles dans les signaux.
- Scénario BDD:
  - Given M-012 a livré corpus, annotations, benchmarks SP, KA, EG, RA, CV, SD, LLM et EX, seuils et décisions.
  - When les gates transverses sont exécutés.
  - Then chaque exigence M-012 est reliée à un test GREEN ou à un écart scientifique explicite, et M-013 reçoit un rapport V1 exploitable.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue tant que la matrice ne relie pas exigences, tests, scripts, specs, modules et rapports M-012, ou tant que le rapport V1 ne liste pas les écarts documentaires, recherche, gouvernance des preuves, réponses, conversation, LLM, stratégies et backtests, y compris les métriques RA obligatoires, les critères CV obligatoires, les tâches LLM obligatoires et les métriques documentaires de formules, temps, mémoire et stabilité.
- Tests unitaires à écrire: tests de `uv run --locked gate` pour exigence sans test, métrique sans corpus, décision sans benchmark, métrique EG non reliée, métrique RA non reliée, critère CV non relié, métrique SD non reliée, tâche LLM obligatoire non reliée, métrique documentaire normative non reliée, écart V1 sans statut, test scientifique RED absent du rapport, donnée sensible dans métrique, gate `test` sans M-012, gate `lint` sans M-012 et compteur incohérent.
- Implémentation attendue: créer `uv run --locked gate`, enrichir `docs/traceability/matrix.md`, publier `docs/governance/m012_v1_gap_report.md` avec les écarts SP, KA, EG, RA, CV, SD, LLM et EX, relier les métriques RA obligatoires, les critères CV de conversation, suivi, routage de mode et absence d'usage factuel de l'historique brut, les tâches LLM obligatoires et les métriques documentaires normatives aux tests et décisions, enrôler tous les tests M-012 dans `uv run --locked gate`, enrôler les validateurs M-012 dans `uv run --locked gate`, puis documenter le résultat dans le journal M-012.
- Invariants et garde-fous: aucun statut GREEN sans exécution de commande; aucun écart sans statut; aucune métrique sensible; aucune exigence M-012 hors matrice; aucun test scientifique RED masqué par un gate logiciel GREEN.
- Dépendances: T-011; `docs/traceability/matrix.md`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`. M-013 consomme le rapport d'écarts V1 produit par M-012, mais n'est pas une dépendance d'implémentation de T-012.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m012): couvrir ecarts v1 tracabilite gates`
- Commit GREEN: `chore(m012): relier ecarts v1 tracabilite gates`
