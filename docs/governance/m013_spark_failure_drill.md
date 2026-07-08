# Exercice pannes Spark M-013

## Statut

- Identifiant: `M013-SPARK-FAILURE-DRILL-0001`
- Politique: `M013-SparkFailureDrill-1.0` / `SparkFailurePolicy`
- Tâche: `docs/tasks/milestone_013/0006_eprouver_pannes_spark_sans_fallback.md`
- ADR applicables: ADR-008, ADR-009, DDD-ADR-006
- ADR: non requise; T-006 applique le chemin `llm-gateway -> spark-inference`, le Spark sans état métier et l'outbox transactionnelle sans introduire de nouveau mode de dégradation fonctionnelle.

## Scénario BDD

- Given une commande V1 requiert Gemma via `llm-gateway`.
- When le Spark est indisponible, lent ou coupe la génération.
- Then `LLM_UNAVAILABLE` ou un diagnostic explicite est publié sans réponse factuelle, fallback, snapshot, benchmark promu ni double outbox.

## Résultat du drill

- Verdict: GREEN pour le comportement logiciel T-006.
- Statut public minimal: `LLM_UNAVAILABLE`.
- Diagnostics explicites couverts: `LLM_FIRST_TOKEN_TIMEOUT`, `LLM_TLS_CERTIFICATE_INVALID`, `LLM_AUTHENTICATION_FAILED`, `LLM_PARTIAL_OUTPUT`, `LLM_CIRCUIT_OPEN`, `LLM_RECOVERED`.
- Circuit breaker: circuit breaker ouvrable et refermable, avec ouverture visible après pannes transitoires et fermeture visible après récupération.
- Disponibilité locale: fonctions locales hors Gemma disponibles pendant la panne Spark.
- Publication: aucune réponse factuelle publiée sans génération complète.
- SD: aucune stratégie snapshotée après panne Spark.
- EV/LLM: aucun benchmark LLM promu sur chemin dégradé.
- Routage: aucun provider alternatif, aucun modèle distant et aucun service Gemma caché dans Compose local ne sont appelés.
- Retry: retry borné avant premier token; retry après premier token interdit.
- Observabilité: aucun prompt complet, aucune preuve complète, aucune réponse complète et aucun secret ne sont exposés dans logs ou métriques.
- Outbox: aucun double outbox; les événements techniques restent idempotents par identifiant.

## Cas de panne

| Cas | Contexte consommateur | Déclencheur | Statut public | Retry | Circuit breaker | État métier |
|---|---|---|---|---|---|---|
| SPARK-FAIL-UNAVAILABLE-RA | RA | Spark indisponible avant premier token | `LLM_UNAVAILABLE` | 1 retry borné avant premier token avec idempotency key | ouverture visible | aucune réponse factuelle publiée |
| SPARK-FAIL-TIMEOUT-CV | CV | Timeout avant premier token | `LLM_FIRST_TOKEN_TIMEOUT` | 1 retry borné avant premier token avec idempotency key | compteur de panne visible | conversation non masquée |
| SPARK-FAIL-TLS-SD | SD | Certificat TLS refusé | `LLM_TLS_CERTIFICATE_INVALID` | aucun retry | cause explicite | aucune stratégie snapshotée |
| SPARK-FAIL-AUTH-EV | EV | Clé API Spark refusée | `LLM_AUTHENTICATION_FAILED` | aucun retry | cause explicite | aucun benchmark LLM promu |
| SPARK-FAIL-CUT-BEFORE-RA | RA | Coupure de flux avant premier token | `LLM_UNAVAILABLE` | 1 retry borné avant premier token avec idempotency key | compteur de panne visible | aucune réponse factuelle publiée |
| SPARK-FAIL-CUT-AFTER-CV | CV | Coupure de flux après premier token | `LLM_PARTIAL_OUTPUT` | aucun retry après premier token | sortie partielle non publiable | conversation non publiée comme fait |
| SPARK-FAIL-CIRCUIT-OPEN | SD | Seuil de panne atteint | `LLM_CIRCUIT_OPEN` | aucun appel Spark immédiat | ouverture visible | aucune stratégie snapshotée |
| SPARK-FAIL-CIRCUIT-CLOSED | EV | Récupération Spark validée | `LLM_RECOVERED` | reprise contrôlée | fermeture visible | aucun benchmark promu rétroactivement |

## Fonctions locales hors Gemma

| Fonction locale | Disponibilité pendant panne Spark | Preuve attendue |
|---|---|---|
| `ingestion_locale` | disponible | SP peut enregistrer et diagnostiquer sans appeler Gemma. |
| `restauration_locale` | disponible | Les drills de sauvegarde et restauration restent exécutables. |
| `consultation_locale` | disponible | Les sources, citations, écarts et audits existants restent consultables. |
| `audit_local` | disponible | Les validateurs locaux et journaux de gouvernance restent lisibles. |

## Contrôles T-006

| Contrôle | Invariant | Preuve |
|---|---|---|
| CTRL-M013-SPARK-001 | `LLM_UNAVAILABLE` ou diagnostic explicite pour chaque panne Spark | Tous les cas portent un statut public non ambigu. |
| CTRL-M013-SPARK-002 | aucune réponse factuelle publiée sans génération complète | RA et CV restent bloqués sur statut d'indisponibilité ou sortie partielle non publiable. |
| CTRL-M013-SPARK-003 | aucune stratégie snapshotée après panne | SD refuse les snapshots quand Gemma est indisponible. |
| CTRL-M013-SPARK-004 | aucun benchmark LLM promu sur chemin dégradé | EV conserve le statut bloquant LLM M-012 et refuse la promotion. |
| CTRL-M013-SPARK-005 | aucun provider alternatif | Le chemin reste `llm-gateway -> spark-inference`; aucun modèle distant ou local caché n'est appelé. |
| CTRL-M013-SPARK-006 | retry borné avant premier token | Les retries conservent l'idempotency key et restent limités à 1. |
| CTRL-M013-SPARK-007 | retry après premier token interdit | `LLM_PARTIAL_OUTPUT` bloque toute reprise non idempotente. |
| CTRL-M013-SPARK-008 | circuit breaker ouvrable et refermable | `LLM_CIRCUIT_OPEN` et `LLM_RECOVERED` sont observables. |
| CTRL-M013-SPARK-009 | fonctions locales hors Gemma disponibles | ingestion, restauration, consultation et audit local restent disponibles. |
| CTRL-M013-SPARK-010 | aucun prompt complet dans logs ou métriques | Les signaux exposent seulement statut, hash, tailles, latence, retry et circuit breaker. |
| CTRL-M013-SPARK-011 | aucun double outbox | Les identifiants d'événements techniques restent uniques. |

## Commandes de preuve

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_spark_failure_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_spark_failure_unit.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_spark_failures.ps1
```
