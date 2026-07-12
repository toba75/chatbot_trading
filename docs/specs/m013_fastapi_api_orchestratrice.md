# Spécification M13-FastAPI - API orchestratrice ASGI

## Statut et portée

- Statut: décision de frontière HTTP publiée par ADR-019.
- Domaine: plateforme locale.
- Bounded context de composition: `platform`.
- Frontière publique: `orchestrator-api`.
- Hors portée T-002: ajout des dépendances, application exécutable, migration des routes et raccordement des read-models.

FastAPI et Uvicorn sont des adaptateurs techniques. Ils ne possèdent aucun aggregate, aucune règle métier et aucun état durable d'un bounded context.

## Langage ubiquitaire

| Terme | Définition normative |
|---|---|
| Application ASGI | Objet d'entrée HTTP asynchrone de `orchestrator-api`, construit avec FastAPI. |
| Serveur HTTP | Processus Uvicorn servant exclusivement l'application ASGI de `orchestrator-api`. |
| Contrat public | Route, payload, statut et erreur observables par un client autorisé, notamment l'UI. |
| Composition root | Point unique qui construit les dépendances concrètes et les injecte aux adaptateurs HTTP. |
| Adaptateur HTTP autorisé | Module sous `app/platform` ou sous `app/<bounded_context>/adapters/http`. |
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

T-002 ne modifie pas les dépendances. Lors de l'implémentation de l'application ASGI, FastAPI et Uvicorn doivent être déclarés explicitement dans `pyproject.toml` et verrouillés dans `uv.lock`. Une installation implicite, une version flottante ou une dépendance disponible seulement dans l'environnement local est interdite.

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

## Gates T-002

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_fastapi_specification_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_fastapi_architecture_policy_unit.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_adr_system.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_fastapi_specification.ps1
```

## Traçabilité

- ADR: ADR-019; ADR-018 inchangée; DDD-ADR-001.
- Tâche: `docs/tasks/milestone_013-fastapi/0002_decider_frontiere_http_publique.md`.
- Tests: `tests/m013_fastapi/validate_fastapi_specification_acceptance.ps1`; `tests/m013_fastapi/validate_fastapi_architecture_policy_unit.ps1`.
- Commit RED: `7a3c3c231`, `test(architecture): couvrir frontiere asgi orchestratrice`.
- Commit GREEN: `docs(architecture): decider fastapi uvicorn ADR-019`.
