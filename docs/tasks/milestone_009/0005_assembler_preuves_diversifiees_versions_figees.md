# T-005 - Assembler des preuves diversifiées et versionnées

## Milestone
- Nom: M-009 - Recherche approfondie multi-sources.
- Source: plan M-009 et spécification v4.1, sections diversification, couverture minimale et jeu de preuves figé.
- Objectif métier: empêcher qu'une seule source domine automatiquement la synthèse approfondie.

## Contexte DDD
- Domaine: recherche et réponse vérifiée approfondie.
- Bounded context: RA.
- Objectif métier: constituer un `EvidenceSet` multi-sources qui couvre le plan, conserve les versions documentaires et reste scellable avant synthèse.
- Langage ubiquitaire: `EvidenceSet`, diversification, source primaire, auteur indépendant, preuve favorable, preuve défavorable, version de projection.
- Invariants critiques: le `EvidenceSet` publié est versionné et figé; un seul document ne peut pas dominer automatiquement la synthèse; la couverture de chaque composant du plan est contrôlée.
- Garde-fous: aucun doublon de preuve; aucun `SourceLocator` non résoluble; aucun ajout de preuve après scellement; aucun seuil implicite.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-004 terminé.
- Présence des milestones amont dans master: M-004, M-005, M-006 et M-008 présents.
- Décisions manquantes: aucune si la diversification reste une politique RA locale; ADR requise si une stratégie durable de classement multi-objectifs est adoptée.
- Risques: confondre pertinence et diversité; accepter plusieurs passages du même document comme sources indépendantes; perdre les versions de projection.

## Tâches
### T-005 - Assembler des preuves diversifiées et versionnées
- But métier: fournir à la synthèse un jeu de preuves équilibré, traçable et scellé.
- Portée DDD: `EvidenceCoveragePolicy`, `EvidenceDiversificationPolicy`, candidates par obligation, limites par document, preuve favorable et défavorable, versions de projection et événement `EvidenceCollectionCompleted`.
- Scénario BDD:
  - Given plusieurs candidats couvrent la même obligation depuis un seul document.
  - When RA assemble les preuves de recherche approfondie.
  - Then l'assemblage refuse la domination d'un seul document ou enregistre une lacune explicite de diversité.
- Tests d'acceptation à écrire: `tests/m009/validate_diversified_evidence_set_acceptance.ps1`, qui échoue tant que RA accepte un EvidenceSet dominé par un seul document sans lacune.
- Tests unitaires à écrire: tests pour duplicat de preuve, duplicat de SourceLocator, version de projection absente, obligation non couverte, absence de preuve défavorable exigée, limite par document dépassée et scellement après mutation.
- Implémentation attendue: étendre `app/research_answering/domain/evidence_set.py` et `app/research_answering/application/collect_evidence.py` pour porter les règles M-009, les versions de projection et les diagnostics de diversification.
- Invariants et garde-fous: aucune preuve non traçable; aucune mutation après scellement; aucune diversité implicite; aucun consensus par volume brut de passages.
- Dépendances: T-004; `EvidenceSet`; `CandidateEvidence`; `SourceLocator`; versions KA M-005.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_diversified_evidence_set_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_diversified_evidence_set_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m009): couvrir preuves diversifiees`
- Commit GREEN: `feat(m009): assembler preuves diversifiees`

