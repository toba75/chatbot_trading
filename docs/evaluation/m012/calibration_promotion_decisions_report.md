# Rapport T-011 - Décisions de calibration et promotion M-012

## Scénario BDD

- Given les benchmarks M-012 sont terminés et publiés comme artefacts sources.
- When les décisions de calibration et promotion sont publiées.
- Then les acceptations, refus et reports restent versionnés avec benchmark, ADR et écart V1.

## Décisions publiées

| Décision | Contexte | Statut | Benchmarks | ADR | Écarts V1 |
|---|---|---|---|---|---|
| `DEC-M012-SP-DEFERRED` | SP | DEFERRED | RBRUN-M012-DOCUMENT-ROUTES-0001 | ADR-010, DDD-ADR-010 | V1-GAP-M012-SP-CELL-QUALITY |
| `DEC-M012-KA-REJECTED` | KA | REJECTED | KSRUN-M012-KNOWLEDGE-0001 | ADR-010, DDD-ADR-010 | V1-GAP-M012-KA-RECALL |
| `DEC-M012-EG-ACCEPTED` | EG | ACCEPTED | EGRUN-M012-0001 | ADR-010, DDD-ADR-010 | Aucun |
| `DEC-M012-RA-DEFERRED` | RA | DEFERRED | VARUN-M012-VERIFIED-ANSWERS-0001 | ADR-010, DDD-ADR-010 | V1-GAP-M012-RA-ABSTENTION |
| `DEC-M012-CV-ACCEPTED` | CV | ACCEPTED | CVRUN-M012-CRITERIA-0001 | ADR-010, DDD-ADR-010 | Aucun |
| `DEC-M012-SD-REJECTED` | SD | REJECTED | SBRUN-M012-STRATEGY-BACKTEST-0001 | ADR-010, DDD-ADR-010 | V1-GAP-M012-SD-CALIBRATION-PLAN |
| `DEC-M012-LLM-REJECTED` | LLM | REJECTED | LLMRUN-M012-REAL-PATH-0001 | ADR-010, DDD-ADR-010 | V1-GAP-M012-LLM-COMMUNITY-PROMOTION |
| `DEC-M012-EX-ACCEPTED` | EX | ACCEPTED | SBRUN-M012-EXPERIMENTS-0001 | ADR-010, DDD-ADR-010 | Aucun |

## Tests scientifiques

Un Test scientifique RED reste publié même quand le gate logiciel GREEN valide le code.

- Test scientifique RED `document_cell_accuracy` depuis `RBRUN-M012-DOCUMENT-ROUTES-0001`: route documentaire sous seuil pilote; gate logiciel GREEN.
- Test scientifique RED `knowledge_recall_at_10` depuis `KSRUN-M012-KNOWLEDGE-0001`: rappel pilote sous seuil de promotion; gate logiciel GREEN.
- Test scientifique RED `answer_correct_abstention_rate` depuis `VARUN-M012-VERIFIED-ANSWERS-0001`: abstention correcte à renforcer; gate logiciel GREEN.
- Test scientifique RED `strategy_parameter_without_calibration_plan_total` depuis `SBRUN-M012-STRATEGY-BACKTEST-0001`: paramètres sans plan de calibration conservés; gate logiciel GREEN.
- Test scientifique RED `exactitude_nombres` depuis `LLMRUN-M012-REAL-PATH-0001`: checkpoint communautaire inférieur aux références sur une tâche obligatoire; gate logiciel GREEN.

## ADR

ADR: non requise; T-011 applique ADR-010 et DDD-ADR-010 sans changer leur sens.
