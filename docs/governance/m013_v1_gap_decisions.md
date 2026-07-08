# Décisions d'écarts V1 M-013

## Scénario BDD

- Given le rapport M-012 contient des écarts V1 satisfaits, différés et bloquants.
- When M-013 publie les décisions d'écarts V1.
- Then chaque écart conserve son benchmark source, reçoit une décision explicite et bloque l'acceptation V1 si son statut reste bloquant.

## Politique de décision

`V1GapDecisionPolicy` contrôle les objets `V1GapDecision` publiés par T-003. La politique consomme `docs/governance/m012_v1_gap_report.md`, applique ADR-010 et DDD-ADR-011, et ne réécrit aucun benchmark M-012.

Invariants:

- aucun écart M-012 SP, KA, EG, RA, CV, SD, LLM ou EX n'est supprimé;
- aucun statut ou décision V1 n'est déduit par défaut;
- une décision `corrigé` référence une commande de correction et une preuve GREEN;
- une décision `différé` ou `bloquant` possède une justification de non-acceptation;
- un écart bloquant M-012 ne peut pas devenir `accepté` sans correction GREEN;
- M-013 ne réécrit pas les benchmarks M-012.

## Décisions V1

| Contexte | Statut M-012 | Décision M-013 | Critère V1 | Benchmark source | Décision calibration | Commande de preuve | Commande de correction | Justification de non-acceptation | Impact acceptation V1 |
|---|---|---|---|---|---|---|---|---|---|
| SP | différé | différé | V1-SP-QUALITE-DOCUMENTAIRE | RBRUN-M012-DOCUMENT-ROUTES-0001 | DEC-M012-SP-DEFERRED | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_document_quality_calibration_acceptance.ps1 | Non applicable: T-003 ne corrige pas cet écart. | document_cell_accuracy reste un Test scientifique RED; report visible avant le rapport final V1. | Écart non accepté transmis au V1AcceptanceReport. |
| KA | différé | différé | V1-KA-RECHERCHE-PAGES | KSRUN-M012-KNOWLEDGE-0001 | DEC-M012-KA-REJECTED | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_knowledge_search_benchmark_acceptance.ps1 | Non applicable: T-003 ne corrige pas cet écart. | Recall@10 pilote sous seuil; report visible avant le rapport final V1. | Écart non accepté transmis au V1AcceptanceReport. |
| EG | satisfait | accepté | V1-EG-GOUVERNANCE-PREUVES | EGRUN-M012-0001 | DEC-M012-EG-ACCEPTED | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_verified_answer_benchmark_acceptance.ps1 | Non applicable: T-003 ne corrige pas cet écart. | Non applicable: écart satisfait et accepté explicitement. | Ne bloque pas l'acceptation V1. |
| RA | différé | différé | V1-RA-REPONSES-VERIFIEES | VARUN-M012-VERIFIED-ANSWERS-0001 | DEC-M012-RA-DEFERRED | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_verified_answer_benchmark_acceptance.ps1 | Non applicable: T-003 ne corrige pas cet écart. | answer_correct_abstention_rate reste à renforcer; report visible avant le rapport final V1. | Écart non accepté transmis au V1AcceptanceReport. |
| CV | satisfait | accepté | V1-CV-CONVERSATION-PRODUIT | CVRUN-M012-CRITERIA-0001 | DEC-M012-CV-ACCEPTED | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_calibration_decisions_acceptance.ps1 | Non applicable: T-003 ne corrige pas cet écart. | Non applicable: écart satisfait et accepté explicitement. | Ne bloque pas l'acceptation V1. |
| SD | bloquant | bloquant | V1-SD-PARAMETRES-CALIBRABLES | SBRUN-M012-STRATEGY-BACKTEST-0001 | DEC-M012-SD-REJECTED | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_strategy_backtest_benchmark_acceptance.ps1 | Non applicable: T-003 ne corrige pas cet écart. | Paramètres sans plan de calibration; l'écart bloque toute acceptation V1. | Acceptation V1 refusée tant que l'écart reste bloquant. |
| LLM | bloquant | bloquant | V1-LLM-CHECKPOINT-PRINCIPAL | LLMRUN-M012-REAL-PATH-0001 | DEC-M012-LLM-REJECTED | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_llm_benchmark_real_path_acceptance.ps1 | Non applicable: T-003 ne corrige pas cet écart. | Checkpoint principal non promu sur toutes les tâches obligatoires; l'écart bloque l'acceptation V1. | Acceptation V1 refusée tant que l'écart reste bloquant. |
| EX | satisfait | accepté | V1-EX-BACKTESTS-REPRODUCTIBLES | SBRUN-M012-EXPERIMENTS-0001 | DEC-M012-EX-ACCEPTED | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_strategy_backtest_benchmark_acceptance.ps1 | Non applicable: T-003 ne corrige pas cet écart. | Non applicable: écart satisfait et accepté explicitement. | Ne bloque pas l'acceptation V1. |

## Liste des écarts non acceptés à transmettre au V1AcceptanceReport

| Contexte | Décision M-013 | Justification | Transmission V1AcceptanceReport |
|---|---|---|---|
| SP | différé | document_cell_accuracy reste un Test scientifique RED. | Obligatoire: écart non accepté. |
| KA | différé | Recall@10 pilote sous seuil. | Obligatoire: écart non accepté. |
| RA | différé | answer_correct_abstention_rate reste à renforcer. | Obligatoire: écart non accepté. |
| SD | bloquant | Paramètres sans plan de calibration. | Obligatoire: bloque l'acceptation V1. |
| LLM | bloquant | Checkpoint principal non promu sur toutes les tâches obligatoires. | Obligatoire: bloque l'acceptation V1. |

## Verdict

Acceptation V1 refusée: SD et LLM restent `bloquant`, et SP, KA et RA restent des écarts non acceptés à transmettre au V1AcceptanceReport.

## Commandes de validation

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_v1_gap_decisions_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_v1_gap_decisions_unit.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_v1_gap_decisions.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_specification.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1
```

## ADR

ADR: non requise; T-003 applique ADR-010 et DDD-ADR-011 sans changer critère d'acceptation, politique de calibration ou frontière de bounded context.
