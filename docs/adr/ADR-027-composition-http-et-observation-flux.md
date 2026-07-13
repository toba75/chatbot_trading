# ADR-027 - Composition HTTP précoce et observation complète des flux

**Statut :** Acceptée
**Date :** 2026-07-13
**Décideurs :** Équipe OSTrading
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** Revue d'architecture et d'observabilité M13-FastAPI, passe 3

## Contexte

ADR-019 impose une application FastAPI/Uvicorn, une composition root explicite et des contrôleurs minces. L'implémentation initiale construisait toutefois la composition et enregistrait les routeurs pendant le lifespan. Le schéma OpenAPI demandé avant le démarrage ne contenait donc pas les contrats publics, et sa forme dépendait du cycle de vie de l'application.

Les contrats historiques de conversation produit et de benchmark LLM étaient aussi implémentés dans `platform`, avec leur transport `urllib`. Cette localisation donnait à la plateforme des règles appartenant respectivement à CV et au contexte transverse EV. À l'inverse, certains cas d'usage SP et KA importaient des DTO concrets de l'outbox plateforme, en contradiction avec les frontières de DDD-ADR-001 et ADR-024.

Enfin, l'observation HTTP déclarait un succès dès la création d'une réponse. Une réponse streaming pouvait donc être comptée comme réussie avant qu'un PDF soit entièrement envoyé, puis échouer sans observation corrélée. Les erreurs internes et le relais outbox ne fournissaient pas toujours les identifiants techniques et compteurs nécessaires, tandis que la readiness ne publiait pas la cause publique d'une dépendance indisponible.

## Décision

- La composition root de `orchestrator-api` **DOIT** être construite par la factory d'application afin d'enregistrer toutes les routes avant le lifespan. Cette construction **NE DOIT PAS** ouvrir de connexion ni exécuter de migration.
- Le lifespan **DOIT** rester l'unique propriétaire de l'ouverture et de la fermeture des dépendances. Une erreur ou un timeout d'ouverture **DOIT** empêcher le démarrage; aucun état dégradé silencieux n'est autorisé.
- Le schéma OpenAPI **DOIT** être complet et identique avant et pendant le lifespan. Les requêtes, réponses nominales et erreurs publiques, dont `503`, **DOIVENT** être décrites par des modèles stricts qui refusent les champs supplémentaires.
- Les réponses produites par les handlers **DOIVENT** être validées contre leur modèle public avant envoi. Une union d'états publics **DOIT** être discriminée par un champ de statut et **NE DOIT PAS** accepter un état partiel incohérent.
- Les règles de conversation produit **DOIVENT** appartenir au handler applicatif CV. Les règles du benchmark de chemin LLM réel **DOIVENT** appartenir au handler applicatif EV. Les contrats publics KA non encore configurés **DOIVENT** être portés par des handlers KA explicites qui répondent `503`.
- CV et EV **DOIVENT** dépendre d'un port d'inférence neutre publié dans `app.contracts`. L'I/O HTTP `urllib` **DOIT** rester dans un adaptateur `app.platform.llm_gateway` injecté par l'unique composition intercontextes.
- Une couche `application` d'un bounded context **NE DOIT PAS** importer `app.platform`. Les protocoles d'outbox et d'inférence partagés **DOIVENT** utiliser des DTO neutres sous `app.contracts`, avec des consommateurs explicitement autorisés par le gate d'architecture.
- La corrélation d'un appel LLM **DOIT** utiliser le `trace_id` validé de la requête HTTP courante. Un champ de payload divergent **NE DOIT PAS** remplacer cette corrélation de transport.
- Une observation HTTP de succès **NE DOIT** être émise qu'après l'achèvement réel de l'envoi ASGI. Une rupture après les en-têtes **DOIT** produire `HTTP_STREAM_INTERRUPTED`, le volume effectivement envoyé, le `trace_id`, un compteur d'échec et aucune observation de succès.
- Les logs d'erreur interne **DOIVENT** conserver les types d'exception et de causes, les positions de stack, le chemin, la méthode, le hash de configuration et le `trace_id`. Ils **NE DOIVENT PAS** journaliser le message de l'exception ni le payload métier.
- Le relais outbox **DOIT** journaliser, pour chaque message traité ou refusé, `message_id`, `trace_id`, durée, compteur relayé et code d'erreur public sûr. Il **NE DOIT PAS** journaliser le payload métier.
- Une dépendance de readiness indisponible **DOIT** exposer un `error_code` public stable; une dépendance prête **NE DOIT PAS** porter de cause d'échec.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Construire les routeurs pendant le lifespan | Rejetée | Le contrat OpenAPI varie selon l'état du runtime et n'est pas générable avant démarrage. |
| Construire la composition et ouvrir les connexions dans la factory | Rejetée | Les imports ou la génération OpenAPI déclencheraient des effets externes hors lifespan. |
| Enregistrer les routes dans la factory et ouvrir les dépendances dans le lifespan | Retenue | Le contrat est stable avant démarrage, tandis que les effets externes restent gouvernés par ASGI. |
| Conserver les cas d'usage conversation et benchmark dans platform | Rejetée | La plateforme deviendrait propriétaire de règles CV/EV et du transport dans le même module. |
| Port neutre injecté et handlers dans leurs contextes propriétaires | Retenue | Les cas d'usage restent indépendants du transport et la composition demeure explicite. |
| Compter un streaming comme succès à la création de la réponse | Rejetée | Une rupture en cours d'envoi serait mesurée comme un succès et pourrait rester invisible. |
| Observer l'envoi ASGI jusqu'à son achèvement | Retenue | Le statut opérationnel et le volume correspondent au transfert réellement terminé. |

## Conséquences

### Positives

- OpenAPI est complet, stable et générable sans démarrer PostgreSQL ni le LLM gateway.
- CV, EV, KA, SP et la plateforme retrouvent des dépendances conformes à leurs responsabilités.
- Le `trace_id` HTTP corrèle réellement l'orchestrateur et le LLM gateway.
- Les réponses publiques et leurs états discriminés sont validés avant envoi.
- Un PDF partiellement envoyé, une erreur interne et un conflit de relais deviennent observables sans fuite de contenu.
- La readiness nomme la dépendance et la cause publique qui empêchent le service d'être prêt.

### Négatives ou coûts

- La factory construit les repositories, handlers et routeurs plus tôt, même si le lifespan n'est jamais ouvert.
- Les contrats de compatibilité historiques conservent uniquement des shims minces jusqu'au retrait de leurs anciens imports.
- L'observation streaming ajoute un middleware ASGI et suit le volume de chaque réponse jusqu'à la fin de l'envoi.
- Les modèles publics stricts doivent évoluer explicitement lorsque le contrat HTTP change.

### Risques et contrôles

- Risque : ouvrir une connexion pendant la construction précoce. Contrôle : tests qui prouvent `open_count == 0` avant le lifespan et construction d'adaptateurs sans I/O dans leurs constructeurs.
- Risque : cycle d'import entre la composition et les handlers. Contrôle : port neutre, module de composition unique et gate d'architecture sur les imports intercontextes.
- Risque : faux succès si une exception streaming traverse plusieurs couches Starlette. Contrôle : observation pure ASGI autour de l'application complète et test de rupture après un premier chunk.
- Risque : fuite d'un message d'exception ou d'un payload outbox. Contrôle : allowlist de champs structurés et codes d'erreur validés; tests avec secrets sentinelles.
- Risque : rupture de compatibilité des réponses existantes. Contrôle : validation des sorties avec conservation des champs `null` explicitement fournis et gate de parité historique.

## Impact d'implémentation

- Modules concernés : `app/contracts/llm_inference.py`, `app/contracts/outbox.py`, `app/conversation/application/public_chat.py`, `app/evaluation/application/llm_real_path.py`, `app/knowledge_access/application/public_commands.py`, `app/platform/orchestrator_runtime.py`, `app/platform/orchestrator_asgi.py`, `app/platform/orchestrator_api_models.py`, `app/platform/orchestrator_contract_routers.py`, `app/platform/llm_gateway/`, `app/platform/job_runtime/relay.py`, `scripts/validate_architecture_boundaries.py`.
- Configuration concernée : aucune nouvelle valeur; URL et timeout du LLM gateway restent obligatoires dans la configuration applicative validée.
- Tests attendus : OpenAPI avant/après lifespan, parité des quatre contrats, propagation du trace HTTP, validation des réponses, états documentaires invalides, 404 historique, readiness causée, rupture streaming, logs internes sanitizés, relais outbox corrélé et refus application vers platform.
- Milestones concernées : M13-FastAPI.

## Liens de traçabilité

- Spécifications : `docs/specs/m013_fastapi_api_orchestratrice.md`; ADR-019; ADR-020; ADR-024; DDD-ADR-001; DDD-ADR-011.
- Plan d'implémentation : `docs/tasks/milestone_013-fastapi/0003_servir_sante_api_application_construite.md`; `docs/tasks/milestone_013-fastapi/0004_preserver_contrats_api_existants.md`; correctifs de revue 3.
- Tests d'acceptation : `tests/m013_fastapi/validate_review3_api_architecture_acceptance.ps1`; `tests/m013_fastapi/validate_existing_api_contract_parity_acceptance.ps1`; `tests/m013_fastapi/validate_orchestrator_asgi_health_acceptance.ps1`; `tests/m001/validate_architecture_boundaries_acceptance.ps1`.
- Commits : RED `5d9ccc695`; RED `a17421ae1`; GREEN `b03e34b67`.

## Notes

ADR-027 complète ADR-019 sans la remplacer. ADR-019 choisit FastAPI/Uvicorn et les contrôleurs minces; ADR-027 précise quand composer les routes, où résident les handlers propriétaires et quand une réponse streaming peut être comptée comme terminée.
