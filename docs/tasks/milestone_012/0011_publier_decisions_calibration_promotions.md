# T-011 - Publier les décisions de calibration et de promotion

## Milestone
- Nom: M-012 - Évaluation pilote et calibration.
- Source: M-012, livrables `seuils calibrés` et critères de promotion des checkpoints.
- Objectif métier: transformer les benchmarks M-012 en décisions explicites, acceptées, refusées ou différées.

## Contexte DDD
- Domaine: évaluation scientifique et calibration des seuils.
- Bounded context: transverse d'évaluation, propriétaire des décisions de calibration, sans réécrire les résultats des contextes évalués.
- Objectif métier: publier les seuils, promotions, refus et reports avec preuve métrique et statut d'écart V1.
- Langage ubiquitaire: décision de calibration, décision de promotion, seuil calibré, référence officielle, checkpoint communautaire, écart V1, test scientifique RED, justification.
- Invariants critiques: toute décision référence des résultats de benchmark; un refus ou un report est conservé; un test scientifique échoué ne peut pas être masqué par un test logiciel GREEN; une promotion communautaire exige comparaison supérieure ou égale aux références.
- Garde-fous: aucune décision implicite dans un fichier de configuration; aucune suppression de décision défavorable; aucun seuil sans version; aucune promotion avec métrique manquante.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-010.
- Présence des milestones amont dans master: M-011 présent dans `master`.
- Décisions manquantes: une ADR doit être créée si une décision de calibration devient structurante pour l'architecture ou remplace une ADR acceptée.
- Risques: mélanger calibration documentaire, recherche, gouvernance des preuves, réponses, stratégies, LLM et backtests dans une décision globale opaque; oublier les décisions refusées; promouvoir malgré une métrique critique RED.

## Tâches
### T-011 - Publier les décisions de calibration et de promotion
- But métier: rendre les choix M-012 auditables et réversibles par nouvelle décision versionnée.
- Portée DDD: `CalibrationDecision`, `PromotionDecision`, `ScientificGateVerdict`, seuils SP, seuils KA, critères EG, seuils RA, critères CV, critères SD, checkpoint LLM, critères EX, statuts `ACCEPTED`, `REJECTED`, `DEFERRED`, liens vers benchmarks et écarts V1.
- Scénario BDD:
  - Given les benchmarks documentaires, recherche, gouvernance des preuves, réponses, stratégies, LLM et backtests sont terminés.
  - When les décisions de calibration et promotion sont publiées.
  - Then chaque décision référence ses métriques sources, conserve les refus et empêche qu'un test scientifique RED soit caché par un gate logiciel GREEN.
- Tests d'acceptation à écrire: `tests/m012/validate_calibration_decisions_acceptance.ps1`, qui échoue si une décision n'a pas de benchmark source, si un refus n'est pas conservé, si une promotion communautaire manque de comparaison sur une tâche LLM obligatoire, si un test scientifique RED est absent du rapport, si une décision EG, RA, CV ou SD manque, ou si un seuil est publié sans version.
- Tests unitaires à écrire: tests de `CalibrationDecisionPolicy` pour décision sans métrique, seuil sans version, promotion insuffisante, refus conservé, report conservé, conflit de décisions, métrique EG manquante, métrique RA manquante, critère CV manquant, métrique SD manquante, tâche LLM obligatoire absente, métrique critique RED, benchmark obsolète et ADR requise non référencée.
- Implémentation attendue: créer le registre des décisions M-012, la politique de verdict scientifique, les rapports de seuils ou critères par contexte SP, KA, EG, RA, CV, SD et EX, les contrôles de promotion LLM sur toutes les tâches obligatoires et les liens vers ADR lorsque nécessaire.
- Invariants et garde-fous: aucun statut par défaut; aucune décision favorable si une métrique critique manque; aucune décision favorable si une métrique RA, EG, SD, un critère CV ou une tâche LLM obligatoire manque; aucune réécriture d'un benchmark; aucune décision structurante sans ADR ou référence ADR existante.
- Dépendances: T-006; T-007; T-008; T-009; T-010; `docs/adr/TEMPLATE.md`; `docs/adr/index.md`; `docs/specs/m012_evaluation_pilote_calibration.md`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_calibration_decisions_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_calibration_decisions_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m012_specification.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_adr_system.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m012): couvrir decisions calibration promotion`
- Commit GREEN: `feat(m012): publier decisions calibration promotion`
