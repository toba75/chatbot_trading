# T-003 - Contrôler les écarts V1 issus de M-012

## Milestone
- Nom: M-013 - Durcissement et acceptation V1.
- Source: `docs/governance/m012_v1_gap_report.md`, critères V1 de la section 21 et livrable M-013 `liste des écarts non acceptés`.
- Objectif métier: décider explicitement si chaque écart V1 M-012 est corrigé, accepté, différé ou bloquant avant le rapport final V1.

## Contexte DDD
- Domaine: durcissement opérationnel et acceptation V1.
- Bounded context: gouvernance V1 consommant EV et les preuves de SP, KA, EG, RA, CV, SD, LLM et EX.
- Objectif métier: empêcher qu'un écart scientifique ou fonctionnel soit effacé par une gate logicielle GREEN.
- Langage ubiquitaire: écart V1, écart bloquant, écart différé, écart accepté, décision V1, preuve de correction, preuve de non-acceptation, test scientifique RED.
- Invariants critiques: un écart bloquant interdit l'acceptation V1; une correction référence un test GREEN; un différé possède une justification; un refus reste visible; M-013 ne réécrit pas les benchmarks M-012.
- Garde-fous: pas de suppression d'écart; pas de statut par défaut; pas de correction par modification du rapport M-012; pas d'acceptation sans preuve; pas de seuil inventé.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-002; le rapport M-012 publie notamment SP, KA et RA comme `différé`, SD et LLM comme `bloquant`, EG, CV et EX comme `satisfait`.
- Présence des milestones amont dans master: M-012 présent dans `master`.
- Décisions manquantes: ADR requise si une décision V1 change un critère d'acceptation, une politique de calibration ou la frontière d'un bounded context.
- Risques: déclarer acceptable un écart SD ou LLM bloquant; oublier un écart différé; recalculer une métrique M-012 au lieu de publier une décision M-013 distincte.

## Tâches
### T-003 - Contrôler les écarts V1 issus de M-012
- But métier: fournir à la gate V1 une liste décisionnelle complète des écarts hérités de M-012.
- Portée DDD: `V1GapDecisionPolicy`, `V1GapDecision`, statuts d'écart, lien vers benchmark source, lien vers décision de calibration, preuve de correction M-013, justification de non-acceptation, refus d'acceptation globale en présence d'un bloquant.
- Scénario BDD:
  - Given le rapport M-012 contient des écarts V1 satisfaits, différés et bloquants.
  - When M-013 publie les décisions d'écarts V1.
  - Then chaque écart conserve son benchmark source, reçoit une décision explicite et bloque l'acceptation V1 si son statut reste bloquant.
- Tests d'acceptation à écrire: `tests/m013/validate_v1_gap_decisions_acceptance.ps1`, qui échoue si un écart M-012 est absent, si SD ou LLM est accepté sans preuve GREEN, si un différé n'a pas de justification, si un benchmark source manque ou si le rapport d'acceptation ignore un écart non accepté.
- Tests unitaires à écrire: tests de `V1GapDecisionPolicy` et de `scripts/validate_m013_v1_gap_decisions.ps1` pour statut inconnu, décision sans preuve, correction sans commande, écart bloquant accepté, écart différé sans justification, décision contredisant M-012, duplication d'écart et absence de lien vers critères V1.
- Implémentation attendue: créer le modèle de décision V1, publier `docs/governance/m013_v1_gap_decisions.md`, créer `scripts/validate_m013_v1_gap_decisions.ps1`, relier chaque écart SP, KA, EG, RA, CV, SD, LLM et EX aux preuves ou non-acceptations, puis mettre à jour la traçabilité.
- Invariants et garde-fous: aucun écart M-012 supprimé; aucun statut implicite; aucun benchmark M-012 réécrit; aucune acceptation V1 avec écart bloquant non corrigé; aucune preuve sans commande.
- Dépendances: T-002; `docs/governance/m012_v1_gap_report.md`; `docs/traceability/matrix.md`; ADR-010; DDD-ADR-011.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_v1_gap_decisions_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_v1_gap_decisions_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_v1_gap_decisions.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_specification.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m013): couvrir decisions ecarts v1`
- Commit GREEN: `feat(m013): controler ecarts v1`
