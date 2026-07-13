# Spécification M13-FastAPI - API orchestratrice ASGI

## Statut et portée

- Statut: décision de frontière HTTP publiée par ADR-019.
- Domaine: plateforme locale.
- Bounded context de composition: `platform`.
- Frontière publique: `orchestrator-api`.
- Hors portée historique T-002: ajout des dépendances, application exécutable, migration des routes et raccordement des read-models; ces éléments ont depuis été livrés par les tâches aval M13-FastAPI.

FastAPI et Uvicorn sont des adaptateurs techniques. Ils ne possèdent aucun aggregate, aucune règle métier et aucun état durable d'un bounded context.

## Langage ubiquitaire

| Terme | Définition normative |
|---|---|
| Application ASGI | Objet d'entrée HTTP asynchrone de `orchestrator-api`, construit avec FastAPI. |
| Serveur HTTP | Processus Uvicorn servant exclusivement l'application ASGI de `orchestrator-api`. |
| Contrat public | Route, payload, statut et erreur observables par un client autorisé, notamment l'UI. |
| Composition root | Point unique qui construit les dépendances concrètes et les injecte aux adaptateurs HTTP. |
| Adaptateur HTTP autorisé | Module sous `app/platform`, sous `app/<bounded_context>/adapters/http`, ou module nommé dans l'allowlist HTTP explicite de la gate d'architecture. |
| Propriétaire métier | Bounded context qui définit la commande, le handler, les invariants, les erreurs et le read-model délégués par HTTP. |

## Scénario BDD de décision

- Given l'API orchestratrice est aujourd'hui servie par un routeur conditionnel partagé
- When la décision de frontière HTTP est publiée
- Then le framework, le serveur, la composition, les responsabilités interdites et la stratégie de migration sont explicites et vérifiables

## Architecture décidée

1. FastAPI construit l'application ASGI de `orchestrator-api`.
2. Uvicorn sert cette application avec le bind et le port explicites de la configuration applicative.
3. La composition root sous `app/platform` construit les dépendances concrètes.
4. Les contrôleurs HTTP valident et traduisent le transport, puis délèguent aux handlers des bounded contexts propriétaires.
5. Les domaines et couches application restent indépendants de FastAPI, Uvicorn et de leurs objets de requête ou réponse.

### Imports autorisés

- `app/platform/**`: application ASGI, composition root, démarrage Uvicorn et traduction transverse du transport.
- `app/<bounded_context>/adapters/http/**` ou `app/<bounded_context>/adapters/http.py`: adaptateurs HTTP autorisés qui traduisent un contrat public vers un port applicatif propriétaire.
- `app/source_processing/adapters/query_http.py` et `app/source_processing/adapters/original_http.py`: adaptateurs HTTP SP explicitement autorisés pour les read-models documentaires et la restitution contrôlée de l'original.

L'allowlist des modules nommés est exacte. Elle n'autorise ni tout le répertoire `adapters/`, ni un même nom de fichier dans un autre bounded context.

### Responsabilités interdites

- aucune logique métier dans `app/platform` ou dans un contrôleur FastAPI;
- aucun import FastAPI/Uvicorn dans `domain` ou `application`;
- aucun service locator fondé sur `Depends`, l'objet application ou l'état global FastAPI;
- aucun accès direct d'un contrôleur au stockage d'un autre bounded context;
- aucun read-model synthétique construit par le transport;
- aucun fallback silencieux vers le routeur conditionnel partagé après la migration d'un contrat.

Une violation d'import est identifiée par le code stable `HTTP_FRAMEWORK_IMPORT_FORBIDDEN` dans la gate d'architecture.

## Contrat de composition

La composition root reçoit une configuration validée et construit explicitement les repositories, handlers, services applicatifs et adaptateurs requis. Un contrôleur reçoit uniquement les ports nécessaires à son contrat. Il ne recherche jamais une dépendance par son nom, par un conteneur global ou par l'état FastAPI.

Les bounded contexts SP, KA, RA et CV restent propriétaires de leurs commandes, événements, invariants, erreurs et lectures publiques. `orchestrator-api` orchestre le transport; elle ne devient pas un nouveau domaine métier.

## Contrat de migration progressive

La migration est effectuée route par route:

1. caractériser le contrat existant, y compris erreurs et statuts;
2. écrire une preuve de parité observable;
3. raccorder le même cas d'usage propriétaire dans l'application ASGI;
4. basculer le contrat une seule fois;
5. retirer explicitement l'ancien branchement du routeur conditionnel partagé.

Une route non encore migrée reste explicitement sur le runtime actuel. Une route migrée ne dispose d'aucun chemin alternatif. Il n'existe aucune migration big bang des autres services: `llm-gateway`, workers et UI ne deviennent pas des applications FastAPI par effet de cette décision.

## Dépendances et verrouillage

Le runtime exige Python `3.12.8` exactement. FastAPI, Uvicorn, Pydantic, Starlette et setuptools sont déclarés directement avec des versions exactes dans `pyproject.toml` et verrouillés dans `uv.lock`. `uv lock --check` vérifie leur cohérence. Une installation implicite, une version flottante ou une dépendance disponible seulement dans l'environnement local est interdite.

## Erreurs et absence de fallback

| Situation | Comportement requis |
|---|---|
| Import FastAPI/Uvicorn hors zone autorisée | La gate échoue avec `HTTP_FRAMEWORK_IMPORT_FORBIDDEN`. |
| Dépendance de composition absente | Le démarrage ou la construction de l'application échoue explicitement; aucun service factice n'est injecté. |
| Payload public invalide | Le contrôleur retourne l'erreur publique documentée sans appeler le cas d'usage. |
| Erreur métier publiée | Le contrôleur traduit le code public prévu sans réinterpréter la décision métier. |
| Contrat migré indisponible | L'erreur reste visible; aucun fallback silencieux vers l'ancien routeur. |
| Contrat non encore migré | Son maintien sur le runtime actuel est explicite et temporaire jusqu'à sa tâche de migration. |

## Invariants vérifiables

- ADR-018 reste inchangée et gouverne toujours le chemin UI.
- ADR-019 précise le moyen technique sans déplacer la propriété métier.
- FastAPI et Uvicorn restent bornés à `app/platform` et aux adaptateurs HTTP autorisés.
- L'application ASGI et la composition root ne portent aucune logique métier.
- Les dépendances seront déclarées et verrouillées ensemble lors de l'implémentation.
- La migration est progressive, observable et sans fallback.
- L'OpenAPI public décrit sémantiquement le multipart PDF, les DTO de réponse, `application/pdf`, les statuts `201`, `202`, `4xx`, `5xx` et les erreurs publiques typées.
- Les routeurs conversation, benchmark, recherche et indexation reçoivent des services publics injectés par la composition root; ils n'appellent aucune fonction privée de `local_runtime`.
- La lecture du corpus SP est paginée par `DocumentId`, groupée sous `REPEATABLE READ READ ONLY` et bornée à un nombre constant de requêtes SQL.
- La gate statique et la preuve live sont sélectionnées par un mode explicite; une invocation sans mode échoue sans fallback.
- La readiness vérifie distinctement le ledger PostgreSQL et `/health` de `llm-gateway`; l'indisponibilité d'une dépendance est visible sans exposer son URL ni ses secrets.
- ADR-026 impose une construction depuis une archive Git, des images API/worker identifiées par commit et schéma, deux replicas worker et une preuve Compose finale incluant UI et Caddy.

## Admission documentaire locale

- ADR-028 impose un token backend hors Git pour les mutations documentaires, un contrôle same-origin au serveur UI, des transferts streaming bornés et un quota corpus sérialisé dans PostgreSQL.
- `POST /v1/documents` et `POST /v1/documents/{document_id}/diagnose` exigent `Authorization: Bearer <token>` entre l'UI et `orchestrator-api`. Le token provient exclusivement de `security.secrets.local_api_token_path`, contient au moins 32 octets et n'apparaît dans aucun contrat public.
- Une mutation directe sans token répond `401 LOCAL_API_TOKEN_REQUIRED`; une valeur incorrecte répond `403 LOCAL_API_TOKEN_INVALID`. Les lectures, `/health` et `/ready` ne sont pas protégées par ce mécanisme.
- Une mutation navigateur doit prouver `Origin` identique à `Host`; `Sec-Fetch-Site`, s'il est présent, vaut `same-origin`. Le serveur UI refuse avant lecture du corps avec `403 UI_ORIGIN_FORBIDDEN`.
- Le PDF est borné à 50 Mio. UI, API et stockage le transmettent ou le copient par chunks de 64 Kio; aucune couche ne matérialise le PDF complet. Les longueurs de titre, auteurs et édition ainsi que le nombre d'auteurs sont bornés avant appel applicatif.
- Le serveur UI accepte au plus quatre requêtes simultanées, applique des timeouts socket et backend de 30 secondes et répond `503 UI_TRANSFER_CAPACITY_EXHAUSTED` en saturation. Un dépassement de taille répond `413` dans une page française accessible.
- `paths.corpus_quota_bytes` fixe le quota agrégé. La migration `009_corpus_quota.sql` porte le compteur et les réservations; `SELECT ... FOR UPDATE` sérialise l'admission et `507 CORPUS_QUOTA_EXCEEDED` refuse un dépassement.
- Le corpus UI charge exactement une page de cent documents par navigation. La lecture SP utilise une requête SQL légère et ne charge ni manifeste, ni décisions de pages, ni routes.
- Une redirection `303` après enregistrement conserve `document_id` et `duplicate`. Une conversion ou une projection M-004 absente affiche exactement `fonctionnalité non livrée` sans conseil de retry.

## Gates T-002

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_fastapi_specification_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_fastapi_architecture_policy_unit.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_adr_system.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_fastapi_specification.ps1
```

## Traçabilité

- ADR: ADR-018; ADR-019; ADR-020; ADR-021; ADR-023; ADR-024; ADR-025; ADR-026; ADR-028; DDD-ADR-001.
- Tâche: `docs/tasks/milestone_013-fastapi/0002_decider_frontiere_http_publique.md`.
- Tests: `tests/m013_fastapi/validate_fastapi_specification_acceptance.ps1`; `tests/m013_fastapi/validate_fastapi_architecture_policy_unit.ps1`.
- Commit RED: `7a3c3c231`, `test(architecture): couvrir frontiere asgi orchestratrice`.
- Commit GREEN: `docs(architecture): decider fastapi uvicorn ADR-019`.
