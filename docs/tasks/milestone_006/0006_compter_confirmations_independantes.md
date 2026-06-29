# T-006 - Compter les confirmations indépendantes

## Milestone
- Nom: M-006 - Claims vérifiables.
- Source: plan M-006 et spécification v4.1, agrégat `DependencyGroup` et règle d'indépendance des sources.
- Objectif métier: distinguer le nombre de mentions documentaires du nombre de confirmations réellement indépendantes.

## Contexte DDD
- Domaine: gouvernance des preuves.
- Bounded context: EG.
- Objectif métier: éviter qu'une même étude reprise par plusieurs documents soit comptée comme plusieurs preuves indépendantes.
- Langage ubiquitaire: `DependencyGroup`, `SourceIndependencePolicy`, `AssignClaimDependencyGroup`, confirmation indépendante, étude primaire, reprise secondaire.
- Invariants critiques: une source secondaire citant l'étude primaire ne compte pas comme confirmation indépendante; un groupe de dépendance est explicite; le comptage ne déduit rien par défaut.
- Garde-fous: pas de regroupement implicite par titre proche; pas de confirmation indépendante sans groupe documenté; pas de modification silencieuse d'un groupe déjà utilisé par un claim vérifié.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-005 attendue GREEN.
- Présence des milestones amont dans master: M-004 et M-005 requis et présents.
- Décisions manquantes: aucune si le regroupement reste une décision EG explicite; ADR requise si un moteur graphe durable est choisi.
- Risques: surcompter les preuves; perdre la traçabilité des reprises; mélanger pertinence documentaire et indépendance empirique.

## Tâches
### T-006 - Compter les confirmations indépendantes
- But métier: rendre auditable le niveau de support d'un claim sans gonfler artificiellement les confirmations.
- Portée DDD: agrégat `DependencyGroup`, commande `AssignClaimDependencyGroup`, politique `SourceIndependencePolicy`, requête `CountIndependentSupport`.
- Scénario BDD:
  - Given trois documents rattachés au même `DependencyGroup`.
  - When le nombre de confirmations indépendantes est calculé.
  - Then une seule confirmation indépendante est comptabilisée.
- Tests d'acceptation à écrire: `tests/m006/validate_dependency_group_acceptance.ps1`, couvrant reprises d'une même étude, groupes distincts et comptage par claim.
- Tests unitaires à écrire: tests de création de groupe, affectation explicite, doublon de groupe, document sans groupe, groupe modifié après vérification et agrégation des compteurs.
- Implémentation attendue: créer `DependencyGroup`, repository associé, handler `AnalyzeSourceDependencyHandler` ou `AssignClaimDependencyGroup`, et service de comptage indépendant exposé au contexte EG.
- Invariants et garde-fous: aucun groupe par défaut; aucun regroupement silencieux; aucune suppression d'une dépendance liée à un claim vérifié.
- Dépendances: T-005; ADR-006; DDD-ADR-005; DDD-ADR-010.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m006\validate_dependency_group_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m006\validate_dependency_group_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m006): couvrir confirmations independantes`
- Commit GREEN: `feat(m006): compter confirmations independantes`
