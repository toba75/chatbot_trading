# Audit sécurité réseau Spark M-013

## Statut

- Identifiant: `M013-SecurityAuditReport-1.0`
- Politique: `SecurityAuditPolicy`
- Tâche: `docs/tasks/milestone_013/0005_auditer_frontiere_reseau_spark.md`
- ADR applicables: ADR-007, ADR-008, ADR-009
- ADR: non requise; T-005 applique la topologie locale à deux plans, le chemin LLM par gateway et le Spark sans état métier sans remplacer ces décisions et sans rendre mTLS obligatoire.

## Scénario BDD

- Given la topologie V1 cible sépare `docker-local` et `spark-inference`.
- When l'audit réseau M-013 inspecte Compose, configuration gateway et règles Spark.
- Then aucun service interne n'est exposé publiquement, le point d'entrée utilisateur reste lié à `127.0.0.1` par défaut, le navigateur ne peut pas joindre le Spark et seul `llm-gateway` possède l'egress autorisé.

## Sources inspectées

| Source | Rôle audité | Résultat |
|---|---|---|
| `deploy/local-compose/compose.yaml` | Ports publiés, réseaux, secrets et egress Spark | Conforme: le seul port publié est le point d'entrée utilisateur local en `127.0.0.1`. |
| `app/platform/topology_registry.json` | Séparation `docker-local` / `spark-inference` et absence d'état métier sur Spark | Conforme: `spark-inference` ne porte que `gemma-vllm` et le cache régénérable du modèle. |
| `deploy/spark-firewall/network-boundary.json` | Allow-list Spark, TLS, refus navigateur, refus workers et callbacks | Conforme: une seule règle autorise `llm-gateway -> spark-inference`. |
| `scripts/validate_network_boundary.ps1` | Validation M-002 réutilisée comme socle | Conforme: ports, TLS et egress sont contrôlés avant les contrôles M-013. |

## Contrôles de frontière

| Contrôle | Invariant | Preuve |
|---|---|---|
| CTRL-M013-NET-001 | Point d'entrée utilisateur lié à `127.0.0.1` par défaut | `edge-gateway` publie `127.0.0.1:${OST_EDGE_HTTPS_PORT?OST_EDGE_HTTPS_PORT requis}:8443`. |
| CTRL-M013-NET-002 | Aucun binding `0.0.0.0` ou implicite pour la V1 locale | `remote_user_access.enabled` reste `false` et aucun binding distant n'est déclaré. |
| CTRL-M013-NET-003 | Aucun service interne public | PostgreSQL, Qdrant, workers, Granite, embeddings, reranker et backtest utilisent `expose` ou aucun port publié. |
| CTRL-M013-NET-004 | Aucun service Gemma/vLLM caché dans Compose local | `gemma-vllm` est déclaré uniquement sur `spark-inference` dans la topologie, pas dans Compose. |
| CTRL-M013-NET-005 | Seul chemin Spark autorisé | La règle unique est `llm-gateway -> spark-inference` vers `gemma-vllm:8443`. |
| CTRL-M013-NET-006 | Navigateur et interface sans accès Spark direct | `browser -> spark-inference | refusé` et aucun secret vLLM n'est exposé à `ui` ou `edge-gateway`. |
| CTRL-M013-NET-007 | Workers sans egress Spark direct | `worker-research -> spark-inference | refusé`; les autres workers sont également dans `denied_initiators`. |
| CTRL-M013-NET-008 | TLS Spark requis | `GEMMA_BASE_URL` utilise HTTPS, `GEMMA_CA_BUNDLE` référence une autorité de certificat et TLS Spark requis est `true`. |
| CTRL-M013-NET-009 | Authentification Spark par secret monté, sans valeur en clair | `GEMMA_API_KEY_FILE` pointe vers `/run/secrets/...`; clé API par fichier secret uniquement. |
| CTRL-M013-NET-010 | Aucun corpus, base, expérience ou secret métier sur Spark | Le Spark ne conserve aucun corpus, base, expérience ou secret métier sur Spark. |
| CTRL-M013-NET-011 | Aucun callback Spark vers les bases locales | `callbacks_from_spark_allowed` reste `false` et aucune règle retour Spark n'est déclarée. |

## Matrice de flux Spark

| Flux | Verdict | Justification |
|---|---|---|
| `llm-gateway -> spark-inference` | autorisé | Chemin applicatif unique vers vLLM selon ADR-008. |
| `browser -> spark-inference | refusé` | refusé | Le navigateur passe par `edge-gateway` puis les services locaux, jamais par Spark. |
| `ui -> spark-inference` | refusé | `ui` n'a ni réseau `spark-egress` ni secret vLLM. |
| `orchestrator-api -> spark-inference` | refusé | L'application utilise `llm-gateway`, sans endpoint Spark direct. |
| `worker-documents -> spark-inference` | refusé | Traitement documentaire local sans egress Spark. |
| `worker-research -> spark-inference | refusé` | Recherche locale via contrats applicatifs et gateway LLM, sans accès Spark direct. |
| `worker-backtest -> spark-inference` | refusé | Backtests locaux sans dépendance Spark directe. |
| `postgres -> spark-inference` | refusé | Stockage local sans egress Spark. |
| `qdrant -> spark-inference` | refusé | Projection locale sans egress Spark. |
| `spark-inference -> docker-local` | refusé | Aucun callback Spark vers corpus, bases ou registres locaux. |

## Secrets et stockage

- Le rapport ne publie aucune valeur complète de secret, certificat, clé API, chaîne de connexion, prompt, preuve, réponse ou donnée métier.
- Les seuls secrets nécessaires à l'inférence sont référencés par fichiers montés dans `llm-gateway`; ils ne sont pas copiés dans `ui`, `edge-gateway`, workers, PostgreSQL ou Qdrant.
- Le Spark ne reçoit pas de corpus, base, expérience, registre, dataset métier ni secret de stockage local.
- La topologie mono-hôte n'est pas le profil V1; toute variante de développement devrait être documentée et validée séparément avant usage.

## Commandes de preuve

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_m013_network_security_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_m013_network_security_unit.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_security.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_network_boundary.ps1
```
