# T-005 - Classer les contradictions et lacunes documentaires

## Milestone
- Nom: M-007 - Réponse documentaire vérifiée.
- Source: plan M-007 et spécification v4.1, section RA `ContradictionAssessment`, `KnowledgeGap`, statuts `INSUFFICIENT_EVIDENCE` et `CONFLICTING_EVIDENCE`.
- Objectif métier: rendre les contradictions et lacunes visibles avant qu'une réponse ne puisse être publiée.

## Contexte DDD
- Domaine: recherche et réponse vérifiée.
- Bounded context: RA, s'appuyant sur les relations de claims EG.
- Objectif métier: qualifier les oppositions, les horizons différents et les absences de preuve sans simplifier abusivement la conclusion.
- Langage ubiquitaire: `ContradictionAssessment`, `KnowledgeGap`, `SupportStatus`, `ContradictionClassificationPolicy`, `RecordContradictionAssessment`, `DeclareInsufficientEvidence`, `DeclareConflictingEvidence`.
- Invariants critiques: une contradiction pertinente ne peut pas être omise; une lacune de couverture produit un statut explicite; une opposition d'horizon n'est pas généralisée en contradiction absolue.
- Garde-fous: aucune conclusion nette si le jeu de preuves est conflictuel; aucun consensus par nombre brut de mentions; aucune fusion silencieuse de portées différentes.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-004 terminé.
- Présence des milestones amont dans master: M-006 présent, notamment relations de claims après comparaison de portée.
- Décisions manquantes: aucune si la classification reste une politique RA; ADR requise si un nouveau moteur de graphe de contradictions est choisi.
- Risques: masquer des contradictions pour produire une réponse plus agréable; ignorer une obligation de couverture non satisfaite; confondre conflit documentaire et absence de preuve.

## Tâches
### T-005 - Classer les contradictions et lacunes documentaires
- But métier: décider si RA peut synthétiser, doit signaler un conflit ou doit conclure à une preuve insuffisante.
- Portée DDD: objets-valeur `ContradictionAssessment` et `KnowledgeGap`, politique `ContradictionClassificationPolicy`, commandes `RecordContradictionAssessment`, `DeclareInsufficientEvidence` et `DeclareConflictingEvidence`, événements `ContradictionDetected`, `KnowledgeGapRecorded`, `ResearchEvidenceFoundInsufficient` et `ResearchEvidenceFoundConflicting`.
- Scénario BDD:
  - Given deux claims opposés portent sur des horizons différents.
  - When RA analyse les contradictions du jeu de preuves scellé.
  - Then la relation est classée `DIFFERENT_HORIZON`, la réponse future doit l'expliquer, et aucun statut `SUPPORTED` général n'est autorisé par simplification.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue tant que RA ne classe pas les contradictions conditionnelles et lacunes avant réponse.
- Tests unitaires à écrire: tests pour conflit non enregistré, horizon différent, métrique différente, lacune d'obligation, preuves insuffisantes, consensus par fréquence interdit, contradiction résolue par qualification, transition vers `CONFLICTING_EVIDENCE`, événement `ResearchEvidenceFoundInsufficient` et événement `ResearchEvidenceFoundConflicting`.
- Implémentation attendue: ajouter le classificateur de contradictions RA, les raisons publiques de lacune, l'enregistrement dans `ResearchCase` et les événements associés, y compris les événements de décision finale d'insuffisance ou de conflit.
- Invariants et garde-fous: aucune contradiction pertinente omise; aucune généralisation abusive; aucune obligation de couverture ignorée; aucune décision par score ou nombre de citations.
- Dépendances: T-004; relations EG M-006; `VerifiedClaimRef`; `EvidenceSet` scellé.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m007): couvrir contradictions lacunes reponse`
- Commit GREEN: `feat(m007): classer contradictions lacunes reponse`
