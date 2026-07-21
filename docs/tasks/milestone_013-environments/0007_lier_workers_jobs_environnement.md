# T-007 - Lier workers et jobs à l'environnement courant

## Milestone

- Nom: M13-environments - Environnements explicites et données étanches.
- Source: demande utilisateur sur les workers; règles des actions UI asynchrones d'`AGENTS.md`.
- Objectif métier: garantir qu'un worker ne réclame, n'exécute ni ne publie un travail appartenant à un autre environnement.

## Contexte DDD

- Domaine: exécution asynchrone et cohérence éventuelle.
- Bounded context: `platform.jobs`, outbox des contextes producteurs, workers documentaires, projection, recherche et expériences.
- Objectif métier: rendre l'appartenance du travail explicite de la commande publique au résultat public.
- Langage ubiquitaire: job d'environnement, worker lié, outbox, relais, claim, progression publique, erreur terminale.
- Invariants critiques: `environment` et `deployment_id` voyagent avec le job; le worker vérifie stockage et message avant claim/exécution; la progression vient du contrat public persistant.
- Garde-fous: `configuration_hash` seul ne remplace pas l'identité; les logs, compteurs locaux ou noms de conteneur ne servent pas à déduire le profil.

## Blocages Ou Préconditions

- État GREEN/RED connu: T-001 à T-006 GREEN.
- Présence des milestones amont dans master: M-000 à M-012 visibles.
- Décisions manquantes: aucune.
- Risques: isoler la file physiquement mais accepter un message mal étiqueté, ou afficher une progression synthétique après refus.

## Tâches

### T-007 - Lier workers et jobs à l'environnement courant

- But métier: prouver l'identité commune de toute la chaîne asynchrone et refuser les travaux croisés avant effet de bord.
- Portée DDD: contrat job/outbox, relais, file PostgreSQL, worker registry, worker documentaire, projection, recherche/backtest et endpoints de santé/progression.
- Scénario BDD:
  - Given un worker `development` est raccordé à ses stockages et reçoit un message déclaré `test`.
  - When le relais ou le worker évalue le message avant claim ou exécution.
  - Then le travail n'est jamais exécuté, une erreur terminale `WORKER_ENVIRONMENT_MISMATCH` est persistée et l'état public reste cohérent dans l'environnement producteur.
- Tests d'acceptation à écrire: propagation API-outbox-relais-queue-worker-read model; mismatch message/worker; worker branché au mauvais stockage; healthcheck exposant identité et hash; progression publique réelle.
- Tests unitaires à écrire: contrat immuable d'identité, filtre atomique de claim, validation du worker id, transitions terminales, absence de callback métier lors d'un mismatch.
- Implémentation attendue: ajouter l'identité aux messages et persistances nécessaires; nommer les workers avec le profil; vérifier tous les workers déclarés par le registre; publier environnement, `deployment_id` et `configuration_hash` dans leurs états de santé et preuves.
- Invariants et garde-fous: aucun job sans identité; aucun claim avant vérification du stockage; aucun traitement cross-environment même si le nom de queue correspond; aucune progression déduite des logs.
- Dépendances: T-004 à T-006; ADR-024; contrats outbox/jobs; exigences UI asynchrones.
- Commandes de validation: tests jobs/outbox/worker ciblés; tests de progression UI/API; tests live de worker; `uv run --locked gate`.
- Commit RED: `test(platform): couvrir appartenance environnement des jobs`.
- Commit GREEN: `feat(platform): lier workers et jobs au profil courant`.
