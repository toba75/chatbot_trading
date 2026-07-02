# T-004 - Collecter des preuves multi-requêtes diversifiées

## Milestone
- Nom: M-009 - Recherche approfondie multi-sources.
- Source: spécification v4.1 sections 8 et 12, plan M-009, et spécification M-009 publiée par T-002.
- Objectif métier: collecter des preuves candidates par sous-question sans laisser un document ou une famille de sources dominer la synthèse.

## Contexte DDD
- Domaine: recherche et réponse vérifiée approfondie.
- Bounded context: RA, consommant KA par port publié.
- Objectif métier: assembler un pool de preuves traçables, diversifiées et rattachées aux obligations de couverture du plan approfondi.
- Langage ubiquitaire: preuve candidate, sous-requête, obligation couverte, diversité documentaire, version de projection, `EvidenceSet`, preuve favorable, preuve défavorable, source primaire, source secondaire.
- Invariants critiques: RA ne lit pas Qdrant directement; chaque preuve candidate porte un `SourceLocator`; chaque obligation demandée doit être couverte ou déclarée manquante; une preuve dupliquée ou un localisateur dupliqué est refusé.
- Garde-fous: aucun accès à collection Qdrant; aucun résultat sans version de projection; aucune collecte au-delà du `result_limit`; aucune domination silencieuse d'un seul document.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-003 terminé.
- Présence des milestones amont dans master: M-008 présent.
- Décisions manquantes: aucune si le port KA existant reste la frontière; ADR requise si RA devait piloter une nouvelle technologie de recherche au lieu de consommer KA.
- Risques: réutiliser l'assembleur M-007 sans modèle multi-requêtes; considérer le rang de recherche comme preuve; perdre les versions KA nécessaires à l'audit.

## Tâches
### T-004 - Collecter des preuves multi-requêtes diversifiées
- But métier: constituer un ensemble de preuves approfondi qui couvre le plan sans dépendre d'un seul document ou d'un ordre de callbacks.
- Portée DDD: requêtes KA par sous-question, `CandidateEvidence` enrichi par obligation, version de projection, contraintes de diversité, assemblage RA, événements de collecte et statut d'insuffisance quand la couverture échoue.
- Scénario BDD:
  - Given un plan approfondi contient trois sous-questions et des obligations de couverture.
  - When RA collecte les preuves candidates auprès de KA.
  - Then chaque obligation satisfaite référence au moins une preuve traçable et aucun document ne domine automatiquement l'EvidenceSet.
- Tests d'acceptation à écrire: `tests/m009/validate_multi_query_evidence_collection_acceptance.ps1`, qui échoue tant que RA ne collecte pas par sous-question avec diversité et versions de projection.
- Tests unitaires à écrire: tests de `CollectDeepResearchEvidenceHandler` pour requête sans sous-question, candidat sans `SourceLocator`, projection version absente, preuve dupliquée, dépassement `result_limit`, domination documentaire, obligation non couverte et ordre de callbacks permuté.
- Implémentation attendue: étendre ou créer un handler RA de collecte approfondie distinct du flux M-007, enrichir les requêtes vers `KnowledgeSearch`, enregistrer les versions de projection dans le résultat RA et conserver le comportement M-007 inchangé.
- Invariants et garde-fous: pas d'accès direct à KA interne; pas de consensus par volume de passages; pas de fallback mono-requête; pas de preuve sans provenance résolvable.
- Dépendances: T-003; `app/research_answering/application/collect_evidence.py`; `app/research_answering/domain/evidence_set.py`; contrats KA publiés par M-005.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_multi_query_evidence_collection_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_multi_query_evidence_collection_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m007\validate_evidence_set_sealing_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`.
- Commit RED: `test(m009): couvrir collecte multi sources`
- Commit GREEN: `feat(m009): collecter preuves multi sources`
