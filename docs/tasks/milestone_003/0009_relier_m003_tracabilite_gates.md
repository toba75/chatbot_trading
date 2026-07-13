# T-009 - Relier M-003 à la traçabilité et aux gates

## Milestone
- Nom: M-003 - Source enregistrée, diagnostiquée et routée.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, sortie attendue M-003, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 20 et 21.
- Objectif métier: prouver que le traitement des sources M-003 est couvert par tests, ADR, code, spécification et validations exécutables.

## Contexte DDD
- Domaine: gouvernance de livraison du traitement des sources.
- Bounded context: transverse, avec preuves pour `SP`.
- Objectif métier: rendre M-003 clôturable seulement si l'enregistrement, le manifeste, le diagnostic, le routage, les blocages, les commandes SP et les signaux d'audit sont reliés à des preuves.
- Langage ubiquitaire: matrice de traçabilité, exigence M-003, gate, test d'acceptation, test unitaire, ADR, journal, définition de terminé, métriques d'ingestion, logs d'audit.
- Invariants critiques: chaque exigence M-003 a une ligne de matrice; chaque ligne pointe vers une commande exécutable; les ADR de routage et OCR sont citées; les métriques ou logs d'audit M-003 sont validés; les gates `test` et `lint` restent GREEN.
- Garde-fous: ne pas marquer `Couvert` sans test exécuté; ne pas citer une ADR absente; ne pas clore M-003 avec une source publiable mais non routée.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 à T-008 doivent être GREEN.
- Présence des milestones amont dans master: M-000, M-001 et M-002 sont présents dans `master`.
- Décisions manquantes: à réévaluer après T-008; toute décision structurante nouvelle doit créer une ADR depuis `docs/adr/TEMPLATE.md` et mettre à jour `docs/adr/index.md`.
- Risques: oublier une exigence de page manifest; référencer un test qui n'exécute pas la gate; fermer M-003 sans preuve d'absence de fallback de route; produire des logs contenant le contenu intégral des documents.

## Tâches
### T-009 - Relier M-003 à la traçabilité et aux gates
- But métier: fournir la preuve finale que SP sait enregistrer, diagnostiquer et router une source sans omission ni fallback silencieux.
- Portée DDD: matrice `REQ-M003-*`, journal M-003, définition de terminé, ADR applicables, gates uv run --locked gate
- Scénario BDD:
  - Given les comportements M-003 sont implémentés et testés.
  - When les gates de clôture sont exécutées.
  - Then chaque exigence M-003 est reliée à une preuve et la clôture est refusée si un test, une ADR, une commande ou un signal d'audit manque.
- Tests d'acceptation à écrire: un test `uv run --locked gate` qui échoue tant qu'une exigence M-003 n'a pas de ligne dans `docs/traceability/matrix.md` avec test, commande, code, ADR ou justification et preuve d'audit.
- Tests unitaires à écrire: tests du validateur de matrice pour statuts M-003, preuves de domaine, preuves d'adaptateur, ADR de routage, commandes introuvables, exigences sans code et métriques ou logs absents.
- Implémentation attendue: mettre à jour `docs/traceability/matrix.md`, compléter les validateurs ou l'agrégateur de gates si nécessaire, vérifier les métriques `documents_par_route`, `taux_quarantaine` et `erreurs_par_modele`, puis documenter la clôture dans `docs/tasks/milestone_003/journal.md`.
- Invariants et garde-fous: aucune preuve manquante; aucune commande non exécutable; aucun statut `Couvert` sans artefact; aucune métrique d'audit absente; aucun log ne contient le contenu intégral d'un document; aucune modification silencieuse d'une ADR acceptée.
- Dépendances: T-001; T-002; T-003; T-004; T-005; T-006; T-007; T-008; `docs/governance/definition_of_done.md`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m003): couvrir la tracabilite des sources`.
- Commit GREEN: `docs(m003): relier m003 aux gates et a la tracabilite`.
