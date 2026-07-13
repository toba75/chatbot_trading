# T-002 - Publier la spécification de configuration applicative

## Milestone

- Nom: M13-config - Configuration applicative sans environnement.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M13-config`; ADR-016; section 13 de la spécification unifiée.
- Objectif métier: transformer la décision ADR-016 en contrat vérifiable avant de modifier les processus applicatifs.

## Contexte DDD

- Domaine: plateforme locale et gouvernance d'exécution.
- Bounded context: `platform.configuration`.
- Objectif métier: donner une forme publique et testable au fichier unique `config/application.yaml`.
- Langage ubiquitaire: configuration applicative, schéma strict, clé obligatoire, valeur placeholder, chemin de secret, configuration hashée, erreur explicite.
- Invariants critiques: toute valeur qui pilote l'application est dans `config/application.yaml`; aucune clé obligatoire n'est absente, vide ou placeholder; les secrets sont référencés par chemin et non copiés en clair.
- Garde-fous: aucune valeur par défaut implicite; aucun fallback environnement; aucun schéma permissif qui accepte des clés inconnues dangereuses.

## Blocages Ou Préconditions

- État GREEN/RED connu: T-001 doit avoir établi la précondition GREEN.
- Présence des milestones amont dans master: M-000 à M-012 visibles dans `master`.
- Décisions manquantes: aucune; ADR-016 gouverne le contrat.
- Risques: produire un schéma trop technique qui ne couvre pas les valeurs métier réellement pilotantes.

## Tâches

### T-002 - Publier la spécification de configuration applicative

- But métier: publier le contrat de configuration qui remplacera `GEMMA_*`, `DATABASE_URL`, `QDRANT_URL`, `LLM_GATEWAY_URL`, les ports, les chemins et les seuils applicatifs.
- Portée DDD: `platform.configuration`, contrats de démarrage, erreurs publiques de configuration, traçabilité de configuration.
- Scénario BDD:
  - Given l'exploitant prépare un fichier `config/application.yaml`.
  - When le contrat de configuration est validé.
  - Then chaque valeur nécessaire au démarrage est présente dans le fichier, le schéma refuse les absences et aucun fallback environnement n'est décrit.
- Tests d'acceptation à écrire: `uv run --locked gate`, couvrant la présence de la spécification, du schéma, des sections obligatoires, des erreurs `CONFIG_*` et de l'interdiction des variables d'environnement.
- Tests unitaires à écrire: `uv run --locked gate`, couvrant section manquante, clé obligatoire absente, placeholder, secret en clair, clé environnement historique non migrée et chemin secret absent.
- Implémentation attendue: créer `docs/specs/m013_config_configuration_applicative.md`, `config/application.schema.json` et un exemple non secret `config/application.example.yaml`; définir les sections minimales `deployment`, `services`, `models.llm`, `paths`, `security`, `quality_gates`, `observability` et `runtime`; documenter le mapping des anciens noms vers les nouvelles clés.
- Invariants et garde-fous: le fichier exemple ne contient aucun secret; les clés `GEMMA_*`, `DATABASE_URL`, `QDRANT_URL`, `LLM_GATEWAY_URL` ne sont pas des entrées acceptées; les valeurs vides ou `TO_BE_FILLED` sont refusées.
- Dépendances: ADR-016; `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`; `docs/specs/plan_implementation_milestones_workstreams.md`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m13-config): couvrir specification configuration applicative`.
- Commit GREEN: `docs(m13-config): publier contrat configuration applicative`.
