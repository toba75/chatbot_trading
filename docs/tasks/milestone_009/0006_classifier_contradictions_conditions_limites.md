# T-006 - Classer les contradictions, conditions et limites

## Milestone
- Nom: M-009 - Recherche approfondie multi-sources.
- Source: spécification v4.1 sections 7, 8 et 12, plan M-009, et spécification M-009 publiée par T-002.
- Objectif métier: expliquer les convergences, compatibilités et oppositions documentaires selon leur portée réelle au lieu de produire une contradiction générale abusive ou un consensus implicite.

## Contexte DDD
- Domaine: analyse des contradictions et compatibilités.
- Bounded context: RA, à partir de relations EG déjà comparées.
- Objectif métier: classer convergences, contradictions réelles, contradictions apparentes, horizons différents, univers différents, métriques différentes, coûts différents, régimes différents et limites conditionnelles.
- Langage ubiquitaire: convergence, compatibilité, relation `SUPPORTS`, relation `QUALIFIES`, `ContradictionAssessment`, contradiction réelle, contradiction apparente, portée comparable, horizon, univers, métrique, fréquence, coûts, régime de marché, limite, qualification.
- Invariants critiques: une convergence doit reposer sur une relation positive explicite et une portée compatible; une relation `CONTRADICTS` exige une comparaison explicite de portée; une opposition non comparable devient qualification; une contradiction bloquante reste visible; une relation ne peut pas être classée par similarité textuelle seule.
- Garde-fous: aucune convergence transformée en consensus par fréquence; aucun conflit supprimé pour rendre la conclusion plus nette; aucun consensus par fréquence; aucune classification sans raison publique; aucun élargissement de portée.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-005 terminé.
- Présence des milestones amont dans master: M-008 présent.
- Décisions manquantes: aucune si les types ajoutés raffinent les politiques RA/EG existantes; ADR requise si la politique de relation des claims change de sens.
- Risques: ne tester que les oppositions et omettre les convergences; confondre conflit non résolu et différence d'horizon; ignorer coûts ou régime de marché; dupliquer les relations EG dans RA.

## Tâches
### T-006 - Classer les contradictions, conditions et limites
- But métier: rendre les convergences, compatibilités et contradictions approfondies explicites et actionnables dans la synthèse.
- Portée DDD: diagnostic des convergences et compatibilités positives, extension de `ContradictionClassificationPolicy`, diagnostic des limites, typologie M-009, conservation des dimensions comparées, événements `ContradictionDetected` et blocage explicite des conflits non résolus.
- Scénario BDD:
  - Given deux affirmations vérifiées se soutiennent sur un univers et un horizon compatibles, et deux autres affirmations opposées portent sur des horizons différents et des coûts de transaction distincts.
  - When l'analyse des contradictions est exécutée.
  - Then la convergence est conservée comme compatibilité positive rattachée aux claims vérifiés, et l'opposition est classée avec les raisons `DIFFERENT_HORIZON` et `DIFFERENT_COST_ASSUMPTION` sans contradiction générale.
- Tests d'acceptation à écrire: `tests/m009/validate_deep_contradiction_classification_acceptance.ps1`, qui échoue tant que les convergences compatibles et les contradictions M-009 ne conservent pas conditions, limites et raisons publiques.
- Tests unitaires à écrire: tests de classification pour relation positive `SUPPORTS` ou `QUALIFIES` avec portée compatible, convergence sans groupe de dépendance indépendant, `GENUINE_CONTRADICTION`, `APPARENT_CONTRADICTION`, `CONTEXT_DEPENDENT`, `DIFFERENT_HORIZON`, `DIFFERENT_UNIVERSE`, `DIFFERENT_METRIC`, `DIFFERENT_COST_ASSUMPTION`, `DIFFERENT_REGIME`, relation sans portée, base par similarité textuelle et conflit bloquant non qualifié.
- Implémentation attendue: étendre `app/evidence_governance/domain/claim_relation.py` si les dimensions de portée doivent être publiées par EG, étendre `app/research_answering/domain/contradiction_assessment.py` et `app/research_answering/application/classify_contradictions.py` pour exposer les compatibilités positives et contradictions sans mélanger les responsabilités EG/RA, puis préserver les tests M-007 existants.
- Invariants et garde-fous: convergence sans relation positive explicite refusée; contradiction sans comparaison refusée; conflit non résolu visible; raison publique obligatoire; aucune conclusion plus large que les claims comparés.
- Dépendances: T-005; `app/evidence_governance/domain/claim_relation.py`; `app/research_answering/domain/contradiction_assessment.py`; `tests/m007/validate_contradiction_gap_acceptance.ps1`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_deep_contradiction_classification_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_deep_contradiction_classification_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m007\validate_contradiction_gap_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`.
- Commit RED: `test(m009): couvrir contradictions conditionnelles`
- Commit GREEN: `feat(m009): classifier contradictions conditionnelles`
