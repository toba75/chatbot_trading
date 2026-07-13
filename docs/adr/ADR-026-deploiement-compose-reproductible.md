# ADR-026 - Déploiement Compose reproductible depuis un commit complet

**Statut :** Acceptée
**Date :** 2026-07-13
**Décideurs :** Équipe OSTrading
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** Findings de revue 3 M13-FastAPI sur déploiement, configuration et dépendances

## Contexte

La preuve live M13-FastAPI lançait Uvicorn depuis le worktree hôte et un PostgreSQL isolé. Elle ne prouvait donc ni le Dockerfile final, ni Caddy, ni le gateway LLM, ni les replicas du worker. Le contexte Docker pouvait aussi incorporer des fichiers non suivis, tandis que l'identité PostgreSQL pilotée par variables techniques pouvait diverger de l'URL montée dans la configuration applicative.

Les images API et worker doivent être reliées au même commit complet et au même schéma PostgreSQL. Un rollback doit vérifier la compatibilité du ledger avant de remplacer le processus courant. Enfin, M13-config publiait des paramètres d'observabilité sans consommateur runtime réel.

## Décision

- La construction d'exploitation **DOIT** utiliser une archive Git de la révision complète ciblée. Le contexte Docker **NE DOIT PAS** provenir directement d'un worktree contenant des fichiers non suivis.
- Le `.dockerignore` racine **DOIT** exclure Git, environnements Python, données, secrets et temporaires; il **DOIT** autoriser explicitement seulement le code, le manifeste, le verrou et les migrations nécessaires.
- Python **DOIT** être verrouillé au patch `3.12.8`; le backend setuptools et les dépendances FastAPI transitives utilisées comme contrats publics **DOIVENT** être déclarés directement avec une version exacte et présents dans `uv.lock`.
- Compose **DOIT** monter un fichier de configuration versionné adapté au réseau conteneur. L'URL PostgreSQL, l'utilisateur, la base et le chemin du secret **DOIVENT** correspondre exactement. L'URL du gateway **DOIT** utiliser le DNS `llm-gateway`.
- La readiness orchestratrice **DOIT** contrôler le ledger PostgreSQL requis et `/health` du gateway LLM. Une panne **DOIT** produire une dépendance `unavailable` et un code technique sûr; aucun détail réseau ou secret n'est exposé.
- Les images API et worker **DOIVENT** porter la révision Git et la version de schéma dans le tag et les labels. Elles **DOIVENT** exécuter un entrypoint explicite sous l'utilisateur non-root `ostrading`.
- La concurrence ingestion configurée à deux **DOIT** être matérialisée par deux replicas worker; chaque replica conserve l'identité d'instance et le fencing d'ADR-025.
- La gate live **DOIT** exporter `HEAD`, construire puis démarrer PostgreSQL, Qdrant, le gateway LLM, l'API, deux workers, l'UI et Caddy. Elle **DOIT** vérifier images, labels, utilisateur, entrypoints, readiness, OpenAPI, migration 008 et un PDF réel traité par le worker.
- Un rollback **DOIT** lire le ledger courant et vérifier la version de schéma de la cible avant tout remplacement. Il **NE DOIT PAS** démarrer une image dont la révision ou le schéma inspecté diffère de la cible.
- Les paramètres d'observabilité sans consommateur réel (`metrics`, chemin de traces, niveau et rétention applicative) **NE DOIVENT PLUS** être acceptés. Le contrat minimal conserve uniquement l'activation de corrélation de traces et l'interdiction des payloads, effectivement consommées par les runtimes.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Construire depuis le worktree | Rejetée | Les fichiers non suivis et changements locaux rendent le contenu différent du commit annoncé. |
| Tag mutable commun aux workers historiques | Rejetée | Il ne prouve ni la révision, ni le schéma requis. |
| Export Git, cibles finales versionnées et preuve Compose live | Retenue | Le contenu, l'identité des images et le chemin d'exploitation deviennent vérifiables de bout en bout. |
| Conserver des clés d'observabilité réservées | Rejetée | Une clé acceptée mais ignorée crée une fausse promesse d'exploitation. |

## Conséquences

### Positives

- L'image inspectée correspond au commit annoncé.
- Le clone propre possède une configuration Compose cohérente sans valeur applicative implicite.
- La preuve live couvre la stack réellement déployée et le worker concurrent.
- Les paramètres acceptés ont tous un effet observable.

### Négatives ou coûts

- La gate live construit plusieurs cibles et dure davantage.
- Le rollback exige une étape de prévalidation avant `compose up`.
- Une évolution du nombre de workers doit modifier explicitement configuration et topologie ensemble.

### Risques et contrôles

- Risque : volume PostgreSQL historique créé avec une autre identité. Contrôle : refus explicite et procédure de migration opérateur; aucune création silencieuse d'un second rôle.
- Risque : archive temporaire ou stack laissée après échec. Contrôle : nettoyage `finally`, projet Compose unique et suppression des volumes temporaires.
- Risque : cible de rollback plus ancienne que le ledger. Contrôle : comparaison avant build et avant remplacement.

## Impact d'implémentation

- Modules concernés: `app/platform/orchestrator_runtime.py`, configuration applicative et gates M13-FastAPI.
- Configuration concernée: `deploy/local-compose/application.compose.yaml`, `compose.yaml`, `.dockerignore`, versions Python et dépendances.
- Tests attendus: `validate_review3_deployment_acceptance.ps1`; `validate_review3_deployment_live.ps1`; `uv lock --check`; migration 008.
- Milestones concernées: M13-FastAPI, correctifs de revue 3.

## Liens de traçabilité

- Spécification: `docs/specs/m013_fastapi_api_orchestratrice.md`; `docs/specs/m013_config_configuration_applicative.md`.
- Plan d'implémentation: `docs/tasks/milestone_013-fastapi/0011_deployer_auditer_api_orchestratrice.md`.
- Tests d'acceptation: `tests/m013_fastapi/validate_review3_deployment_acceptance.ps1`; `tests/m013_fastapi/validate_review3_deployment_live.ps1`.
- Commits: RED `c64311691`; corrections du harness live encore RED `3df97b3b2`, `6b9a94c48`, `fd72ab75d`, `03d301088` et `d38a2142c`; GREEN fonctionnel `f49ffded1`.

## Notes

ADR-026 complète ADR-021 et ADR-025. Elle précise le chemin de livraison et remplace uniquement la partie du contrat ADR-016 qui autorisait des paramètres d'observabilité sans consommateur; l'obligation de fichier unique et l'interdiction des variables applicatives restent inchangées.
