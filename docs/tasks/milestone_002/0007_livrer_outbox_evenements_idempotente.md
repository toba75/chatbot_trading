# T-007 - Livrer l'outbox d'événements idempotente

## Milestone
- Nom: M-002 - Plateforme locale sûre.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, livrable `outbox transactionnelle et consommateurs idempotents`, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 14, 15, 20 et 21.
- Objectif métier: permettre la cohérence éventuelle entre contextes sans transaction forte intercontexte.

## Contexte DDD
- Domaine: livraison d'événements intercontextes.
- Bounded context: `platform.event_bus`, consommant le contrat `EventEnvelope` publié par M-001.
- Objectif métier: publier les faits métier passés dans une outbox atomique avec l'état producteur et les livrer à des consommateurs idempotents.
- Langage ubiquitaire: outbox transactionnelle, événement de domaine, consommateur idempotent, `event_id` traité, `aggregate_version`, livraison au moins une fois, doublon.
- Invariants critiques: un événement est écrit dans la même transaction que l'état producteur; un consommateur enregistre les `event_id` traités; une duplication n'altère pas l'état; la livraison exactement une fois n'est jamais supposée.
- Garde-fous: ne pas implémenter d'event sourcing généralisé; ne pas partager les tables des contextes; ne pas traiter un job comme événement.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-002 et T-003 doivent être GREEN; le contrat `EventEnvelope` M-001 est livré.
- Présence des milestones amont dans master: M-000 et M-001 sont présents dans `master`.
- Décisions manquantes: aucune si DDD-ADR-006 et DDD-ADR-008 sont appliquées sans changer leur sens.
- Risques: persister l'outbox hors transaction; créer un bus global qui contourne les contextes; oublier l'ordre conditionnel par `aggregate_version`.

## Tâches
### T-007 - Livrer l'outbox d'événements idempotente
- But métier: synchroniser les contextes par faits publiés sans couplage fort ni double transition.
- Portée DDD: dépôt outbox, statut de livraison, registre des événements traités, contrat avec `EventEnvelope` et doubles de consommation.
- Scénario BDD:
  - Given un contexte publie un événement intercontexte dans la même transaction que son état.
  - When le même événement est livré deux fois au consommateur.
  - Then le consommateur applique la décision une seule fois et enregistre le doublon sans erreur métier silencieuse.
- Tests d'acceptation à écrire: un test de processus qui écrit un événement outbox, le livre deux fois à un consommateur double et vérifie une seule transition observée.
- Tests unitaires à écrire: tests du stockage d'outbox, statut `pending/delivered/failed`, registre `event_id`, ordre par `aggregate_version` et refus d'un événement invalide.
- Implémentation attendue: créer les abstractions d'outbox et de consommation idempotente avec stockage local explicite ou double contrôlé, sans bus distribué externe.
- Invariants et garde-fous: aucun partage direct de stockage métier; aucune livraison exactement une fois supposée; aucun événement sans producteur; aucun fallback de version d'événement.
- Dépendances: T-002; contrat M-001 `EventEnvelope`; DDD-ADR-006; DDD-ADR-008; tests d'architecture M-001.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m002): couvrir outbox et idempotence`.
- Commit GREEN: `feat(m002): livrer outbox idempotente`.
