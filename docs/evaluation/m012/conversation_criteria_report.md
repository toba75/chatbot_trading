# Rapport T-011 - Critères conversationnels CV M-012

## Scénario BDD

- Given les critères V1 du contexte conversation sont publiés par M-008.
- When M-012 produit les décisions de calibration et de promotion.
- Then la décision CV référence un rapport dédié aux critères conversationnels sans réutiliser un artefact RA comme source implicite.

## Source

- Benchmark source: `CVRUN-M012-CRITERIA-0001`.
- Politique: `ConversationCriteriaPolicy-M012-1.0`.
- ADR appliquées: ADR-010 et DDD-ADR-010.
- Spécification source: `docs/specs/m008_conversation_produit.md`.

## Critères CV

| Critère | Statut M-012 | Justification |
|---|---|---|
| `conversation_creation_criterion` | ACCEPTED | La création et l'ajout de tours visibles restent requis. |
| `conversation_follow_up_resolution_rate` | ACCEPTED | Une question de suivi doit être résolue en question autonome avant appel aval. |
| `conversation_mode_routing_justified_rate` | ACCEPTED | Le routage de mode doit rester explicite et justifié. |
| `conversation_raw_history_fact_usage_rejection_total` | ACCEPTED | L'historique brut ne peut pas devenir une preuve factuelle sans revalidation. |

## Garde-fous

- Aucun prompt complet ni historique brut complet n'est publié.
- Aucun stockage RA, EG ou KA interne n'est lu pour produire la décision CV.
- Aucun endpoint HTTP nouveau n'est introduit par M-012; le rapport publie un artefact de décision exploitable par les gates.

## Commandes de preuve

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_calibration_decisions_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_calibration_decisions_unit.ps1
```
