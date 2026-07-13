# T-010 - Relier M-004 à la traçabilité et aux gates

## Milestone
- Nom: M-004 - Version canonique publiée.
- Source: sortie attendue M-004 du plan v4.1 et sections 19, 20 et 21 de la spécification v4.1.
- Objectif métier: prouver que la version canonique publiée est couverte par tests, ADR, code, spécification, métriques et validations exécutables.

## Contexte DDD
- Domaine: gouvernance de livraison du traitement des sources.
- Bounded context: transverse, avec preuves pour `SP`.
- Objectif métier: rendre M-004 clôturable seulement si conversion, adjudication, QA, publication, résolvabilité et événements aval sont reliés à des preuves vérifiables.
- Langage ubiquitaire: matrice de traçabilité, exigence M-004, gate, test d'acceptation, test unitaire, ADR, journal, métriques de conversion, logs d'audit, définition de terminé.
- Invariants critiques: chaque exigence M-004 a une ligne de matrice; chaque ligne pointe vers une commande exécutable; les ADR canoniques sont citées; les gates `test` et `lint` restent GREEN.
- Garde-fous: ne pas marquer `Couvert` sans test exécuté; ne pas citer une ADR absente; ne pas clore M-004 avec une version non résolvable ou sans événement aval.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 à T-009 doivent être GREEN.
- Présence des milestones amont dans master: M-000 à M-003 sont présents dans `master`.
- Décisions manquantes: à réévaluer après T-009; toute décision structurante nouvelle doit créer une ADR depuis `docs/adr/TEMPLATE.md` et mettre à jour `docs/adr/index.md`.
- Risques: oublier la preuve d'autorité textuelle; clore M-004 sans citations ouvrables; publier des métriques contenant le contenu intégral des documents; laisser M-005 indexer une version non acceptée.

## Tâches
### T-010 - Relier M-004 à la traçabilité et aux gates
- But métier: fournir la preuve finale que SP sait publier une version canonique fiable, immutable et consommable par les contextes aval.
- Portée DDD: matrice `REQ-M004-*`, journal M-004, définition de terminé, ADR applicables, gates uv run --locked gate
- Scénario BDD:
  - Given les comportements M-004 sont implémentés et testés.
  - When les gates de clôture sont exécutées.
  - Then chaque exigence M-004 est reliée à une preuve et la clôture est refusée si un test, une ADR, une commande, un locator ou un signal d'audit manque.
- Tests d'acceptation à écrire: un test `uv run --locked gate` qui échoue tant qu'une exigence M-004 n'a pas de ligne dans `docs/traceability/matrix.md` avec test, commande, code, ADR ou justification et preuve d'audit.
- Tests unitaires à écrire: tests du validateur de matrice pour statuts M-004, preuves de domaine, preuves d'adaptateur, ADR-001 à ADR-004, commandes introuvables, exigences sans code et métriques ou logs absents.
- Implémentation attendue: mettre à jour `docs/traceability/matrix.md`, compléter les validateurs ou l'agrégateur de gates si nécessaire, vérifier les métriques `versions_canoniques_publiees`, `pages_refusees_qa`, `autorites_textuelles_ambigues`, `refus_canoniques` et documenter la clôture dans `docs/tasks/milestone_004/journal.md`.
- Invariants et garde-fous: aucune preuve manquante; aucune commande non exécutable; aucun statut `Couvert` sans artefact; aucun locator non résolvable; aucun log ne contient le contenu intégral d'un document.
- Dépendances: T-001; T-002; T-003; T-004; T-005; T-006; T-007; T-008; T-009; `docs/governance/definition_of_done.md`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m004): couvrir la tracabilite de version canonique`.
- Commit GREEN: `docs(m004): relier m004 aux gates et a la tracabilite`.
