# T-007 - Publier les runbooks de migration de configuration

## Milestone

- Nom: M13-config - Configuration applicative sans environnement.
- Source: ADR-016; runbooks M-013; `deploy/local-compose/README.md`.
- Objectif métier: permettre à l'exploitant local de démarrer, auditer et migrer la V1 sans variables d'environnement.

## Contexte DDD

- Domaine: exploitation locale et documentation utilisateur.
- Bounded context: transverse, `platform`, exploitation.
- Objectif métier: remplacer les procédures `GEMMA_*` et `DATABASE_URL` par un fichier de configuration relisible et vérifiable.
- Langage ubiquitaire: runbook, mapping de migration, fichier exemple, secret hors Git, audit de configuration, preuve d'exploitation.
- Invariants critiques: aucun runbook ne demande une variable d'environnement applicative; les secrets restent hors Git; les commandes de démarrage nomment `--config`.
- Garde-fous: pas de documentation de fallback; pas de secret factice; pas de commande qui publie un service interne.

## Blocages Ou Préconditions

- État GREEN/RED connu: T-005 et T-006 doivent avoir migré les chemins de lancement et les gates.
- Présence des milestones amont dans master: M-000 à M-012 visibles dans `master`.
- Décisions manquantes: aucune.
- Risques: conserver une ancienne procédure opérationnelle qui réintroduit les variables par copier-coller.

## Tâches

### T-007 - Publier les runbooks de migration de configuration

- But métier: fournir une procédure exploitable pour passer de l'ancien démarrage par variables au démarrage par `config/application.yaml`.
- Portée DDD: documentation d'exploitation, README Compose, runbooks Spark, sécurité réseau, certificats et incident LLM.
- Scénario BDD:
  - Given un exploitant local lit les runbooks après M13-config.
  - When il prépare et démarre la pile V1.
  - Then chaque commande utilise `--config`, les anciennes variables sont présentées comme entrées rejetées, et la preuve d'audit cite le fichier chargé.
- Tests d'acceptation à écrire: `uv run --locked gate`, couvrant absence de `GEMMA_*` comme précondition, présence du mapping de migration, commandes `--config`, secrets hors Git et preuve d'audit.
- Tests unitaires à écrire: `uv run --locked gate`, couvrant chaque runbook concerné, README Compose, interdiction de `env_file`, interdiction de secret en clair et cohérence des chemins.
- Implémentation attendue: mettre à jour `docs/runbooks/exploitation_locale.md`, `docs/runbooks/spark_reseau_incidents.md`, `docs/runbooks/certificats_spark.md`, `deploy/local-compose/README.md` et publier `docs/runbooks/configuration_applicative.md` avec migration des anciennes clés vers `config/application.yaml`.
- Invariants et garde-fous: aucun exemple ne lance un processus avec variables applicatives; les anciennes clés sont documentées seulement comme valeurs à refuser ou à migrer; aucun secret n'est versionné.
- Dépendances: T-002; T-005; T-006; ADR-016.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(docs): couvrir runbooks configuration sans environnement`.
- Commit GREEN: `docs(runbooks): publier migration application yaml`.
