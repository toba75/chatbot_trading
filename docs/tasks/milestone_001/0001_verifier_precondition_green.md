# T-001 - Vérifier la précondition GREEN de M-001

## Milestone
- Nom: M-001 - Frontières DDD et contrats publiés.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M-001 - Frontières DDD et contrats publiés`, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 2, 4, 13, 14, 15, 20 et 21.
- Objectif métier: stabiliser les frontières et le langage publié seulement après avoir retrouvé une base de validation GREEN.

## Contexte DDD
- Domaine: gouvernance d'implémentation et frontières DDD transverses.
- Bounded context: transverse, avec impact sur SP, KA, EG, RA, CV, SD et EX.
- Objectif métier: empêcher que les contrats M-001 soient créés sur un socle documentaire ou de validation déjà RED.
- Langage ubiquitaire: précondition GREEN, tâche de milestone, validateur de tâches, contrat publié, frontière de contexte, RED, GREEN.
- Invariants critiques: un RED existant n'est pas assimilé à GREEN; la correction d'un validateur ne doit pas assouplir silencieusement la convention; les milestones amont doivent rester visibles dans `master`.
- Garde-fous: exécuter les gates M-000, consigner le RED exact, corriger le contrôle ou la donnée fautive par test RED avant toute tâche de contrat.

## Blocages Ou Préconditions
- État GREEN/RED connu: `uv run --locked gate` et `uv run --locked gate` sont RED au 2026-06-25 car `uv run --locked gate` refuse `docs/tasks/milestone_000/0001_verifier_precondition_green.md` avec `Titre de tâche invalide ou absent`.
- Présence des milestones amont dans master: `git fetch origin --prune` a réussi; `git ls-tree -r --name-only master -- docs/tasks docs/adr docs/specs scripts` montre `docs/tasks/milestone_000`, les scripts M-000, les ADR et les specs.
- Décisions manquantes: aucune décision structurante nouvelle n'est identifiée pour corriger la précondition; ADR-010 cadre déjà les gates uv run --locked gate
- Risques: planifier les contrats M-001 malgré une gate documentaire RED; corriger la convention en tolérant des titres invalides; modifier le sens des tâches M-000 acceptées.

## Tâches
### T-001 - Vérifier la précondition GREEN de M-001
- But métier: restaurer une preuve GREEN fiable avant de publier les frontières DDD et les contrats intercontextes.
- Portée DDD: gouvernance transverse; aucune logique métier SP, KA, EG, RA, CV, SD ou EX n'est ajoutée avant retour GREEN.
- Scénario BDD:
  - Given M-000 est présent dans `master` et les fichiers de tâches utilisent la convention publiée.
  - When les gates M-000 sont exécutées avant M-001.
  - Then tout RED existant est corrigé par test explicite ou bloque les contrats M-001 sans fallback silencieux.
- Tests d'acceptation à écrire: un test qui exécute `uv run --locked gate` sur les tâches M-000 et M-001, reproduit le RED de titre observé, puis exige un message ciblé ou un passage GREEN après correction.
- Tests unitaires à écrire: tests du contrôle de titre de tâche avec fins de ligne CRLF et LF, titre manquant, numéro incohérent et fichier `journal.md` ignoré comme tâche.
- Implémentation attendue: corriger uniquement le validateur ou les fins de ligne fautives nécessaires pour que les titres valides soient acceptés et que les titres invalides restent refusés; ne pas changer le sens des tâches M-000.
- Invariants et garde-fous: aucun assouplissement global du regex de tâche; aucun `try/catch` de confort; aucune normalisation silencieuse qui transforme un titre invalide en titre valide.
- Dépendances: M-000 présent dans `master`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; ADR-010.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m001): reproduire le red de précondition des tâches`.
- Commit GREEN: `fix(m001): restaurer la précondition green des tâches`.
