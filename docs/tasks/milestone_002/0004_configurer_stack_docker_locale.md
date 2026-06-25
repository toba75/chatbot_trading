# T-004 - Configurer la stack Docker locale contrôlée

## Milestone
- Nom: M-002 - Plateforme locale sûre.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, livrable `configuration locale docker-local`, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 13, 18 et 21.
- Objectif métier: fournir une configuration locale qui exécute les services nécessaires sans exposition publique ni présence de Gemma local principal.

## Contexte DDD
- Domaine: composition locale des services techniques.
- Bounded context: `platform`, supportant tous les contextes métier.
- Objectif métier: permettre aux futurs traitements de disposer de PostgreSQL, Qdrant, API, workers et `llm-gateway` sans violer la séparation Docker/Spark.
- Langage ubiquitaire: Compose local, service interne, réseau `core`, réseau `spark-egress`, secret monté, port publié, port exposé, healthcheck.
- Invariants critiques: PostgreSQL, Qdrant, workers et services de modèle locaux utilisent des ports internes; le seul point d'entrée utilisateur est lié à `127.0.0.1`; aucun service Gemma ou vLLM principal n'est dans le Compose local.
- Garde-fous: ne pas publier PostgreSQL ou Qdrant; ne pas injecter de secret en clair; ne pas mettre un endpoint Spark par défaut dans le domaine.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-003 doit être GREEN.
- Présence des milestones amont dans master: M-000 et M-001 sont présents dans `master`.
- Décisions manquantes: aucune si ADR-007 et ADR-008 sont appliquées; une ADR est requise si un provider LLM distant est ajouté.
- Risques: produire un Compose qui démarre mais expose trop; accepter des images non épinglées; mélanger configuration d'environnement et logique de domaine.

## Tâches
### T-004 - Configurer la stack Docker locale contrôlée
- But métier: rendre l'exécution locale reproductible sans ouvrir les stockages ou le Spark à des clients non autorisés.
- Portée DDD: fichiers `deploy/local-compose`, réseaux, secrets, healthchecks, services locaux et validations statiques de placement.
- Scénario BDD:
  - Given l'utilisateur lance la stack `docker-local`.
  - When la configuration Compose est validée.
  - Then les stockages et workers restent internes, `llm-gateway` est présent, et aucun service Gemma ou vLLM principal n'est déclaré localement.
- Tests d'acceptation à écrire: un test statique Compose qui refuse `ports` sur PostgreSQL, Qdrant, Granite, embeddings, reranker et workers, refuse vLLM principal local, exige les secrets Spark et vérifie le réseau `spark-egress` limité au gateway.
- Tests unitaires à écrire: tests du parseur Compose pour `ports` contre `expose`, images non épinglées, service sans healthcheck, secret absent et réseau interdit.
- Implémentation attendue: créer les fichiers Compose et scripts de validation statique nécessaires, avec valeurs injectées explicitement par environnement et secrets hors dépôt.
- Invariants et garde-fous: aucune variable implicite; aucun endpoint `127.0.0.1:8000` supposé; aucun secret versionné; aucun fallback de configuration.
- Dépendances: T-003; ADR-007; ADR-008; ADR-009; `deploy/local-compose`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m002\validate_local_compose_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m002\validate_local_compose_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`.
- Commit RED: `test(m002): couvrir la stack docker locale`.
- Commit GREEN: `feat(m002): configurer la stack docker locale`.
