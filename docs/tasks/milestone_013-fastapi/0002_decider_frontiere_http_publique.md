# T-002 - Décider la frontière HTTP publique

## Milestone

- Nom: M13-FastAPI - API orchestratrice ASGI raccordée.
- Source: plan d'implémentation M13-FastAPI, ADR-018 et runtime HTTP actuel.
- Objectif métier: rendre explicite le choix durable de la technologie qui sert les contrats publics.

## Contexte DDD

- Domaine: plateforme locale.
- Bounded context: `platform`; les bounded contexts métier restent indépendants du framework HTTP.
- Objectif métier: disposer d'une frontière publique structurée sans introduire de logique métier dans le transport.
- Langage ubiquitaire: application ASGI, serveur HTTP, routeur, composition root, contrat public.
- Invariants critiques: FastAPI et Uvicorn restent des adaptateurs de plateforme; SP, KA, RA et CV ne les importent pas.
- Garde-fous: aucune migration big bang des autres services; aucune dépendance implicite ou non verrouillée.

## Blocages Ou Préconditions

- T-001 GREEN.
- ADR-019 est le prochain numéro technique disponible lors de la planification.
- Risque: utiliser l'injection FastAPI comme service locator dans les couches domaine ou application.

## Tâches

### T-002 - Décider la frontière HTTP publique

- But métier: publier la décision `FastAPI + Uvicorn` pour `orchestrator-api` et le contrat de migration sans régression.
- Portée DDD: ADR technique, spécification exécutable et règles d'architecture.
- Scénario BDD:
  - Given l'API orchestratrice est aujourd'hui servie par un routeur conditionnel partagé
  - When la décision de frontière HTTP est publiée
  - Then le framework, le serveur, la composition, les responsabilités interdites et la stratégie de migration sont explicites et vérifiables
- Tests d'acceptation à écrire: `uv run --locked gate`, couvrant décision, scénarios, livrables, erreurs et gates.
- Tests unitaires à écrire: `uv run --locked gate`, refusant tout import FastAPI/Uvicorn hors `app/platform` et adaptateurs HTTP autorisés.
- Implémentation attendue: créer `docs/adr/ADR-019-api-orchestratrice-fastapi-uvicorn.md`, mettre à jour `docs/adr/index.md`, créer `docs/specs/m013_fastapi_api_orchestratrice.md` et son validateur.
- Invariants et garde-fous: ADR-018 reste inchangée; ADR-019 précise le moyen technique sans déplacer la propriété métier; dépendances déclarées dans `pyproject.toml` et verrouillées dans `uv.lock` lors de l'implémentation.
- Dépendances: T-001; ADR-018; DDD-ADR-001; spécifications M-003 à M-005 et UI.
- Commandes de validation:
  - `uv run --locked gate`
  - `uv run --locked gate`
  - `uv run --locked gate`
  - `uv run --locked gate`
- Commit RED: `test(architecture): couvrir frontiere asgi orchestratrice`.
- Commit GREEN: `docs(architecture): decider fastapi uvicorn ADR-019`.
