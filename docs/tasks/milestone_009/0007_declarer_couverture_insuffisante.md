# T-007 - Déclarer la couverture insuffisante avec statut explicite

## Milestone
- Nom: M-009 - Recherche approfondie multi-sources.
- Source: spécification v4.1 sections 8, 12 et 21, plan M-009, et spécification M-009 publiée par T-002.
- Objectif métier: produire un résultat explicite lorsque la couverture documentaire ne suffit pas à répondre.

## Contexte DDD
- Domaine: recherche et réponse vérifiée approfondie.
- Bounded context: RA.
- Objectif métier: empêcher une synthèse supportée quand des obligations de couverture critiques restent non satisfaites.
- Langage ubiquitaire: obligation manquante, `KnowledgeGap`, couverture insuffisante, `INSUFFICIENT_EVIDENCE`, abstention, preuve défavorable absente, source primaire absente, zone non documentée.
- Invariants critiques: une obligation critique manquante produit un statut explicite; les lacunes sont rattachées aux obligations; l'abstention est un résultat valide; aucun texte ne comble silencieusement une lacune documentaire.
- Garde-fous: aucun `SUPPORTED` avec obligation critique non couverte; aucune phrase de synthèse inventée pour masquer une absence de preuve; aucune lacune sans raison publique.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-004 à T-006 terminées.
- Présence des milestones amont dans master: M-008 présent.
- Décisions manquantes: aucune si les statuts RA existants sont conservés; ADR requise si un nouveau statut public remplace le contrat `SupportStatus`.
- Risques: qualifier une recherche comme partiellement supportée sans expliquer les obligations manquantes; mélanger absence de données actuelles et absence de couverture documentaire.

## Tâches
### T-007 - Déclarer la couverture insuffisante avec statut explicite
- But métier: rendre les limites de couverture visibles et auditables.
- Portée DDD: politique `EvidenceCoveragePolicy` approfondie, `KnowledgeGap`, transition terminale `INSUFFICIENT_EVIDENCE`, raison publique, conservation des obligations manquantes et blocage de publication supportée.
- Scénario BDD:
  - Given un plan approfondi exige des preuves défavorables et des sources primaires.
  - When la collecte ne couvre que des sources secondaires favorables.
  - Then RA publie `INSUFFICIENT_EVIDENCE` avec les obligations manquantes au lieu de produire une conclusion supportée.
- Tests d'acceptation à écrire: `tests/m009/validate_insufficient_deep_coverage_acceptance.ps1`, qui échoue tant que les obligations critiques manquantes ne produisent pas un statut explicite.
- Tests unitaires à écrire: tests de politique pour obligation critique manquante, obligation non critique qualifiée, absence de preuve défavorable, source primaire absente, donnée actuelle requise séparée, lacune dupliquée et raison publique absente.
- Implémentation attendue: étendre la politique de couverture RA, enrichir les événements `KnowledgeGapRecorded` et `ResearchEvidenceFoundInsufficient` si nécessaire, et exposer les lacunes dans les résultats approfondis sans changer le sens de M-007.
- Invariants et garde-fous: pas de statut supporté sans couverture; pas de fallback vers réponse simple; pas de confusion `CURRENT_DATA_REQUIRED`; pas de lacune non traçable.
- Dépendances: T-004; T-006; `app/research_answering/domain/evidence_set.py`; `app/research_answering/domain/research_case.py`; `app/research_answering/domain/contradiction_assessment.py`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_insufficient_deep_coverage_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_insufficient_deep_coverage_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m007\validate_current_data_abstention_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`.
- Commit RED: `test(m009): couvrir couverture insuffisante`
- Commit GREEN: `feat(m009): declarer couverture insuffisante`
