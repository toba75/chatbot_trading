# T-001 - Vérifier la précondition GREEN de M13-environments

## Milestone

- Nom: M13-environments - Environnements explicites et données étanches.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M13-environments`; demande utilisateur du 2026-07-21.
- Objectif métier: établir que la gestion des trois environnements peut être implémentée sur une base saine et que M13-config est réellement disponible.

## Contexte DDD

- Domaine: gouvernance d'implémentation et plateforme d'exécution.
- Bounded context: transverse, `platform.configuration`.
- Objectif métier: éviter qu'un défaut antérieur soit confondu avec une régression d'isolation.
- Langage ubiquitaire: environnement d'exécution, précondition GREEN, profil explicite, donnée étanche, worker lié.
- Invariants critiques: M-000 à M-012 sont visibles dans `master`; M13-config est livré; le sous-milestone ne vaut pas clôture de M-013.
- Garde-fous: aucun RED préexistant n'est masqué; aucune ressource ou processus courant n'est modifié par cette vérification.

## Blocages Ou Préconditions

- État GREEN/RED connu: le scope `governance` est GREEN au 2026-07-21; la baseline applicative complète doit être rejouée avant le premier test RED.
- Présence des milestones amont dans master: M-000 à M-012 sont présents dans `master`; M-013 n'est pas requis pour ce sous-milestone.
- Décisions manquantes: ADR-016 existe mais devra être remplacée pour autoriser trois fichiers nommés sans réintroduire de fallback.
- Risques: commencer l'implémentation alors qu'un test live ou une ressource locale est déjà indisponible.

## Tâches

### T-001 - Vérifier la précondition GREEN de M13-environments

- But métier: produire une preuve initiale qui sépare la dette existante des régressions introduites par M13-environments.
- Portée DDD: gouvernance transverse, chargeur M13-config, API, workers, PostgreSQL, Qdrant et parcours documentaire réel.
- Scénario BDD:
  - Given M13-environments est demandé sur une branche issue de `master`.
  - When les prérequis Git, la gate canonique et les parcours live actuellement disponibles sont contrôlés.
  - Then chaque état GREEN ou RED est consigné sans correction silencieuse et l'implémentation ne commence que sur une baseline explicitement qualifiée.
- Tests d'acceptation à écrire: aucun nouveau test fonctionnel; rejouer les validations existantes pertinentes et consigner les éventuels RED externes.
- Tests unitaires à écrire: aucun; cette tâche utilise les gates canoniques existantes.
- Implémentation attendue: compléter `journal.md` avec références Git, présence M-000 à M-012, résultat de `uv run --locked gate` et état des prérequis live sans démarrer ni arrêter de service hors validation autorisée.
- Invariants et garde-fous: ne pas créer de faux GREEN; ne pas utiliser un mock pour remplacer un service indisponible; ne pas altérer les données des trois futurs environnements.
- Dépendances: `AGENTS.md`; `docs/tasks/README.md`; M13-config; ADR-016.
- Commandes de validation: `git fetch origin --prune`; `git ls-tree -r --name-only master -- docs/tasks/milestone_000 docs/tasks/milestone_001 docs/tasks/milestone_002 docs/tasks/milestone_003 docs/tasks/milestone_004 docs/tasks/milestone_005 docs/tasks/milestone_006 docs/tasks/milestone_007 docs/tasks/milestone_008 docs/tasks/milestone_009 docs/tasks/milestone_010 docs/tasks/milestone_011 docs/tasks/milestone_012`; `uv run --locked gate --scope governance`; `uv run --locked gate`.
- Commit RED: aucun commit RED artificiel; consigner tout RED réel observé.
- Commit GREEN: `docs(m13-environments): publier precondition green`.
