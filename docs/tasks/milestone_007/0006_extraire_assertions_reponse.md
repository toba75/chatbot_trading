# T-006 - Extraire les assertions importantes du brouillon de réponse

## Milestone
- Nom: M-007 - Réponse documentaire vérifiée.
- Source: plan M-007 et spécification v4.1, section RA `Answer`, `AnswerAssertion`, `AssertionOrigin`, générateur et extracteur d'assertions.
- Objectif métier: transformer un brouillon en assertions vérifiables avant toute publication.

## Contexte DDD
- Domaine: recherche et réponse vérifiée.
- Bounded context: RA.
- Objectif métier: distinguer contenu de source, déduction et choix de conception dans un brouillon de réponse.
- Langage ubiquitaire: `Answer`, `AnswerDraft`, `AnswerAssertion`, `AssertionOrigin`, `DraftAnswer`, `ExtractAnswerAssertions`, `AnswerAssertionExtractor`.
- Invariants critiques: une assertion factuelle importante doit être extraite et vérifiée; un brouillon n'est pas une réponse publiée; une origine d'assertion est obligatoire.
- Garde-fous: aucune auto-approbation par le générateur; aucune assertion composite non testable; aucun prompt ou brouillon interne publié comme contrat.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-004 terminé; T-005 peut être terminé pour enrichir les contradictions, mais T-006 ne publie pas encore.
- Présence des milestones amont dans master: M-006 présent.
- Décisions manquantes: aucune si le générateur reste derrière un port; ADR requise si un fournisseur LLM durable ou une politique de prompt structurante est figé.
- Risques: confondre JSON valide et vérité; laisser une assertion importante non extraite; perdre la distinction entre source et déduction.

## Tâches
### T-006 - Extraire les assertions importantes du brouillon de réponse
- But métier: préparer la vérification de réponse en rendant chaque assertion importante observable.
- Portée DDD: agrégat `Answer`, objets-valeur `AnswerAssertion` et `AssertionOrigin`, ports `AnswerGenerator` et `AnswerAssertionExtractor`, commandes `DraftAnswer` et `ExtractAnswerAssertions`, événement `AnswerDrafted`.
- Scénario BDD:
  - Given un jeu de preuves scellé et un brouillon contenant deux assertions factuelles et une déduction.
  - When RA extrait les assertions importantes.
  - Then les assertions deviennent atomiques, portent leur origine, et aucune n'est marquée supportée avant évaluation.
- Tests d'acceptation à écrire: `tests/m007/validate_answer_assertion_extraction_acceptance.ps1`, qui échoue tant que RA ne sépare pas brouillon, assertions et origines.
- Tests unitaires à écrire: tests pour brouillon vide, assertion composite, origine absente, assertion factuelle non extraite, déduction sans prémisses, mutation d'une version de brouillon publiée et tentative du générateur de fixer le statut final.
- Implémentation attendue: ajouter le modèle `Answer`, le port de génération, l'extracteur déterministe local, le repository mémoire et les règles d'atomicité des assertions RA.
- Invariants et garde-fous: aucun statut `SUPPORTED` en sortie de génération; aucune assertion importante sans origine; aucun brouillon final immuable avant publication; aucun fallback si l'extracteur ne couvre pas une assertion.
- Dépendances: T-004; T-005 recommandé; `EvidenceSet` scellé; `AnswerGenerator` via port.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m007\validate_answer_assertion_extraction_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m007\validate_answer_assertion_extraction_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m007): couvrir extraction assertions reponse`
- Commit GREEN: `feat(m007): extraire assertions reponse`

