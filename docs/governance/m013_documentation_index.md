# Index documentation M-013

## Statut

- Identifiant: `M013-DocumentationIndex-1.0`
- Tâche: `docs/tasks/milestone_013/0010_publier_runbooks_documentation_utilisateur.md`
- Politique appliquée: `RunbookPolicy` et `UserDocumentationPolicy` de `docs/specs/m013_durcissement_acceptation_v1.md`.
- ADR applicables: ADR-010, ADR-046 et ADR-048.
- ADR: ADR-048 remplace formellement les anciens points d'entrée tout en conservant progression et parallélisme.

## Scénario BDD

- Given la V1 possède des gates, sauvegardes, restauration, audit réseau, pannes Spark, monitoring et écarts.
- When les runbooks et la documentation utilisateur sont publiés.
- Then chaque document cite les commandes vérifiées, les preuves, les statuts publics, les limites et les garde-fous sans fallback silencieux.

## Documents publiés

| Document | Rôle | Commandes vérifiées | Preuve source |
|---|---|---|---|
| docs/runbooks/environnements_explicites.md | Chemin opérateur unique development, test et production; export de la CA Caddy; opérations bornées. | `uv run --locked gate --scope m013_environments --offline`; `uv run --locked gate --scope m013_environments --live` | `deploy/environments/compose.base.yaml`; `deploy/environments/*.compose.yaml` |
| docs/runbooks/exploitation_locale.md | Document historique déprécié; redirige vers les environnements explicites. | `uv run --locked gate --scope m013_environments --offline` | `docs/runbooks/environnements_explicites.md` |
| docs/runbooks/configuration_applicative.md | Document M13-config déprécié; aucun chemin opératoire actif. | `uv run --locked gate --scope m013_environments --offline` | ADR-046 |
| docs/runbooks/api_orchestratrice.md | Document M13-FastAPI déprécié; l'API est interne au profil sélectionné. | `uv run --locked gate --scope m013_environments --offline` | ADR-046 ; ADR-048 |
| docs/runbooks/sauvegarde_restauration.md | Sauvegarde, restauration et `restore_test_result`. | `scripts\backup_v1.ps1`; `scripts\restore_v1.ps1`; `scripts\validate_m013_backup_restore.ps1` | `docs/governance/m013_backup_restore_drill.md` |
| docs/runbooks/spark_reseau_incidents.md | Audit réseau, panne Spark et statuts publics. | `scripts\validate_m013_security.ps1`; `scripts\validate_m013_spark_failures.ps1` | `docs/governance/m013_security_audit.md`; `docs/governance/m013_spark_failure_drill.md` |
| docs/runbooks/certificats_spark.md | Validation de certificat, rotation certificat et refus TLS/authentification. | `scripts\validate_m013_security.ps1`; `scripts\validate_network_boundary.ps1` | `docs/governance/m013_security_audit.md` |
| docs/runbooks/monitoring_local.md | Monitoring local et profil ressources. | `scripts\validate_m013_monitoring.ps1` | `docs/governance/m013_local_monitoring.md`; `docs/governance/m013_resource_profile.md` |
| docs/runbooks/ingestion_pdf.md | Ingestion PDF, route explicite et version canonique. | `scripts\validate_m003_specification.ps1`; `scripts\validate_m004_specification.ps1` | `docs/specs/m003_source_enregistree_diagnostiquee_routee.md`; `docs/specs/m004_version_canonique_publiee.md` |
| docs/runbooks/conversation_v1.md | Conversation locale, citations et pannes Spark. | `scripts\validate_m008_specification.ps1`; `scripts\validate_m013_spark_failures.ps1` | `docs/specs/m008_conversation_produit.md`; `docs/governance/m013_spark_failure_drill.md` |
| docs/runbooks/recherche_approfondie.md | Recherche approfondie multi-sources et limites. | `scripts\validate_m009_specification.ps1` | `docs/specs/m009_recherche_approfondie_multi_sources.md` |
| docs/runbooks/strategie_backtest.md | Stratégie, métriques SD et backtest EX. | `scripts\validate_m010_specification.ps1`; `scripts\validate_m011_specification.ps1`; `tests\m012\validate_strategy_backtest_benchmark_acceptance.ps1` | `docs/evaluation/m012/strategy_backtest_benchmark_report.md` |
| docs/runbooks/purge_administrative.md | Purge administrative, archive logique et reconstruction de projection KA. | `scripts\validate_m013_retention.ps1`; `scripts\rebuild_knowledge_projection.ps1` | `docs/governance/m013_retention_policy.md` |
| docs/runbooks/rapport_acceptation_v1.md | Lecture du rapport d'acceptation V1 et traçabilité du verdict final. | `scripts\validate_m013_acceptance.ps1`; `scripts\validate_traceability.ps1` | `docs/governance/m013_v1_acceptance_report.md`; `docs/traceability/matrix.md` |
| docs/user/v1_guide_utilisateur.md | Documentation utilisateur V1. | `scripts\validate_m013_runbooks.ps1` | `docs/governance/m013_documentation_index.md` |

## Commandes vérifiées

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_runbooks_user_docs_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_runbooks_user_docs_unit.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_runbooks.ps1
```

## Limites et écarts V1

- SP, KA et RA restent différés.
- SD et LLM restent bloquants.
- Les statuts publics sont visibles dans `docs/user/v1_guide_utilisateur.md`.
- Les métriques SD `strategy_compilable_rate`, `strategy_rejection_reason_distribution`, `strategy_parameter_without_calibration_plan_total` et `strategy_compatibility_conflict_total` restent visibles dans `docs/runbooks/strategie_backtest.md`.

## Garde-fous

- Aucune publication de service interne.
- Aucun secret.
- Aucune promesse financière.
- Aucune commande destructive sans précondition.
- Aucun fallback silencieux.
- Aucune valeur par défaut implicite.
- Aucune correction silencieuse d'un écart V1.
