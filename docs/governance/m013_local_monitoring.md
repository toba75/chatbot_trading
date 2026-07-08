# Monitoring local d'exploitation M-013

## Statut

- Identifiant: `M013-LocalMonitoringProfile-1.0`
- Politique: `LocalMonitoringProfile` / `MonitoringSignalPolicy`
- Tâche: `docs/tasks/milestone_013/0009_publier_monitoring_local_exploitation.md`
- ADR applicables: ADR-008, ADR-009, ADR-010.
- ADR: non requise; T-009 publie un profil documentaire et une politique locale sans créer de composant d'observabilité structurant et sans export externe.
- Export externe par défaut: interdit.
- Endpoint public: interdit.
- Rétention courte des logs: 72 heures.
- Corrélation: `trace_id`, `request_id`, `job_id`, `event_id` ou identifiant stable de drill selon le signal.

## Scénario BDD

- Given la V1 traite documents, conversations, recherches, stratégies, expériences et sauvegardes avec Gemma sur Spark et les services techniques sur `docker-local`.
- When le monitoring local et le profil de ressources sont consultés après une exécution, une panne ou un benchmark de capacité.
- Then les signaux indiquent santé, erreurs, latence, jobs, outbox, gateway, Spark, sauvegarde, restauration, écarts, sécurité, capacité et réglages sans exposer de payload sensible ni masquer une non-acceptation V1.

## Invariants

- Le monitoring reste local: aucun export externe, aucune télémétrie fournisseur, aucun endpoint public.
- Aucun prompt complet, preuve complète, réponse complète, secret ou donnée de marché complète n'est publié.
- Chaque signal possède un propriétaire, une famille de métrique, une corrélation et une rétention courte.
- Les pannes Spark, le circuit breaker, les retries avant premier token, les coupures après premier token et les récupérations restent visibles.
- Les résultats de sauvegarde et de restauration, dont `restore_test_result`, restent visibles.
- Les écarts V1 hérités de M-012 restent visibles avec leur statut; aucun écart bloquant ou différé n'est masqué.
- Les alertes locales nomment leur seuil et leur source de benchmark ou de décision.
- Une métrique issue d'un fallback est interdite.

## Signaux critiques V1

| Signal | Contexte | Composant | Famille | Propriétaire | Corrélation | Rétention | Seuil sourcé | Payload sensible |
|---|---|---|---|---|---|---|---|---|
| `v1_health_status` | `platform` | `edge-gateway` | santé | `platform` | `trace_id` | 72 heures | benchmark M-012 et validation M-013 | interdit |
| `v1_error_total` | `SP` | `source-processing` | erreurs | `SP` | `trace_id` | 72 heures | benchmark M-012 et validation M-013 | interdit |
| `v1_latency_ms` | `KA` | `knowledge-access` | latence | `KA` | `trace_id` | 72 heures | benchmark M-012 et validation M-013 | interdit |
| `job_queue_depth` | `platform` | `job-runtime` | jobs | `platform` | `job_id` | 72 heures | benchmark M-012 et validation M-013 | interdit |
| `outbox_pending_total` | `platform` | `outbox` | outbox | `platform` | `event_id` | 72 heures | benchmark M-012 et validation M-013 | interdit |
| `llm_gateway_latency_ms` | `RA` | `llm-gateway` | gateway | `RA` | `trace_id` | 72 heures | `docs/evaluation/m012/llm_real_path_benchmark_report.md` | interdit |
| `spark_inference_availability` | `platform` | `spark-inference` | Spark | `platform` | `trace_id` | 72 heures | `docs/governance/m013_spark_failure_drill.md` | interdit |
| `backup_restore_result` | `platform` | `backup-restore` | sauvegarde restauration | `platform` | `restore_test_result` | 72 heures | `docs/governance/m013_backup_restore_drill.md` | interdit |
| `v1_gap_status` | `EV` | `v1-acceptance-gate` | écarts | `EV` | `gap_id` | 72 heures | `docs/governance/m013_v1_gap_decisions.md` | interdit |
| `network_security_violation_total` | `platform` | `network-boundary` | sécurité réseau | `platform` | `trace_id` | 72 heures | `docs/governance/m013_security_audit.md` | interdit |
| `claim_verification_error_total` | `EG` | `evidence-governance` | erreurs | `EG` | `claim_id` | 72 heures | benchmark M-012 et validation M-013 | interdit |
| `conversation_turn_latency_ms` | `CV` | `conversation` | latence | `CV` | `conversation_id` | 72 heures | benchmark M-012 et validation M-013 | interdit |
| `strategy_snapshot_block_total` | `SD` | `strategy-design` | écarts | `SD` | `strategy_id` | 72 heures | `docs/governance/m013_v1_gap_decisions.md` | interdit |
| `experiment_job_latency_ms` | `EX` | `experimentation` | jobs | `EX` | `experiment_id` | 72 heures | benchmark M-012 et validation M-013 | interdit |

## Santé et erreurs

| Zone | Signal | État attendu | Écart visible |
|---|---|---|---|
| Santé V1 | `v1_health_status` | `GREEN`, `DEGRADED` ou `BLOCKED` explicite | Oui |
| Erreurs métiers et techniques | `v1_error_total` | Compteur local par contexte et statut | Oui |
| Latence produit | `v1_latency_ms` | p50, p95 et maximum sourcés par benchmark | Oui |
| Sécurité réseau | `network_security_violation_total` | zéro attendu, violation bloquante visible | Oui |

## Jobs, outbox et gateway

| Zone | Signal | Invariant |
|---|---|---|
| Jobs locaux | `job_queue_depth` | La file de jobs est visible par contexte sans payload de tâche complet. |
| Outbox | `outbox_pending_total` | Les événements pendants et doublons sont corrélables par `event_id`. |
| Gateway LLM | `llm_gateway_latency_ms` | Latence, TTFT, retry avant premier token et circuit breaker sont visibles sans prompt complet. |
| Sortie interrompue | `llm_gateway_output_interrupted_total` | Une coupure après premier token publie un statut non publiable sans fragment de réponse. |

## Spark, sauvegarde et restauration

| Zone | Signal | Invariant |
|---|---|---|
| Spark | `spark_inference_availability` | Disponibilité, TLS, authentification, circuit breaker ouvert et récupération sont visibles. |
| Sauvegarde | `backup_restore_result` | Le résultat `restore_test_result` est visible avant acceptation. |
| Restauration | `backup_restore_result` | Les erreurs de restauration sont corrélables sans clé, certificat privé ni archive complète. |
| Écarts V1 | `v1_gap_status` | SP, KA, RA, SD et LLM restent visibles tant qu'ils ne sont pas acceptés ou corrigés. |

## Sécurité des signaux

- Aucun payload sensible: les logs et métriques ne contiennent que statuts, tailles, hashes, compteurs, durées, identifiants stables et corrélations.
- Aucun prompt complet.
- Aucune preuve complète.
- Aucune réponse complète.
- Aucun secret.
- Aucune donnée de marché complète.
- Aucun endpoint public.
- Aucun export externe.
- Rétention courte: 72 heures pour les journaux techniques locaux, puis purge technique explicite hors artefacts d'autorité.

## Alertes locales

| Alerte | Signal | Seuil | Source |
|---|---|---|---|
| `M013-ALERT-HEALTH-BLOCKED` | `v1_health_status` | statut `BLOCKED` | `docs/governance/m013_v1_gap_decisions.md` |
| `M013-ALERT-SPARK-DOWN` | `spark_inference_availability` | indisponibilité ou TLS refusé | `docs/governance/m013_spark_failure_drill.md` |
| `M013-ALERT-RESTORE-MISSING` | `backup_restore_result` | `restore_test_result` absent | `docs/governance/m013_backup_restore_drill.md` |
| `M013-ALERT-SECURITY-VIOLATION` | `network_security_violation_total` | compteur supérieur à zéro | `docs/governance/m013_security_audit.md` |
| `M013-ALERT-GAP-BLOCKING` | `v1_gap_status` | écart bloquant ou différé non accepté | `docs/governance/m013_v1_gap_decisions.md` |

## Commandes de preuve

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_local_monitoring_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_local_monitoring_unit.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_monitoring.ps1
```
