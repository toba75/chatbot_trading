# T-011 - Déployer et auditer l'API orchestratrice

## Milestone

- Nom: M13-FastAPI - API orchestratrice ASGI raccordée.
- Source: ADR-019, M-002, M13-config et gates transverses M-013.
- Objectif métier: rendre la nouvelle frontière HTTP reproductible, observable et bloquante en cas de régression.

## Contexte DDD

- Domaine: exploitation locale et gouvernance.
- Bounded context: `platform`, avec preuves transverses SP, KA et UI.
- Objectif métier: lancer le même runtime en local et sous Compose, puis prouver ses contrats de bout en bout.
- Langage ubiquitaire: serveur Uvicorn, readiness, OpenAPI, trace de requête, gate, rollback.
- Invariants critiques: un seul runtime public `orchestrator-api`; configuration unique; aucun ancien routeur actif en parallèle.
- Garde-fous: pas de port supplémentaire, pas de backend alternatif, pas de documentation OpenAPI exposant des champs internes.

## Blocages Ou Préconditions

- T-003 à T-010 GREEN.
- Le déploiement ne peut basculer qu'après parité des contrats et parcours documentaire GREEN.
- Risque: laisser `local_runtime.py` et Uvicorn servir simultanément des versions divergentes de l'API.

## Tâches

### T-011 - Déployer et auditer l'API orchestratrice

- But métier: basculer les lancements locaux et Compose vers Uvicorn et inscrire les preuves M13-FastAPI dans les gates canoniques.
- Portée DDD: commandes de lancement, Compose, healthchecks, observabilité, OpenAPI, runbook, traçabilité et rollback.
- Scénario BDD:
  - Given l'application ASGI et les contrats documentaires sont GREEN
  - When la stack locale démarre puis exécute le parcours PDF jusqu'aux lectures publiques
  - Then un seul `orchestrator-api` sert les contrats, chaque appel est traçable et toute régression bloque la gate M13-FastAPI
- Tests d'acceptation à écrire: `uv run --locked gate` et `uv run --locked gate`, couvrant démarrage, healthcheck, OpenAPI et parcours HTTP réel.
- Tests unitaires à écrire: `uv run --locked gate` et `uv run --locked gate`.
- Implémentation attendue: ajouter une commande `uv run api`, migrer le service Compose `orchestrator-api`, conserver le port 8080, publier le runbook et le rapport d'audit, enrôler le validateur dans `uv run --locked gate` et `uv run --locked gate`.
- Invariants et garde-fous: UI et `llm-gateway` ne sont pas migrés vers FastAPI par effet de bord; arrêt explicite si la configuration ou une dépendance obligatoire manque; aucun ancien dispatch documentaire conservé.
- Dépendances: T-003 à T-010; M-002; M13-config; ADR-018; ADR-019.
- Commandes de validation:
  - `uv run --locked gate`
  - `uv run --locked gate`
  - `uv run --locked gate`
  - `uv run --locked gate`
  - `uv run --locked gate`
  - `uv run --locked gate`
- Commit RED: `test(platform): couvrir deploiement audit m13 fastapi`.
- Commit GREEN: `feat(platform): deployer api orchestratrice fastapi`.
