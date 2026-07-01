# T-005 - Résoudre une référence de suivi en question autonome

## Milestone
- Nom: M-008 - Conversation produit.
- Source: scénario directeur M-008 et politique `ReferenceResolutionPolicy`.
- Objectif métier: transformer un message de suivi ambigu en question autonome avant toute recherche ou réponse.

## Contexte DDD
- Domaine: conversation produit fondée sur preuves.
- Bounded context: CV.
- Objectif métier: permettre les questions de suivi sans transmettre d'ambiguïté implicite à RA, SD ou EX.
- Langage ubiquitaire: question résolue, référence conversationnelle, `ReferenceResolutionPolicy`, `QuestionResolver`, ambiguïté, mandat actif, `FollowUpQuestionResolved`.
- Invariants critiques: une question de suivi est résolue avant d'être transmise à un autre contexte; une ambiguïté non résolue déclenche une clarification CV; les faits réutilisés sont référencés par résultat vérifié ou revalidés.
- Garde-fous: aucun passage direct de message ambigu vers RA; aucune résolution par défaut; aucune interprétation silencieuse d'un pronom ou d'un démonstratif.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-004 terminé.
- Présence des milestones amont dans master: M-007 présent.
- Décisions manquantes: aucune si le résolveur reste un port CV; ADR requise si un modèle externe devient obligatoire pour résoudre les références.
- Risques: résoudre par heuristique fragile sans signal d'ambiguïté; utiliser le texte historique comme preuve; envoyer le snapshot complet au LLM sans filtrage.

## Tâches
### T-005 - Résoudre une référence de suivi en question autonome
- But métier: rendre la conversation suivie exploitable par les contextes de recherche sans contexte implicite.
- Portée DDD: politique de résolution, port `QuestionResolver`, commande `ResolveFollowUpQuestion`, événement `FollowUpQuestionResolved` et statut de clarification.
- Scénario BDD:
  - Given une conversation portant sur le volatility targeting.
  - When l'utilisateur écrit `compare-la maintenant à Kelly`.
  - Then une question autonome mentionnant explicitement le volatility targeting et Kelly est produite avant tout appel à RA.
- Tests d'acceptation à écrire: `tests/m008/validate_followup_question_resolution_acceptance.ps1`, qui échoue tant que le scénario volatility targeting versus Kelly ne produit pas une question autonome.
- Tests unitaires à écrire: tests de pronoms ambigus, documents sélectionnés, mandat actif, référence vers réponse vérifiée, ambiguïté nécessitant clarification, refus de question résolue vide et absence d'appel RA avant résolution.
- Implémentation attendue: créer `app/conversation/application/resolve_followup_question.py`, une implémentation déterministe locale de `QuestionResolver` pour les cas de test, et les événements CV associés.
- Invariants et garde-fous: aucune question ambiguë transmise à RA; aucune résolution implicite sans justification; aucune preuve dérivée du texte historique seul.
- Dépendances: T-004; `ConversationContextSnapshot`; `VerifiedResearchOutcome`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_followup_question_resolution_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_followup_question_resolution_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m008): couvrir resolution reference suivi`
- Commit GREEN: `feat(m008): resoudre references en questions autonomes`

