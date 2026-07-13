# T-003 - Charger la configuration depuis un fichier unique

## Milestone

- Nom: M13-config - Configuration applicative sans environnement.
- Source: ADR-016; `docs/specs/m013_config_configuration_applicative.md`.
- Objectif métier: rendre le démarrage applicatif reproductible depuis un fichier explicite, sans lecture de variables système.

## Contexte DDD

- Domaine: plateforme locale.
- Bounded context: `platform.configuration`.
- Objectif métier: centraliser la validation de configuration avant tout accès réseau, stockage ou inférence.
- Langage ubiquitaire: chargeur de configuration, chemin `--config`, fichier illisible, schéma invalide, clé obligatoire, variable homonyme rejetée, configuration validée.
- Invariants critiques: aucun processus applicatif ne démarre sans `--config`; la validation précède l'usage de toute ressource externe; une variable homonyme déclenche `CONFIG_ENV_INPUT_REJECTED`.
- Garde-fous: pas de valeur par défaut pour le chemin; pas de fallback vers `.env`; pas de lecture de `os.environ` sauf pour détecter et refuser les homonymes.

## Blocages Ou Préconditions

- État GREEN/RED connu: T-002 doit publier le schéma attendu.
- Présence des milestones amont dans master: M-000 à M-012 visibles dans `master`.
- Décisions manquantes: aucune.
- Risques: introduire un chargeur qui lit l'environnement pour compléter le fichier au lieu de le refuser.

## Tâches

### T-003 - Charger la configuration depuis un fichier unique

- But métier: fournir le port technique strict qui transforme `config/application.yaml` en configuration validée utilisable par les processus.
- Portée DDD: `app/platform/configuration`, erreurs de démarrage, validation de schéma, détection d'environnement pollué.
- Scénario BDD:
  - Given un processus applicatif reçoit `--config config/application.yaml`.
  - When le fichier est lisible, conforme et qu'aucune variable homonyme n'est présente.
  - Then le chargeur retourne une configuration validée et aucun accès à l'environnement ne pilote l'application.
- Tests d'acceptation à écrire: `uv run --locked gate`, couvrant chargement nominal, absence de `--config`, fichier absent, fichier illisible, schéma invalide, clé vide, placeholder et variable homonyme rejetée.
- Tests unitaires à écrire: `uv run --locked gate`, couvrant parse YAML, validation de types, rejet des sections inconnues critiques, détection des anciens noms `GEMMA_*`, `DATABASE_URL`, `QDRANT_URL`, `LLM_GATEWAY_URL`, hash stable de configuration et messages `CONFIG_*`.
- Implémentation attendue: implémenter `app/platform/configuration/__init__.py` avec value objects de configuration, `load_application_configuration(config_path, environment_snapshot)`, erreurs nommées, calcul de hash et absence de lecture directe de `os.environ` hors snapshot fourni par le point d'entrée.
- Invariants et garde-fous: le chargeur ne complète jamais une valeur manquante depuis l'environnement; toute clé obligatoire vide échoue; les chemins secrets sont validés comme chemins, pas lus comme contenu secret.
- Dépendances: T-002; ADR-016; `config/application.schema.json`; `app/platform/configuration/__init__.py`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(platform): couvrir chargement configuration fichier unique`.
- Commit GREEN: `feat(platform): charger configuration applicative sans environnement`.
