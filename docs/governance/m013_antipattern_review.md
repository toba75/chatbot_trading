# Revue anti-patterns interdits V1 M-013

## Statut

- Identifiant: `M013-ForbiddenAntiPatternReview-1.0`
- Politique: `ForbiddenAntiPatternPolicy`
- Tâche: `docs/tasks/milestone_013/0011_verifier_antipatterns_v1.md`
- Source normative: `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, section 23.
- Date de revue: 2026-07-08
- Périmètre revu: section 23, spécification M-013, audits réseau, pannes Spark, sauvegarde/restauration, rétention, monitoring, runbooks, traçabilité et ADR.
- Verdict T-011: aucune violation active.
- ADR: non requise; T-011 ne tranche pas de nouvelle question ouverte et applique les décisions existantes ADR-007, ADR-008, ADR-009, DDD-ADR-004, DDD-ADR-006, DDD-ADR-010 et DDD-ADR-012.

## Scénario BDD

- Given la spécification V1 liste les anti-patterns interdits et les questions ouvertes contrôlées.
- When la validation M-013 des anti-patterns s'exécute.
- Then chaque interdiction possède un contrôle automatisé ou une revue documentée datée avec preuve et périmètre, toute violation bloque l'acceptation V1, et aucune question ouverte n'est résolue sans ADR.

## Contrôles transverses reliés

| Contrôle relié | Portée | Preuve |
|---|---|---|
| `scripts/validate_architecture_boundaries.ps1` | frontières de bounded contexts, absence de dépendances techniques dans le domaine et refus du microservice imposé | `docs/specs/m001_frontieres_ddd_contrats_publies.md` |
| `scripts/validate_network_boundary.ps1` | exposition réseau, egress Spark, TLS et refus du navigateur vers Spark | `deploy/spark-firewall/network-boundary.json` |
| `scripts/validate_traceability.ps1` | rattachement des exigences, tests, artefacts et ADR | `docs/traceability/matrix.md` |
| `scripts/validate_adr_system.ps1` | questions structurantes tranchées uniquement par ADR | `docs/adr/index.md` |
| `scripts/validate_m013_security.ps1` | frontière `llm-gateway -> spark-inference`, vLLM non exposé au LAN, Spark sans données métier | `docs/governance/m013_security_audit.md` |
| `scripts/validate_m013_backup_restore.ps1` | Qdrant projection régénérable, restauration testée et conservation des artefacts défavorables | `docs/governance/m013_backup_restore_drill.md` |
| `scripts/validate_m013_retention.ps1` | conservation des résultats négatifs, versions supersédées et purge administrative explicite | `docs/governance/m013_retention_policy.md` |
| `scripts/validate_m013_monitoring.ps1` | absence de prompt complet persistant, contexte et concurrence sourcés par benchmark | `docs/governance/m013_local_monitoring.md`; `docs/governance/m013_resource_profile.md` |
| `scripts/validate_m013_runbooks.ps1` | runbooks sans fallback, sans service interne publié et sans secret | `docs/governance/m013_documentation_index.md`; `docs/runbooks/conversation_v1.md` |

## Anti-patterns contrôlés

| Anti-pattern interdit | Contrôle | Type | Preuve | Périmètre | Date | Statut bloquant |
|---|---|---|---|---|---|---|
| Conversation utilisée comme source factuelle | `CTRL-M013-DOMAIN-001` | validation documentaire | `docs/runbooks/conversation_v1.md` | CV, RA, EG | 2026-07-08 | Bloque si la conversation remplace les preuves publiées. |
| Score de similarité traité comme preuve | `CTRL-M013-DOMAIN-002` | revue de preuves | `docs/evaluation/m012/knowledge_search_benchmark_report.md` | KA, EG, RA | 2026-07-08 | Bloque si un score KA devient preuve EG. |
| Affirmation vérifiée sans span direct | `CTRL-M013-DOMAIN-003` | revue de preuves | `docs/evaluation/m012/evidence_governance_benchmark_report.md` | EG, RA | 2026-07-08 | Bloque si un claim vérifié n'a pas de span direct. |
| Règle de stratégie sans origine | `CTRL-M013-DOMAIN-004` | validation de spécification | `scripts/validate_m010_specification.ps1` | SD | 2026-07-08 | Bloque si une règle de stratégie n'a pas d'origine publiée. |
| Paramètre inventé silencieusement | `CTRL-M013-DOMAIN-004` | validation de spécification | `docs/governance/m013_v1_gap_decisions.md` | SD | 2026-07-08 | Bloque si un paramètre est ajouté sans plan de calibration. |
| Résultat négatif supprimé | `CTRL-M013-RETENTION-001` | validation de rétention | `docs/governance/m013_retention_policy.md` | EG, RA, SD, EX, EV | 2026-07-08 | Bloque si un résultat défavorable est purgé hors opération administrative autorisée. |
| Version publiée modifiée en place | `CTRL-M013-RETENTION-001` | validation de rétention | `docs/governance/m013_retention_policy.md` | SP, RA, SD, EX | 2026-07-08 | Bloque si une version publiée est mutée au lieu d'être supersédée. |
| Accès direct d'un contexte métier au protocole vLLM | `CTRL-M013-NET-001` | validation réseau | `docs/governance/m013_security_audit.md` | RA, CV, SD, EV, workers | 2026-07-08 | Bloque si un contexte contourne `llm-gateway`. |
| Bounded contexts ou bases déployés sur le Spark | `CTRL-M013-NET-002` | audit de topologie | `docs/governance/m013_security_audit.md`; `docs/governance/m013_backup_restore_drill.md` | platform, stockages, workers | 2026-07-08 | Bloque si un stockage ou contexte métier réside sur Spark. |
| Navigateur ou interface appelant directement le Spark | `CTRL-M013-NET-003` | validation réseau | `docs/governance/m013_security_audit.md` | UI, edge-gateway, Spark | 2026-07-08 | Bloque si le navigateur reçoit URL ou secret Spark. |
| Service Gemma caché dans le Compose local comme fallback non déclaré | `CTRL-M013-LLM-001` | audit réseau et runbooks | `docs/governance/m013_security_audit.md`; `docs/governance/m013_spark_failure_drill.md` | platform, LLM | 2026-07-08 | Bloque si un provider alternatif est appelé silencieusement. |
| Retry illimité d'une génération distante | `CTRL-M013-LLM-002` | drill panne Spark | `docs/governance/m013_spark_failure_drill.md` | LLM gateway | 2026-07-08 | Bloque si un retry après premier token ou illimité est accepté. |
| Prompt complet persistant | `CTRL-M013-MONITORING-001` | validation monitoring | `docs/governance/m013_local_monitoring.md` | logs, métriques, Spark | 2026-07-08 | Bloque si un prompt complet devient journal persistant. |
| Qdrant source de vérité | `CTRL-M013-BACKUP-001` | sauvegarde/restauration | `docs/governance/m013_backup_restore_drill.md`; `docs/adr/DDD-ADR-004-qdrant-projection-regenerable.md` | KA, backup, restauration | 2026-07-08 | Bloque si Qdrant devient autorité métier. |
| Checkpoint quantifié sans benchmark | `CTRL-M013-MONITORING-002` | benchmark et profil ressources | `docs/evaluation/m012/llm_real_path_benchmark_report.md`; `docs/governance/m013_resource_profile.md` | EV, LLM | 2026-07-08 | Bloque si un checkpoint quantifié est promu sans benchmark métier. |
| Contexte 256K par défaut | `CTRL-M013-MONITORING-002` | benchmark et profil ressources | `docs/governance/m013_resource_profile.md` | LLM gateway | 2026-07-08 | Bloque si la longueur de contexte n'est pas sourcée par benchmark. |
| Microservice par contexte imposé | `CTRL-M013-ARCH-001` | validation architecture | `scripts/validate_architecture_boundaries.ps1`; `docs/adr/DDD-ADR-001-monolithe-modulaire.md` | architecture transverse | 2026-07-08 | Bloque si le DDD est traduit en microservices obligatoires. |

## Questions ouvertes contrôlées

| Sujet | Statut | Décision | ADR | Preuve |
|---|---|---|---|---|
| Frontière exacte de KA | ouverte contrôlée | Non tranchée | ADR requise si résolution future | `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md` |
| Langage d'expression des règles | ouverte contrôlée | Non tranchée | ADR requise si résolution future | `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md` |
| Granularité maximale d'un claim | ouverte contrôlée | Non tranchée | ADR requise si résolution future | `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md` |
| Politique de vérification | ouverte contrôlée | Non tranchée | ADR requise si résolution future | `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md` |
| Revue humaine | ouverte contrôlée | Non tranchée | ADR requise si résolution future | `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md` |
| Moteur de backtest | ouverte contrôlée | Non tranchée | ADR requise si résolution future | `docs/evaluation/m012/strategy_backtest_benchmark_report.md` |
| Conservation | résolue par ADR | Durées V1 et purge administrative explicite | DDD-ADR-012 | `docs/governance/m013_retention_policy.md` |
| Données de marché | ouverte contrôlée | Non tranchée | ADR requise si résolution future | `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md` |
| Versioning des réponses | ouverte contrôlée | Non tranchée | ADR requise si résolution future | `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md` |
| Graphe de claims | ouverte contrôlée | Non tranchée | ADR requise si résolution future | `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md` |
| Hôte Docker local | ouverte contrôlée | Capacité mesurée sans seuil matériel V1 final | ADR requise si résolution future | `docs/governance/m013_resource_profile.md` |
| Sécurité inter-hôtes | ouverte contrôlée | Non tranchée | ADR requise si résolution future | `docs/governance/m013_security_audit.md` |
| Résolution réseau | ouverte contrôlée | Non tranchée | ADR requise si résolution future | `docs/governance/m013_security_audit.md` |
| Disponibilité du Spark | ouverte contrôlée | Non tranchée | ADR requise si résolution future | `docs/governance/m013_spark_failure_drill.md` |

## Violations bloquantes refusées

- vLLM exposé à tout le LAN sans filtrage par adresse source: refusé par `CTRL-M013-NET-001`.
- fallback LLM silencieux: refusé par `CTRL-M013-LLM-001`.
- Qdrant source de vérité: refusé par `CTRL-M013-BACKUP-001`.
- historique conversationnel factuel: refusé par `CTRL-M013-DOMAIN-001`.
- résultat négatif supprimé: refusé par `CTRL-M013-RETENTION-001`.
- prompt complet persistant: refusé par `CTRL-M013-MONITORING-001`.
- checkpoint quantifié sans benchmark: refusé par `CTRL-M013-MONITORING-002`.
- contexte 256K par défaut: refusé par `CTRL-M013-MONITORING-002`.
- microservice par contexte imposé: refusé par `CTRL-M013-ARCH-001`.

## Commandes de preuve

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_v1_antipatterns_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_v1_antipatterns_unit.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_antipatterns.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_architecture_boundaries.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_network_boundary.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_adr_system.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_security.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_backup_restore.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_retention.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_monitoring.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_runbooks.ps1
```
