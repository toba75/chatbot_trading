# T-003 - Servir la santé de l'API par une application construite explicitement

## Milestone

- Nom: M13-FastAPI - API orchestratrice ASGI raccordée.
- Source: ADR-019 à créer et contrat de santé M-002.
- Objectif métier: démarrer une API orchestratrice dont les dépendances sont construites une seule fois et dont l'état est observable.

## Contexte DDD

- Domaine: plateforme locale.
- Bounded context: `platform`.
- Objectif métier: rendre le processus API prêt ou explicitement non prêt avant d'accepter des commandes.
- Langage ubiquitaire: application factory, lifespan, composition root, santé, readiness.
- Invariants critiques: pas de singleton caché; pas de création de repository à chaque requête; configuration obligatoire.
- Garde-fous: aucun cas d'usage simulé pour obtenir un healthcheck GREEN.

## Blocages Ou Préconditions

- T-002 GREEN et ADR-019 acceptée.
- Risque: confondre processus vivant et dépendances métier prêtes.

## Tâches

### T-003 - Servir la santé de l'API par une application construite explicitement

- But métier: exposer `/health` et `/ready` depuis une application ASGI construite avec la configuration applicative stricte.
- Portée DDD: adaptateur de plateforme, composition et états de disponibilité; aucun changement métier.
- Scénario BDD:
  - Given une configuration applicative valide et les dépendances obligatoires de l'API
  - When Uvicorn démarre l'application orchestratrice
  - Then la santé répond et la readiness distingue explicitement une dépendance non câblée sans fallback
- Tests d'acceptation à écrire: `uv run --locked gate`, utilisant un client ASGI et couvrant santé, readiness et configuration invalide.
- Tests unitaires à écrire: `uv run --locked gate`, couvrant factory, lifespan, construction unique et fermeture des ressources.
- Implémentation attendue: ajouter la dépendance FastAPI/Uvicorn, créer l'application factory et le composition root dans `app/platform`, sans encore migrer les routes métier.
- Invariants et garde-fous: aucune valeur par défaut de configuration; aucune connexion créée à l'import; aucune exception de démarrage transformée en état healthy.
- Dépendances: T-002; configuration M13-config; contrat de santé M-002.
- Commandes de validation:
  - `uv run --locked gate`
  - `uv run --locked gate`
  - `uv run --locked gate`
- Commit RED: `test(platform): couvrir demarrage api orchestratrice asgi`.
- Commit GREEN: `feat(platform): servir sante api orchestratrice asgi`.
