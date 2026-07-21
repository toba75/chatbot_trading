# T-005 - Isoler toutes les ressources mutables

## Milestone

- Nom: M13-environments - Environnements explicites et données étanches.
- Source: contrat T-002 et contrôle d'identité T-004.
- Objectif métier: rendre les données d'un environnement inaccessibles aux deux autres même en présence d'une erreur de raccordement simple.

## Contexte DDD

- Domaine: plateforme de données et exploitation.
- Bounded context: transverse aux contextes qui persistent des sources, projections, réponses, expériences ou preuves.
- Objectif métier: séparer les ressources par frontière d'exécution et non par discipline opérateur.
- Langage ubiquitaire: ressource mutable, base dédiée, volume dédié, racine dédiée, secret dédié, queue/outbox dédiée.
- Invariants critiques: aucune ressource mutable ni credential ne sert à deux profils; la production n'est pas montée dans les piles non productives.
- Garde-fous: un préfixe de table, collection ou fichier n'est pas l'unique barrière; aucun volume générique partagé n'est conservé.

## Blocages Ou Préconditions

- État GREEN/RED connu: T-001 à T-004 GREEN.
- Présence des milestones amont dans master: M-000 à M-012 visibles.
- Décisions manquantes: aucune.
- Risques: isoler PostgreSQL mais oublier Qdrant, corpus, artefacts, logs, caches, rapports ou expériences.

## Tâches

### T-005 - Isoler toutes les ressources mutables

- But métier: garantir qu'une donnée créée sous un profil ne peut être observée ni modifiée depuis un autre.
- Portée DDD: PostgreSQL, Qdrant, corpus PDF, sources canoniques, artefacts documentaires, rapports, logs, caches, expériences, files et outbox.
- Scénario BDD:
  - Given un identifiant unique et un PDF réel sont écrits dans un environnement.
  - When les API et adaptateurs des deux autres environnements recherchent cet identifiant.
  - Then aucune donnée, projection, fichier, job, événement, rapport ou artefact correspondant n'est visible et aucune credential du premier environnement n'est disponible.
- Tests d'acceptation à écrire: matrice d'unicité des URLs, bases, rôles, credentials, volumes, chemins et files; écritures sentinelles croisées; absence des secrets de production dans `development` et `test`.
- Tests unitaires à écrire: validateur exhaustif des clés mutables, collisions de chemins résolus, collisions de noms Compose/volumes et refus des alias ambigus.
- Implémentation attendue: créer trois configurations complètes et trois ensembles de ressources; utiliser bases/rôles/secrets distincts, instances ou volumes Qdrant distincts et racines de fichiers distinctes; inventorier chaque ressource mutable depuis le registre des contextes.
- Invariants et garde-fous: configurations autonomes sans merge; chemins absolus/résolus non chevauchants; aucun credential commun; aucune écriture croisée servant de fallback.
- Dépendances: T-002 et T-004; `app/context_registry.json`; schéma de configuration; adaptateurs de persistance.
- Commandes de validation: tests d'unicité et d'écriture croisée; tests de persistance ciblés; `uv run --locked gate`.
- Commit RED: `test(platform): couvrir etancheite des ressources mutables`.
- Commit GREEN: `feat(platform): isoler les donnees par environnement`.
