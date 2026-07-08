# Rapport d'acceptation V1 M-013

## Statut

- Identifiant: `M013-V1AcceptanceReport-1.0`
- Politique: `V1AcceptanceReportPolicy`
- Tâche: `docs/tasks/milestone_013/0012_publier_rapport_acceptation_v1.md`
- Spécification: `docs/specs/m013_durcissement_acceptation_v1.md`
- Date de publication: 2026-07-08
- Verdict V1: non acceptée
- ADR applicables: ADR-010; DDD-ADR-010; DDD-ADR-011.
- ADR: non requise; T-012 agrège les preuves existantes sans changer la politique de gates, la conservation des résultats négatifs ni la propriété EV des écarts V1.

## Scénario BDD

- Given M-013 a livré décisions d'écarts, régression, audit sécurité, drill Spark, sauvegarde/restauration, rétention, monitoring, runbooks et anti-patterns.
- When la gate finale V1 agrège les preuves.
- Then le rapport d'acceptation publie un verdict par critère, refuse l'acceptation en présence d'un bloquant et liste les écarts non acceptés avec leurs commandes de preuve.

## Verdict synthétique

Acceptation V1 refusée: la V1 est en non-acceptation. Les critères EG, CV et EX sont acceptés; SP, KA et RA restent différés; SD et LLM restent bloquants. La présence des bloquants SD et LLM interdit le verdict `acceptée`.

Le rapport distingue:

- acceptation: critère satisfait et explicitement accepté avec preuve;
- non-acceptation: écart différé ou bloquant non accepté;
- différé: report visible qui ne devient pas accepté sans décision explicite future.

## Verdicts par critère

| Critère V1 | Contexte | Verdict | Preuve | Commande de preuve | ADR | Impact final |
|---|---|---|---|---|---|---|
| V1-SP-QUALITE-DOCUMENTAIRE | SP | différé | docs/governance/m013_v1_gap_decisions.md; docs/evaluation/m013/v1_regression_suite.json | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_document_quality_calibration_acceptance.ps1 | ADR-010; DDD-ADR-010; DDD-ADR-011 | Écart non accepté: qualité documentaire pilote différée. |
| V1-KA-RECHERCHE-PAGES | KA | différé | docs/governance/m013_v1_gap_decisions.md; docs/evaluation/m013/v1_regression_suite.json | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_knowledge_search_benchmark_acceptance.ps1 | ADR-010; DDD-ADR-010; DDD-ADR-011 | Écart non accepté: rappel pilote KA sous seuil. |
| V1-EG-GOUVERNANCE-PREUVES | EG | accepté | docs/governance/m013_v1_gap_decisions.md; docs/evaluation/m012/evidence_governance_benchmark_report.md | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_verified_answer_benchmark_acceptance.ps1 | ADR-010; DDD-ADR-010; DDD-ADR-011 | Accepté: gouvernance des preuves séparée de RA. |
| V1-RA-REPONSES-VERIFIEES | RA | différé | docs/governance/m013_v1_gap_decisions.md; docs/evaluation/m012/verified_answer_benchmark_report.md | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_verified_answer_benchmark_acceptance.ps1 | ADR-010; DDD-ADR-010; DDD-ADR-011 | Écart non accepté: abstention correcte à renforcer. |
| V1-CV-CONVERSATION-PRODUIT | CV | accepté | docs/governance/m013_v1_gap_decisions.md; docs/evaluation/m012/conversation_criteria_report.md | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_calibration_decisions_acceptance.ps1 | ADR-010; DDD-ADR-010; DDD-ADR-011 | Accepté: critères conversationnels V1 satisfaits. |
| V1-SD-PARAMETRES-CALIBRABLES | SD | bloquant | docs/governance/m013_v1_gap_decisions.md; docs/evaluation/m012/strategy_backtest_benchmark_report.md | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_strategy_backtest_benchmark_acceptance.ps1 | ADR-010; DDD-ADR-010; DDD-ADR-011 | Écart bloquant: paramètres sans plan de calibration. |
| V1-LLM-CHECKPOINT-PRINCIPAL | LLM | bloquant | docs/governance/m013_v1_gap_decisions.md; docs/evaluation/m012/llm_real_path_benchmark_report.md | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_llm_benchmark_real_path_acceptance.ps1 | ADR-010; DDD-ADR-010; DDD-ADR-011 | Écart bloquant: checkpoint principal non promu sur toutes les tâches obligatoires. |
| V1-EX-BACKTESTS-REPRODUCTIBLES | EX | accepté | docs/governance/m013_v1_gap_decisions.md; docs/evaluation/m012/strategy_backtest_benchmark_report.md | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_strategy_backtest_benchmark_acceptance.ps1 | ADR-010; DDD-ADR-010; DDD-ADR-011 | Accepté: expériences reproductibles et résultats négatifs conservés. |

## Preuves agrégées

| Domaine | Preuve | Commande |
|---|---|---|
| décisions d'écarts | docs/governance/m013_v1_gap_decisions.md | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_v1_gap_decisions.ps1 |
| régression | docs/evaluation/m013/v1_regression_suite.json | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_regression.ps1 |
| sécurité réseau | docs/governance/m013_security_audit.md | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_security.ps1 |
| panne Spark | docs/governance/m013_spark_failure_drill.md | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_spark_failures.ps1 |
| sauvegarde/restauration | docs/governance/m013_backup_restore_drill.md | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_backup_restore.ps1 |
| rétention | docs/governance/m013_retention_policy.md | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_retention.ps1 |
| monitoring | docs/governance/m013_local_monitoring.md; docs/governance/m013_resource_profile.md | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_monitoring.ps1 |
| runbooks | docs/governance/m013_documentation_index.md; docs/user/v1_guide_utilisateur.md | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_runbooks.ps1 |
| anti-patterns | docs/governance/m013_antipattern_review.md | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_antipatterns.ps1 |
| traceabilité | docs/traceability/matrix.md | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1 |
| gates finales | docs/governance/m013_v1_acceptance_report.md | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_acceptance.ps1 |

## Écarts non acceptés

| Contexte | Critère V1 | Statut | Justification | Action requise |
|---|---|---|---|---|
| SP | V1-SP-QUALITE-DOCUMENTAIRE | différé | Qualité documentaire pilote différée et conservée comme test scientifique visible. | Publier une correction mesurée ou une décision d'acceptation explicite future. |
| KA | V1-KA-RECHERCHE-PAGES | différé | Recall@10 pilote sous seuil. | Publier une correction mesurée ou une décision d'acceptation explicite future. |
| RA | V1-RA-REPONSES-VERIFIEES | différé | Abstention correcte et réponses vérifiées à renforcer. | Publier une correction mesurée ou une décision d'acceptation explicite future. |
| SD | V1-SD-PARAMETRES-CALIBRABLES | bloquant | Paramètres sans plan de calibration. | Corriger avant toute acceptation V1. |
| LLM | V1-LLM-CHECKPOINT-PRINCIPAL | bloquant | Checkpoint principal non promu sur toutes les tâches obligatoires. | Corriger avant toute acceptation V1. |

## Définition de terminé

La définition de terminé est reliée à `docs/governance/definition_of_done.md`. Elle n'est pas satisfaite pour une acceptation V1 complète parce que le verdict final reste en non-acceptation. Les gates documentaires et logicielles M-013 sont GREEN, mais elles ne transforment pas SD et LLM en critères acceptés.

## Gates finales

| Gate | Commande | Verdict | Preuve |
|---|---|---|---|
| T-012 acceptance | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_v1_acceptance_report_acceptance.ps1 | GREEN | docs/governance/m013_v1_acceptance_report.md |
| T-012 unit | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_v1_acceptance_report_unit.ps1 | GREEN | app/evaluation/domain/v1_acceptance_report.py |
| Rapport final | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_acceptance.ps1 | NON_ACCEPTATION | docs/governance/m013_v1_acceptance_report.md |
| Traçabilité | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1 | GREEN | docs/traceability/matrix.md |
| Spécification M-013 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_specification.ps1 | GREEN | docs/specs/m013_durcissement_acceptation_v1.md |
| Lint | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1 | GREEN | scripts/lint.ps1 |
| Test | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1 | GREEN | scripts/test.ps1 |

## Preuves de sortie des gates finales

| Commande | Sortie capturée |
|---|---|
| powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_v1_acceptance_report_acceptance.ps1 | Test d'acceptation T-012 rapport d'acceptation V1 M-013: OK |
| powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_v1_acceptance_report_unit.ps1 | Tests unitaires V1AcceptanceReportPolicy M-013: OK; Tests unitaires du validateur rapport d'acceptation V1 M-013: OK |
| powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_acceptance.ps1 | Rapport d'acceptation V1 M-013 valide: 8 critère(s), 5 écart(s) non accepté(s), 2 écart(s) bloquant(s), verdict V1 non acceptée. |
| powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1 | Matrice de traçabilité valide: 152 exigence(s) contrôlée(s). |
| powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_specification.ps1 | Spécification M-013 valide: 11 comportement(s), 8 objet(s), 8 écart(s) V1 contrôlé(s). |
| powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1 | Gate lint GREEN: 35 validation(s), 0 test(s). |
| powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1 | Gate test GREEN: 34 validation(s), 292 test(s). |

## Absence de secret

Le rapport ne publie aucun secret, clé API, token bearer, certificat privé, prompt complet, preuve complète, réponse complète ou donnée de marché complète. Les preuves sont référencées par chemin et commande, pas copiées en clair.
