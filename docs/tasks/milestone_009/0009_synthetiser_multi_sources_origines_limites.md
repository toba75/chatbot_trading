# T-009 - Synthétiser multi-sources avec origines et limites

## Milestone
- Nom: M-009 - Recherche approfondie multi-sources.
- Source: plan M-009 et spécification v4.1 phase synthèse multi-sources.
- Objectif métier: produire une synthèse approfondie qui expose mandat, périmètre, preuves favorables, preuves défavorables, contradictions, limites et incertitude.

## Contexte DDD
- Domaine: recherche et réponse vérifiée approfondie.
- Bounded context: RA.
- Objectif métier: transformer un jeu de preuves scellé et des contradictions classées en réponse vérifiée sans effacer les nuances.
- Langage ubiquitaire: synthèse multi-sources, `AnswerDraft`, `AnswerAssertion`, `AssertionOrigin`, preuve favorable, preuve défavorable, limite, conclusion incertaine.
- Invariants critiques: source, déduction et choix de conception sont distingués; chaque assertion importante est vérifiée; une contradiction pertinente reste visible dans la réponse.
- Garde-fous: le LLM ne décide pas le statut documentaire; aucune assertion non supportée ne devient factuelle; aucune section obligatoire de synthèse n'est omise silencieusement.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-008 terminé.
- Présence des milestones amont dans master: M-007 et M-008 présents.
- Décisions manquantes: aucune si `AnswerGenerator` reste un port et `AnswerSupportPolicy` décide; ADR requise si une nouvelle structure publique remplace `VerifiedResearchOutcome`.
- Risques: publier une synthèse fluide mais invérifiable; confondre déduction et source; masquer le degré d'incertitude.

## Tâches
### T-009 - Synthétiser multi-sources avec origines et limites
- But métier: fournir une réponse approfondie exploitable sans perdre la provenance et les réserves.
- Portée DDD: `AnswerDraft`, structure obligatoire de synthèse, `AnswerAssertion`, `AssertionOrigin`, `AnswerSupportPolicy`, citations, contradictions, lacunes et version finale immuable.
- Scénario BDD:
  - Given un EvidenceSet scellé contient preuves favorables, preuves défavorables et une contradiction `DIFFERENT_HORIZON`.
  - When RA produit la synthèse multi-sources.
  - Then la réponse distingue contenu de source, déduction et limites, explique l'horizon différent et vérifie chaque assertion importante.
- Tests d'acceptation à écrire: `tests/m009/validate_multi_source_synthesis_acceptance.ps1`, qui échoue tant que la synthèse n'expose pas les sections obligatoires et l'origine des assertions.
- Tests unitaires à écrire: tests pour section obligatoire absente, assertion sans origine, preuve favorable absente, preuve défavorable absente, contradiction absente, limite absente, citation non ouvrable, assertion non supportée et version finale mutable.
- Implémentation attendue: étendre `app/research_answering/application/draft_answer.py`, `verify_answer.py` et le modèle `Answer` pour porter la structure de synthèse M-009, les origines d'assertions et les limites publiques.
- Invariants et garde-fous: aucune assertion importante non évaluée; aucune conclusion sans citations; aucune version finale mutable; aucun brouillon publié sans politique RA.
- Dépendances: T-007; T-008; `Answer`; `AnswerSupportPolicy`; `CitationIntegrityPolicy`; `VerifiedResearchOutcome`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_multi_source_synthesis_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_multi_source_synthesis_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m009): couvrir synthese multi sources`
- Commit GREEN: `feat(m009): synthetiser multi sources`

