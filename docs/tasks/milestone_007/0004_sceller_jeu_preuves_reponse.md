# T-004 - Sceller le jeu de preuves de réponse

## Milestone
- Nom: M-007 - Réponse documentaire vérifiée.
- Source: plan M-007 et spécification v4.1, section RA `EvidenceSet`, ports `KnowledgeSearch`, `VerifiedClaimCatalog` et assemblage de preuves.
- Objectif métier: assembler les preuves admissibles d'une réponse puis les figer avant rédaction.

## Contexte DDD
- Domaine: recherche et réponse vérifiée.
- Bounded context: RA, consommant KA et EG par ports publiés.
- Objectif métier: produire un jeu de preuves versionné, diversifié et citable pour un cas de recherche planifié.
- Langage ubiquitaire: `EvidenceSet`, `Citation`, `VerifiedClaimRef`, `EvidenceRef`, `SourceLocator`, `EvidenceCoveragePolicy`, `EvidenceDiversificationPolicy`, `SealEvidenceSet`.
- Invariants critiques: une réponse publiée référence un jeu de preuves figé; chaque preuve publique possède une citation ouvrable; RA ne lit ni Qdrant ni les tables EG.
- Garde-fous: aucun score de recherche traité comme vérité; aucune preuve sans `SourceLocator`; aucun jeu de preuves modifiable après scellement.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-003 terminé.
- Présence des milestones amont dans master: M-005 et M-006 présents via dépendance M-006.
- Décisions manquantes: aucune si KA et EG sont consommés par ports; ADR requise si RA devient propriétaire d'un stockage de preuves partagé.
- Risques: fuite de détail Qdrant; duplication de preuves non indépendante; citation impossible à ouvrir; ajout tardif de preuves après génération.

## Tâches
### T-004 - Sceller le jeu de preuves de réponse
- But métier: garantir que la réponse sera produite depuis un ensemble stable de preuves et claims vérifiés.
- Portée DDD: objet-valeur `EvidenceSet`, politiques `EvidenceCoveragePolicy` et `EvidenceDiversificationPolicy`, ports `KnowledgeSearch` et `VerifiedClaimCatalog`, commande `CollectEvidence`, commande `SealEvidenceSet` et événement `EvidenceSetSealed`.
- Scénario BDD:
  - Given un cas de recherche `PLANNED` et des preuves candidates KA avec claims EG vérifiés.
  - When RA collecte puis scelle le jeu de preuves.
  - Then le jeu de preuves devient immuable, versionné, et chaque citation pointe vers un `SourceLocator` ouvrable.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue tant que RA ne scelle pas un jeu de preuves versionné à partir des ports KA et EG.
- Tests unitaires à écrire: tests pour preuve sans `SourceLocator`, claim non vérifié, doublon de preuve, mutation après scellement, absence d'obligation couverte, accès direct Qdrant simulé, accès direct repository EG simulé et citation non résoluble.
- Implémentation attendue: ajouter l'assembleur de preuves RA, les ports applicatifs, le repository mémoire de cas, le modèle de `EvidenceSet` et les validations de citation.
- Invariants et garde-fous: aucun accès direct aux stockages d'autres contextes; aucun jeu de preuves vide pour une réponse factuelle; aucune modification après scellement; aucune preuve en quarantaine acceptée.
- Dépendances: T-003; `KnowledgeSearchPort` M-005; `VerifiedClaimRef` et API EG M-006; `SourceLocator` M-001/M-004.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m007): couvrir scellement jeu preuves reponse`
- Commit GREEN: `feat(m007): sceller jeu preuves reponse`
