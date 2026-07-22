# T-012 - Relier environnements, runbooks et gates

> **Requalification du 2026-07-23 — ADR-049.** La gate live courante dépend
> uniquement des deux cycles T-010 du profil `test`. Les profils `development`
> et `production` sont contrôlés sans mutation par la gate statique.

## Milestone

- Nom: M13-environments - Environnements explicites et données étanches.
- Source: définition d'achèvement transverse et preuves T-009 à T-011.
- Objectif métier: empêcher la clôture du sous-milestone sans preuve rejouable des trois environnements et de leur étanchéité.

## Contexte DDD

- Domaine: gouvernance et exploitation V1.
- Bounded context: transverse, évaluation et plateforme.
- Objectif métier: rendre chaque invariant traçable vers tests, code, configuration, runbooks et rapports live.
- Langage ubiquitaire: matrice d'étanchéité, preuve d'environnement, gate live, runbook, écart non accepté.
- Invariants critiques: une gate structurelle ne remplace pas les trois E2E; toute ressource mutable et tout worker ont une preuve; un RED live bloque la clôture.
- Garde-fous: aucun rapport déclaratif sans données d'exécution; aucun secret dans les artefacts; aucune clôture implicite de M-013.

## Blocages Ou Préconditions

- État GREEN/RED connu: T-001 à T-011 GREEN avec rapports live des trois profils.
- Présence des milestones amont dans master: M-000 à M-012 visibles.
- Décisions manquantes: aucune.
- Risques: enrôler seulement des scans statiques ou omettre un worker rarement utilisé.

## Tâches

### T-012 - Relier environnements, runbooks et gates

- But métier: fournir à l'exploitant et à la gouvernance une preuve complète, rejouable et non ambiguë.
- Portée DDD: matrice de traçabilité, gate M13-environments, runbooks de lancement/arrêt/migration/backup/restore, rapport de clôture et journal.
- Scénario BDD:
  - Given les trois parcours réels ont produit leurs rapports et la matrice d'isolation couvre toutes les ressources et tous les workers.
  - When la gate M13-environments et la gate canonique sont exécutées.
  - Then chaque exigence est reliée à une preuve GREEN, toute collision ou preuve live absente rend la gate RED et M-013 n'est pas déclaré clôturé par ce seul sous-milestone.
- Tests d'acceptation à écrire: enrôlement unique des validateurs, complétude des trois rapports, couverture ressources/workers, cohérence ADR-045/spec/code/runbooks et refus d'une preuve manquante.
- Tests unitaires à écrire: parsing des rapports, matrice 3 x 3, détection des collisions, rédaction des secrets, statut de clôture.
- Implémentation attendue: publier les runbooks simples autour des trois commandes UV, documenter les opérations bornées, mettre à jour la traçabilité, enrôler gates statiques et live, compléter `journal.md` avec commits RED/GREEN et preuves.
- Invariants et garde-fous: les gates live utilisent les vraies piles; aucune donnée sensible n'est copiée; aucun écart n'est déclaré accepté implicitement; le sous-milestone ne clôt pas M-013.
- Dépendances: T-001 à T-011; ADR-045; rapports E2E.
- Commandes de validation: gate M13-environments statique; gates live development/test/production; `uv run --locked gate --scope governance`; `uv run --locked gate`; `git diff --check`.
- Commit RED: `test(governance): couvrir tracabilite m13 environments`.
- Commit GREEN: `docs(governance): relier environnements aux preuves`.
