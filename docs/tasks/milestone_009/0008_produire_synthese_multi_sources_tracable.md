# T-008 - Produire une synthèse multi-sources traçable

## Milestone
- Nom: M-009 - Recherche approfondie multi-sources.
- Source: spécification v4.1 section 8 `Synthèse multi-sources`, processus de recherche approfondie section 12, et spécification M-009 publiée par T-002.
- Objectif métier: publier une réponse approfondie qui distingue clairement sources, déductions, conditions, limites, contradictions et incertitude.

## Contexte DDD
- Domaine: recherche et réponse vérifiée approfondie.
- Bounded context: RA.
- Objectif métier: transformer un EvidenceSet approfondi en synthèse utile sans perdre les nuances des études.
- Langage ubiquitaire: synthèse multi-sources, mandat retenu, périmètre documentaire, méthodes identifiées, conditions d'application, preuves favorables, preuves défavorables, niveau de preuve, dépendances, contradictions, limites, zones non documentées, conclusion, incertitude.
- Invariants critiques: chaque assertion factuelle importante est citée; source, déduction et choix de conception sont distingués; une fréquence élevée de mention n'est pas consensus; un paramètre non justifié est interdit; un échec du LLM de rédaction ne détruit pas le `ResearchCase`, le plan ni l'`EvidenceSet` scellé.
- Garde-fous: aucun brouillon publié sans vérification; aucune conclusion qui efface les preuves défavorables; aucune règle de stratégie générée en M-009; aucune donnée actuelle inventée; aucun fallback vers une réponse simple après échec de rédaction.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-005 à T-007 terminées.
- Présence des milestones amont dans master: M-008 présent.
- Décisions manquantes: aucune si le contrat `VerifiedResearchOutcome` reste compatible; ADR requise si la synthèse approfondie change le contrat public publié par M-001.
- Risques: transformer la synthèse en stratégie candidate; publier des paragraphes non structurés impossibles à vérifier; mélanger interprétation et source; perdre le cas de recherche ou relancer silencieusement une recherche après échec du générateur.

## Tâches
### T-008 - Produire une synthèse multi-sources traçable
- But métier: obtenir une réponse approfondie vérifiée, citée et nuancée.
- Portée DDD: `DeepResearchReport`, génération de brouillon structuré, conservation du `ResearchCase` en cas d'échec de rédaction, extraction des assertions, origine des assertions, vérification finale, citations ouvrables, statut `SUPPORTED`, `PARTIALLY_SUPPORTED`, `INSUFFICIENT_EVIDENCE` ou `CONFLICTING_EVIDENCE`.
- Scénario BDD:
  - Given un EvidenceSet approfondi contient preuves favorables, preuves défavorables, dépendances et contradictions qualifiées.
  - When RA produit la synthèse multi-sources.
  - Then la réponse finale expose mandat, périmètre, méthodes, conditions, preuves, dépendances, contradictions, limites, zones non documentées et conclusion avec citations ouvrables.
- Tests d'acceptation à écrire: `tests/m009/validate_multi_source_synthesis_acceptance.ps1`, qui échoue tant que la synthèse approfondie ne respecte pas la structure obligatoire et la vérification des assertions.
- Tests unitaires à écrire: tests de structure obligatoire, citation absente, assertion non supportée, origine implicite, preuve défavorable omise, contradiction omise, paramètre de stratégie inventé, dépendance absente, zone non documentée absente, brouillon publié sans vérification, générateur en échec et conservation du `ResearchCase`, du plan et de l'`EvidenceSet` scellé.
- Implémentation attendue: créer les objets de rapport RA nécessaires, étendre le flux de brouillon et vérification sans modifier le DTO M-007 de façon incompatible, produire une version finale immuable et conserver les citations ouvrables; si le générateur échoue, enregistrer un statut ou événement explicite non terminal pour la publication et conserver les artefacts de recherche déjà scellés sans relance silencieuse.
- Invariants et garde-fous: assertion importante vérifiée; distinction source/déduction/conception; aucune stratégie candidate en sortie; aucune synthèse supportée sans EvidenceSet scellé; aucun échec LLM ne supprime ni ne remplace silencieusement le cas de recherche.
- Dépendances: T-005; T-006; T-007; `app/research_answering/domain/answer.py`; `app/research_answering/application/draft_answer.py`; `app/research_answering/application/verify_answer.py`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_multi_source_synthesis_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_multi_source_synthesis_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m007\validate_answer_support_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`.
- Commit RED: `test(m009): couvrir synthese multi sources`
- Commit GREEN: `feat(m009): produire synthese multi sources`
