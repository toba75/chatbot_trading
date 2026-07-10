# Runbook audit réseau et incidents Spark M-013

## Statut

- Identifiant: `M013-Runbook-SparkNetworkIncidents-1.0`
- Rapports sources: `docs/governance/m013_security_audit.md` et `docs/governance/m013_spark_failure_drill.md`
- Politique réseau: `M013-SecurityAuditReport-1.0`
- Drill incident: `M013-SPARK-FAILURE-DRILL-0001`
- ADR applicables: ADR-007, ADR-008, ADR-009, ADR-014, DDD-ADR-006
- ADR: ADR-014; ce runbook applique la frontière réseau, l'endpoint Docker Spark externe sans clé API et les statuts de panne existants.

## Scénario BDD

- Given le chemin LLM unique est `llm-gateway -> spark-inference`.
- When l'audit réseau ou un incident Spark est vérifié.
- Then aucun service interne n'est publié, le navigateur ne joint pas Spark et chaque panne produit un statut public explicite.

## Audit réseau

- Précondition: exécuter depuis la racine du dépôt avec la configuration locale versionnée.
- Commande vérifiée:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_security.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_network_boundary.ps1
```

- Résultat attendu: seul `llm-gateway -> spark-inference` est autorisé, `GEMMA_AUTH_MODE=none`, `GEMMA_TLS_MODE=disabled`, `GEMMA_MODEL_REVISION` et `GEMMA_RUNTIME_VERSION` sont explicites, PostgreSQL, Qdrant, workers et Spark ne sont pas publiés.
- Erreur explicite: toute exposition interne, tout accès navigateur direct ou tout secret Spark côté interface rend l'audit RED.
- Preuve à conserver: sortie des validateurs, `docs/governance/m013_security_audit.md` et horodatage de l'audit.

## Incidents Spark

- Commande vérifiée:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_spark_failures.ps1
```

- Résultat attendu: les statuts publics suivants restent visibles: `LLM_UNAVAILABLE`, `LLM_FIRST_TOKEN_TIMEOUT`, `LLM_TLS_CERTIFICATE_INVALID`, `LLM_AUTHENTICATION_FAILED`, `LLM_PARTIAL_OUTPUT`, `LLM_CIRCUIT_OPEN`, `LLM_RECOVERED`.
- Erreur explicite: une coupure après premier token publie `LLM_PARTIAL_OUTPUT` et ne publie pas de réponse factuelle; une indisponibilité avant premier token publie `LLM_UNAVAILABLE`.
- Preuve à conserver: sortie du validateur et `docs/governance/m013_spark_failure_drill.md`.

## Garde-fous

- Accès direct Spark depuis navigateur: interdit.
- Publication de service interne: interdite.
- Retry borné avant premier token seulement; retry après premier token interdit.
- Aucun provider alternatif, modèle distant ou service Gemma caché.
- Aucun prompt complet, preuve complète, réponse complète ou secret dans les logs.
- Fallback silencieux: interdit.
