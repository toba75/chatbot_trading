# Runbook monitoring local M-013

## Statut

- Identifiant: `M013-Runbook-LocalMonitoring-1.0`
- Profil monitoring: `M013-LocalMonitoringProfile-1.0`
- Profil ressources: `M013-ResourceProfile-1.0`
- Sources: `docs/governance/m013_local_monitoring.md` et `docs/governance/m013_resource_profile.md`
- ADR applicables: ADR-008, ADR-009, ADR-010
- ADR: non requise; ce runbook documente le profil local T-009 sans export externe.

## Scénario BDD

- Given la V1 traite documents, conversations, recherches, stratégies, expériences, sauvegardes et incidents Spark.
- When l'utilisateur consulte le monitoring local.
- Then santé, erreurs, latence, jobs, outbox, gateway, Spark, sauvegarde, restauration, écarts et sécurité sont visibles sans payload sensible.

## Lecture du monitoring

- Commande vérifiée:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_monitoring.ps1
```

- Résultat attendu: le validateur contrôle `v1_health_status`, `v1_error_total`, `v1_latency_ms`, `spark_inference_availability`, `backup_restore_result`, `v1_gap_status`, `network_security_violation_total` et le profil CPU/GPU/I/O.
- Erreur explicite: métrique critique absente, export externe, endpoint public, payload sensible ou source de benchmark manquante bloque la procédure.
- Preuve à conserver: sortie GREEN du validateur, `docs/governance/m013_local_monitoring.md`, `docs/governance/m013_resource_profile.md` et horodatage local.

## Signaux attendus

| Signal | Usage utilisateur | Preuve |
|---|---|---|
| `v1_health_status` | Voir `GREEN`, `DEGRADED` ou `BLOCKED`. | `docs/governance/m013_local_monitoring.md` |
| `v1_error_total` | Identifier contexte et statut d'erreur sans payload. | `docs/governance/m013_local_monitoring.md` |
| `v1_latency_ms` | Lire p50, p95 et maximum sourcés. | `docs/governance/m013_local_monitoring.md` |
| `spark_inference_availability` | Voir indisponibilité, TLS, auth, circuit breaker et récupération. | `docs/governance/m013_spark_failure_drill.md` |
| `backup_restore_result` | Voir `restore_test_result` avant acceptation. | `docs/governance/m013_backup_restore_drill.md` |
| `v1_gap_status` | Voir les écarts V1 non acceptés. | `docs/governance/m013_v1_gap_decisions.md` |
| `network_security_violation_total` | Voir toute violation réseau bloquante. | `docs/governance/m013_security_audit.md` |

## Garde-fous

- aucun export externe.
- aucun endpoint public.
- Aucun prompt complet, preuve complète, réponse complète, secret ou donnée de marché complète.
- Corrélation obligatoire par `trace_id`, `request_id`, `job_id`, `event_id` ou identifiant de drill.
- Fallback silencieux: interdit.
