# T-005 - Migrer Compose et le déploiement vers le fichier de configuration

## Milestone

- Nom: M13-config - Configuration applicative sans environnement.
- Source: ADR-016; section 13 de la spécification unifiée; `deploy/local-compose/compose.yaml`.
- Objectif métier: démarrer la pile locale depuis un fichier de configuration monté en lecture seule, sans `environment:` applicatif ni `env_file`.

## Contexte DDD

- Domaine: plateforme locale et exploitation.
- Bounded context: `platform.local_compose`, `platform.security`.
- Objectif métier: rendre le démarrage Compose auditable et reproductible depuis `config/application.yaml`.
- Langage ubiquitaire: Compose local, point d'entrée utilisateur, montage read-only, `--config`, service applicatif, secret par chemin, frontière Spark.
- Invariants critiques: les services applicatifs reçoivent `--config`; les valeurs applicatives ne sont pas dans `environment:`; les secrets ne sont pas des variables; Spark reste accessible seulement via `llm-gateway`.
- Garde-fous: ne pas déplacer Gemma dans Compose; ne pas publier de port interne; ne pas accepter `env_file`.

## Blocages Ou Préconditions

- État GREEN/RED connu: T-003 et T-004 doivent définir le chargeur et le gateway par fichier.
- Présence des milestones amont dans master: M-000 à M-012 visibles dans `master`.
- Décisions manquantes: aucune.
- Risques: supprimer les variables Compose sans fournir le chemin `--config` à tous les services concernés.

## Tâches

### T-005 - Migrer Compose et le déploiement vers le fichier de configuration

- But métier: supprimer les entrées de configuration applicative de Compose et des scripts de lancement au profit du fichier unique.
- Portée DDD: `deploy/local-compose/compose.yaml`, `deploy/local-compose/README.md`, validateurs Compose, scripts de déploiement Spark.
- Scénario BDD:
  - Given le fichier `config/application.yaml` est monté en lecture seule dans les services applicatifs.
  - When la pile locale est validée et démarrée.
  - Then chaque processus reçoit `--config`, aucune valeur applicative n'est transmise par `environment:` ou `env_file`, et la frontière Spark reste contrôlée.
- Tests d'acceptation à écrire: `uv run --locked gate`, couvrant absence de `env_file`, absence des anciennes variables applicatives dans Compose, présence de `--config`, montage read-only et refus d'un service qui expose une valeur applicative par environnement.
- Tests unitaires à écrire: `uv run --locked gate`, couvrant parsing Compose, détection des services applicatifs, liste autorisée des variables non applicatives si indispensable au runtime conteneur, et refus des clés historiques.
- Implémentation attendue: adapter `deploy/local-compose/compose.yaml`, `app/platform/local_compose.py`, `uv run --locked gate` et README Compose pour lire et contrôler `config/application.yaml`; maintenir les contrôles de ports, réseaux, secrets et healthchecks.
- Invariants et garde-fous: `environment:` ne transporte aucune configuration applicative; `env_file` est interdit; le fichier de configuration est monté `:ro`; aucun service interne n'est publié.
- Dépendances: T-003; T-004; `deploy/local-compose/compose.yaml`; `app/platform/local_compose.py`; `uv run --locked gate`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(platform): couvrir compose sans environnement applicatif`.
- Commit GREEN: `feat(platform): piloter compose par application yaml`.
