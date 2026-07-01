# T-007 - Revalider une assertion historique et rattacher la réponse

## Milestone
- Nom: M-008 - Conversation produit.
- Source: spécification M-008, scénario `l'historique n'est pas une preuve`, commande `AttachVerifiedAnswerToTurn` et intégration RA M-007.
- Objectif métier: réutiliser une affirmation conversationnelle seulement après revalidation RA, puis exposer la réponse documentaire vérifiée dans le fil de conversation sans donner à CV la propriété de la preuve.

## Contexte DDD
- Domaine: conversation produit fondée sur preuves.
- Bounded context: CV, avec RA comme fournisseur de résultat documentaire public.
- Objectif métier: revalider une assertion reprise depuis l'historique lorsqu'elle ne référence pas de `VerifiedAnswerVersion`, puis associer le résultat RA à un tour assistant traçable.
- Langage ubiquitaire: tour assistant, `VerifiedResearchOutcome`, résultat documentaire public RA, `VerifiedAnswerVersion`, `SupportStatus`, citation ouvrable, `VerifiedResultReusePolicy`, `ResearchFacade`, `VerifiedAnswerAttachedToTurn`.
- Invariants critiques: CV référence le résultat RA sans le modifier; une réponse factuelle attachée porte un statut documentaire; une citation absente ou non ouvrable reste une responsabilité RA; le tour conserve la corrélation avec la question résolue; une assertion historique sans `VerifiedAnswerVersion` est recherchée et vérifiée à nouveau par RA avant usage.
- Garde-fous: aucun accès direct à `AnswerRepository`; aucune réécriture de `VerifiedResearchOutcome`; aucune publication conversationnelle sans statut RA; aucun ajout silencieux de `answer_text` ou `citations` au contrat publié `VerifiedResearchOutcome`.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-006 terminé.
- Présence des milestones amont dans master: M-007 présent.
- Décisions manquantes: aucune si CV consomme un DTO de résultat documentaire public RA composé du contrat `VerifiedResearchOutcome` et des champs publics RA de réponse, notamment texte et citations; ADR requise si le contrat `VerifiedResearchOutcome` change.
- Risques: recopier la réponse RA comme vérité CV; perdre l'identifiant de version vérifiée; attacher un résultat partiel sans statut explicite; considérer une assertion historique comme preuve; inventer des champs dans `VerifiedResearchOutcome`.

## Tâches
### T-007 - Revalider une assertion historique et rattacher la réponse
- But métier: faire apparaître les réponses vérifiées dans la conversation tout en conservant RA comme source du résultat documentaire et en empêchant l'historique de devenir une preuve.
- Portée DDD: politique `VerifiedResultReusePolicy`, port `ResearchFacade`, DTO CV de résultat documentaire public RA, orchestration d'un tour documentaire, commande `AttachVerifiedAnswerToTurn`, événement `VerifiedAnswerAttachedToTurn` et statut de résultat du tour.
- Scénario BDD:
  - Given une réponse précédente contient une assertion sans `VerifiedAnswerVersion`.
  - When l'utilisateur réutilise cette assertion dans un nouveau tour documentaire.
  - Then CV appelle `ResearchFacade` pour rechercher et vérifier à nouveau l'assertion avant de rattacher le résultat public RA au tour.
- Tests d'acceptation à écrire: `tests/m008/validate_verified_result_reuse_acceptance.ps1`, qui échoue tant qu'une assertion historique sans `VerifiedAnswerVersion` peut être utilisée sans nouvelle vérification RA.
- Tests unitaires à écrire: tests de résultat RA invalide, statut absent, citation absente du DTO public RA, rattachement à un tour inexistant, double rattachement, corrélation question-réponse, assertion historique sans version vérifiée, assertion historique avec version vérifiée et absence d'import d'adaptateur RA interne.
- Implémentation attendue: créer `app/conversation/application/answer_conversation_turn.py`, `app/conversation/application/attach_verified_answer.py`, `app/conversation/application/reuse_verified_result.py` et les ports CV vers RA; définir côté CV un DTO d'intégration qui référence `VerifiedResearchOutcome` et transporte séparément les champs publics RA nécessaires à la présentation, notamment texte et citations.
- Invariants et garde-fous: aucune mutation RA; aucune preuve possédée par CV; aucun statut inventé par CV; aucun rattachement sans question résolue; aucune assertion historique non versionnée utilisée sans revalidation; aucune extension silencieuse de `VerifiedResearchOutcome`.
- Dépendances: T-006; `app/research_answering/application/answer_question.py`; `app/contracts/research_outcomes.py`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_verified_result_reuse_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_verified_answer_attachment_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_architecture_boundaries.ps1 -AppRoot .\app -ContextRegistryPath .\app\context_registry.json -SpecificationPath .\docs\specs\m001_frontieres_ddd_contrats_publies.md`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`.
- Commit RED: `test(m008): couvrir revalidation historique`
- Commit GREEN: `feat(m008): revalider historique et rattacher reponse`
