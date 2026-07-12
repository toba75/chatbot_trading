# ADR-019 - API orchestratrice FastAPI et Uvicorn

**Statut :** Acceptée
**Date :** 2026-07-12
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** `docs/tasks/milestone_013-fastapi/0002_decider_frontiere_http_publique.md`; ADR-018; DDD-ADR-001

## Contexte

`orchestrator-api` est la frontière HTTP publique du système local. Son runtime actuel repose sur un routeur conditionnel partagé dans la plateforme. Cette composition rend la parité des contrats difficile à vérifier et ne fournit pas une application ASGI explicite à laquelle raccorder progressivement les commandes et read-models publics.

ADR-018 impose à l'UI de passer exclusivement par `orchestrator-api`, sans déplacer dans le transport la propriété métier des bounded contexts. DDD-ADR-001 impose un monolithe modulaire dont les frontières de modèle et de dépendance restent indépendantes d'un framework HTTP.

La décision doit donc préciser le moyen technique de transport sans transformer FastAPI, Uvicorn ou leur injection de dépendances en modèle applicatif, service locator ou propriétaire des règles métier.

## Scénario BDD

- Given l'API orchestratrice est aujourd'hui servie par un routeur conditionnel partagé.
- When la décision de frontière HTTP est publiée.
- Then le framework, le serveur, la composition, les responsabilités interdites et la stratégie de migration sont explicites et vérifiables.

## Décision

- `orchestrator-api` **DOIT** exposer une application ASGI construite avec FastAPI.
- L'application ASGI **DOIT** être servie localement par Uvicorn.
- FastAPI et Uvicorn **DOIVENT** rester des adaptateurs techniques de la plateforme. Leurs imports sont autorisés sous `app/platform` et dans les adaptateurs HTTP explicites des bounded contexts; ils sont interdits dans les couches domaine et application.
- La composition root de `orchestrator-api` **DOIT** construire explicitement les handlers, repositories, services applicatifs et adaptateurs nécessaires, puis les injecter aux contrôleurs HTTP.
- Le mécanisme d'injection de FastAPI **NE DOIT PAS** devenir un service locator accessible depuis les domaines, les services applicatifs ou les handlers métier.
- Les contrôleurs FastAPI **DOIVENT** traduire le transport, valider le contrat public, déléguer aux cas d'usage propriétaires et traduire leurs résultats ou erreurs publiques. Ils **NE DOIVENT PAS** porter de logique métier, décider un routage documentaire, fabriquer un read-model ou accéder directement à un stockage appartenant à un bounded context.
- ADR-018 reste inchangée: l'UI demeure cliente exclusive de `orchestrator-api`, et ADR-019 précise seulement le moyen technique qui sert cette frontière.
- La migration **DOIT** être une migration progressive, contrat par contrat, avec preuve de parité avant le retrait de chaque route du routeur conditionnel partagé. Il n'y a aucune migration big bang des autres services.
- Une route non migrée **DOIT** rester explicitement servie par son chemin actuel jusqu'à sa tranche de migration. Une route migrée **NE DOIT PAS** basculer silencieusement vers l'ancien routeur en cas d'erreur.
- Les dépendances FastAPI et Uvicorn **DOIVENT** être déclarées dans `pyproject.toml` et verrouillées dans `uv.lock` lors de l'implémentation de l'application ASGI, pas par la présente tâche documentaire.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Conserver durablement le routeur conditionnel partagé | Rejetée | La composition et la responsabilité des routes publiques restent implicites et difficiles à vérifier. |
| Migrer tous les services HTTP en une seule fois | Rejetée | Une migration big bang élargit le risque de régression au-delà de `orchestrator-api`. |
| FastAPI avec un serveur de développement implicite | Rejetée | Le serveur d'exécution et son contrat opérationnel resteraient non décidés. |
| FastAPI pour l'application ASGI, Uvicorn pour le serveur, migration progressive de `orchestrator-api` | Retenue | La frontière publique devient explicite sans déplacer la propriété métier ni imposer le framework aux autres services. |

## Conséquences

### Positives

- La frontière HTTP publique possède une application ASGI et un serveur nommés.
- Les contrats peuvent être migrés et comparés un par un.
- Les bounded contexts conservent leurs commandes, règles, erreurs et read-models.
- Une politique d'import vérifiable empêche le framework de contaminer le domaine et l'application.

### Négatives ou coûts

- Le routeur actuel et l'application FastAPI coexistent temporairement pendant la migration.
- Chaque contrat exige une preuve de parité avant le retrait de son ancien chemin.
- L'exploitation doit déclarer et verrouiller deux dépendances supplémentaires lors de l'implémentation ASGI.

### Risques et contrôles

- Risque: utiliser l'injection FastAPI comme service locator. Contrôle: composition root explicite et interdiction d'import dans les couches domaine/application.
- Risque: déplacer des règles métier dans les contrôleurs. Contrôle: contrôleurs limités à la validation et à la traduction du transport, délégation obligatoire aux cas d'usage propriétaires.
- Risque: conserver deux implémentations concurrentes d'un même contrat. Contrôle: parité vérifiée, bascule unique et suppression explicite de l'ancien chemin pour chaque route migrée.
- Risque: masquer une erreur FastAPI par l'ancien routeur. Contrôle: aucun fallback silencieux après la bascule d'un contrat.

## Impact d'implémentation

- Modules concernés: future composition ASGI sous `app/platform`, adaptateurs HTTP publics et runtime de `orchestrator-api`.
- Configuration concernée: commande Uvicorn, bind et port déjà déclarés pour `orchestrator-api`; dépendances à déclarer dans `pyproject.toml` et `uv.lock` lors de l'implémentation.
- Tests attendus: spécification M13-FastAPI, politique d'import, santé ASGI, parité des contrats existants et erreurs publiques sans fallback.
- Milestones concernées: M13-FastAPI, T-002 à T-004, puis raccordements documentaires T-006 à T-010.

## Liens de traçabilité

- Spécification: `docs/specs/m013_fastapi_api_orchestratrice.md`.
- Plan d'implémentation: `docs/specs/plan_implementation_milestones_workstreams.md`, section M13-FastAPI; `docs/tasks/milestone_013-fastapi/0002_decider_frontiere_http_publique.md`.
- Tests d'acceptation: `tests/m013_fastapi/validate_fastapi_specification_acceptance.ps1`; `tests/m013_fastapi/validate_fastapi_architecture_policy_unit.ps1`.
- Commits: RED `7a3c3c231` (`test(architecture): couvrir frontiere asgi orchestratrice`); GREEN `docs(architecture): decider fastapi uvicorn ADR-019`.

## Notes

Cette ADR ne crée aucune route et n'ajoute aucune dépendance. L'application ASGI, la composition root et le verrouillage FastAPI/Uvicorn sont livrés dans la tranche d'implémentation suivante.
