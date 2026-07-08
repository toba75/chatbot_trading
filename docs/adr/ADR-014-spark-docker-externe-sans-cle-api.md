# ADR-014 - Endpoint Docker Spark externe sans clé API

**Statut :** Acceptée
**Date :** 2026-07-08
**Décideurs :** Propriétaire du projet
**Remplace :** ADR-007; ADR-008
**Remplacée par :** Aucune
**Source :** Demande utilisateur du 2026-07-08; `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 3, 13, 16, 18, 20 et 21

## Contexte

Gemma est servi dans un conteneur Docker sur la machine Spark. Ce conteneur expose une API compatible OpenAI sur le réseau local contrôlé; il n'expose pas de clé API applicative. Le code M-013 précédent modélisait Spark comme un endpoint `https://spark-inference:8443/v1` avec clé API et autorité de certificat obligatoires. Ce modèle bloque le démarrage local et pousse vers des secrets fictifs, ce qui contredit l'interdiction de fallback et de configuration silencieuse.

La décision doit conserver les invariants déjà acceptés: deux plans physiques, Spark sans état métier, gateway LLM unique, absence d'accès navigateur direct, absence de provider distant de secours et erreurs Spark explicites.

## Décision

La plateforme DOIT modéliser Gemma comme un endpoint Docker externe explicite porté par `spark-inference`.

Le conteneur Gemma NE DOIT PAS être ajouté au Compose local applicatif comme service de secours. `docker-local` garde les services métier, l'interface, les workers, PostgreSQL, Qdrant, les artefacts et les expériences. `spark-inference` garde uniquement le serving Gemma/vLLM, le cache régénérable de modèle et les métriques techniques à rétention courte.

Le seul chemin applicatif autorisé vers Gemma DOIT rester `llm-gateway -> spark-inference`. Les bounded contexts, workers, navigateur, `ui` et `orchestrator-api` NE DOIVENT PAS appeler l'endpoint Gemma directement.

L'URL de l'endpoint DOIT être déclarée explicitement par `GEMMA_BASE_URL`. Le mode d'authentification DOIT être déclaré explicitement par `GEMMA_AUTH_MODE`. Pour le conteneur Spark actuel, `GEMMA_AUTH_MODE` vaut `none`; aucun `GEMMA_API_KEY_FILE`, secret `gemma_api_key` ou header `Authorization` ne doit être exigé ni injecté.

Le mode TLS DOIT être déclaré explicitement par `GEMMA_TLS_MODE`. Pour le conteneur Spark actuel sans terminaison HTTPS locale, `GEMMA_TLS_MODE` vaut `disabled`; aucun `GEMMA_CA_BUNDLE` ni secret `spark_ca` ne doit être exigé. Si une terminaison HTTPS contrôlée est ajoutée plus tard, le mode `ca_bundle` devra être déclaré et le bundle CA devra être fourni explicitement, sans valeur par défaut et sans désactivation silencieuse.

Toute indisponibilité, erreur HTTP, erreur d'authentification, erreur TLS, timeout avant premier token ou interruption de streaming DOIT rester publiée comme panne Spark explicite sans réponse factuelle inventée et sans fallback de modèle.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Garder clé API et CA obligatoires | Rejetée | Ne correspond pas au conteneur Gemma réel et impose des secrets fictifs. |
| Ajouter Gemma au Compose local applicatif | Rejetée | Masque le Spark réel et crée un service de secours local ambigu. |
| Endpoint Docker Spark externe sans clé API, avec modes explicites | Retenue | Reflète l'installation réelle tout en gardant gateway unique, frontière réseau et absence de fallback. |

## Conséquences

### Positives

- Le démarrage local ne dépend plus d'une clé API inexistante.
- La configuration décrit explicitement l'endpoint Docker Spark réel.
- Le gateway LLM reste le point de contrôle unique pour erreurs, métriques, retries et provenance.

### Négatives ou coûts

- L'URL réseau Spark doit être fournie et vérifiée par l'exploitant local.
- Le mode `disabled` reporte la confidentialité réseau sur l'isolation du réseau local contrôlé tant qu'aucune terminaison HTTPS n'est ajoutée.
- Les validateurs Compose, réseau, gateway, runbooks et audit M-013 doivent distinguer mode `none` et mode `ca_bundle` au lieu d'imposer une seule forme.

### Risques et contrôles

- Risque: exposition directe du conteneur Gemma. Contrôle: seul `llm-gateway` possède `GEMMA_BASE_URL`, le navigateur et les workers restent refusés.
- Risque: réintroduction d'un provider distant ou d'un service Gemma caché. Contrôle: validateurs anti-patterns, Compose et frontière réseau.
- Risque: confusion entre absence de clé et fallback. Contrôle: `GEMMA_AUTH_MODE=none` obligatoire et absence de `Authorization` testée.

## Impact d'implémentation

- Modules concernés: `app/platform/local_compose.py`, `app/platform/security/network_boundary.py`, `app/platform/llm_gateway/__init__.py`.
- Configuration concernée: `deploy/local-compose/compose.yaml`, `deploy/spark-firewall/network-boundary.json`, secrets Compose, variables `GEMMA_BASE_URL`, `GEMMA_AUTH_MODE`, `GEMMA_TLS_MODE`.
- Tests attendus: Compose local sans secret Spark fictif, frontière réseau avec modes explicites, gateway OpenAI compatible sans header `Authorization`, absence d'accès direct hors `llm-gateway`.
- Milestones concernées: M-002, M-013.

## Liens de traçabilité

- Spécification: sections 3, 13, 16, 18, 20 et 21.
- Plan d'implémentation: M-002 et M-013.
- Tests d'acceptation: `tests/m002/validate_local_compose_acceptance.ps1`, `tests/m002/validate_network_boundary_acceptance.ps1`, `tests/m002/validate_llm_gateway_contract_acceptance.ps1`, `tests/m013/validate_m013_network_security_acceptance.ps1`.
- Commits: RED et GREEN à renseigner après livraison.

## Notes

Cette ADR remplace les obligations de transport et de secret de ADR-007 et ADR-008. Elle conserve leurs invariants de séparation physique, de gateway unique et de Spark sans état métier.
