# T-009 - Conserver les résultats négatifs et les échecs

## Milestone
- Nom: M-011 - Expérience reproductible.
- Source: M-011, DDD-ADR-010 et scénario d'acceptation EX sur le résultat négatif conservé.
- Objectif métier: empêcher l'effacement ou l'amélioration artificielle de l'historique expérimental.

## Contexte DDD
- Domaine: expérimentation quantitative reproductible.
- Bounded context: EX.
- Objectif métier: rendre les résultats défavorables, échoués, archivés ou invalidés consultables sans mutation destructrice.
- Langage ubiquitaire: résultat négatif, échec, archivage logique, invalidation, justification, rétention, supersession, relation de correction, audit.
- Invariants critiques: un résultat négatif ou un échec ne peut pas être supprimé; une invalidation ne détruit rien; une correction crée une nouvelle expérience; l'archivage est logique et explicite.
- Garde-fous: pas de suppression ordinaire; pas de statut favorable recalculé; pas d'invalidation sans justification; pas de correction sous le même `ExperimentId`; pas de purge administrative implicite.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-008.
- Présence des milestones amont dans master: M-010 présent dans `master`.
- Décisions manquantes: aucune si M-011 applique DDD-ADR-010 sans définir la purge administrative M-013.
- Risques: confondre archivage produit et suppression métier; masquer un résultat échoué; invalider un résultat sans trace d'audit; corriger une expérience sans nouvelle expérience liée à l'expérience invalidée.

## Tâches
### T-009 - Conserver les résultats négatifs et les échecs
- But métier: préserver l'intégrité scientifique de l'historique EX.
- Portée DDD: politique `ExperimentRetentionPolicy`, commande `InvalidateExperimentResult`, archivage logique, statuts d'invalidation, justification obligatoire, consultation des résultats négatifs, relation explicite vers l'expérience invalidée lors d'une correction et événements `ExperimentResultInvalidated`.
- Scénario BDD:
  - Given une expérience `COMPLETED` avec un rendement défavorable.
  - When son archivage est demandé.
  - Then le résultat reste immuable et consultable, et seul un statut d'archivage logique peut être appliqué.
- Tests d'acceptation à écrire: `tests/m011/validate_experiment_retention_acceptance.ps1`, qui échoue tant qu'un résultat négatif peut être supprimé, qu'un échec peut disparaître, qu'une invalidation peut manquer de justification, qu'une archive logique rend le résultat inaccessible, ou qu'une correction peut réutiliser le même `ExperimentId` sans créer une nouvelle expérience liée à l'expérience invalidée.
- Tests unitaires à écrire: tests de `ExperimentRetentionPolicy`, `InvalidateExperimentResult`, store append-only, consultation de résultats négatifs, consultation d'échecs, justification obligatoire, statut d'archivage logique, relation de correction vers l'expérience invalidée, création d'une nouvelle expérience liée et interdiction de suppression ordinaire.
- Implémentation attendue: ajouter la politique de rétention EX, l'invalidation non destructive, les relations vers résultat invalidé, la création d'une nouvelle expérience liée lors d'une correction, la consultation des résultats archivés et les événements d'audit.
- Invariants et garde-fous: aucune suppression silencieuse; aucune mutation du payload `ExperimentResult`; aucune invalidation sans raison; aucune correction sous le même `ExperimentId`; aucune correction sans relation vers l'expérience invalidée; aucune archive qui casse `GET` métier; aucune purge administrative dans M-011.
- Dépendances: T-008; DDD-ADR-010.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_experiment_retention_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_experiment_retention_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m011_specification.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m011): couvrir conservation resultats negatifs`
- Commit GREEN: `feat(m011): conserver resultats negatifs echecs`
