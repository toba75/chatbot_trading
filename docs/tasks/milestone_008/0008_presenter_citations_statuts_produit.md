# T-008 - Présenter citations et statuts dans la réponse produit

## Milestone
- Nom: M-008 - Conversation produit.
- Source: spécification M-008, format d'une réponse de chat et critères V1 sur citations ouvrables et statut documentaire visible.
- Objectif métier: rendre le résultat conversationnel inspectable par l'utilisateur sans masquer support, lacunes ou abstention.

## Contexte DDD
- Domaine: conversation produit fondée sur preuves.
- Bounded context: CV.
- Objectif métier: produire une vue de tour assistant qui distingue réponse principale, citations, statut documentaire, contradictions, lacunes et hypothèses.
- Langage ubiquitaire: réponse conversationnelle citée, résultat documentaire public RA, statut documentaire, citation ouvrable, hypothèse manquante, source, déduction, choix de conception, vue produit.
- Invariants critiques: chaque réponse factuelle affichable porte son `SupportStatus`; les citations restent des références ouvrables; les lacunes et contradictions RA ne sont pas supprimées; la présentation ne transforme pas une abstention en réponse supportée.
- Garde-fous: aucun payload RA interne exposé; aucun prompt, brouillon ou texte documentaire complet dans la vue produit; aucune reformulation qui change le statut; aucune lecture des citations depuis des champs absents de `VerifiedResearchOutcome`.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-007 terminé.
- Présence des milestones amont dans master: M-007 présent.
- Décisions manquantes: ADR requise si un design system ou un format public durable de présentation devient structurant; non requise pour un DTO produit minimal.
- Risques: perdre les citations dans la couche produit; cacher une contradiction pour améliorer l'expérience; confondre absence de preuve et réponse courte.

## Tâches
### T-008 - Présenter citations et statuts dans la réponse produit
- But métier: permettre à l'utilisateur d'évaluer immédiatement le niveau de preuve d'un tour assistant.
- Portée DDD: projection de lecture CV pour tour assistant, DTO produit, mapping strict depuis le DTO de résultat documentaire public RA qui contient `VerifiedResearchOutcome` plus texte et citations séparés.
- Scénario BDD:
  - Given un tour assistant référence une réponse RA `PARTIALLY_SUPPORTED` avec une citation et une lacune.
  - When la réponse produit du tour est construite.
  - Then le statut, la citation ouvrable et la lacune sont visibles sans publier de prompt ni de stockage interne.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue tant que le statut documentaire et les citations ne sont pas exposés.
- Tests unitaires à écrire: tests de mapping `SUPPORTED`, `PARTIALLY_SUPPORTED`, `INSUFFICIENT_EVIDENCE`, `CONFLICTING_EVIDENCE`, `REQUIRES_CURRENT_DATA`, citation non ouvrable dans le DTO public RA, lacune manquante, contradiction manquante, absence de payload sensible et refus d'un DTO qui attendrait `citations` dans `VerifiedResearchOutcome`.
- Implémentation attendue: créer `app/conversation/application/present_conversation_answer.py` et les DTO publics de réponse conversationnelle.
- Invariants et garde-fous: aucun statut réinterprété; aucune citation retirée silencieusement; aucune fuite de prompt; aucune preuve complète dupliquée dans CV; aucun changement implicite du contrat `VerifiedResearchOutcome`.
- Dépendances: T-007; DTO de résultat documentaire public RA; `VerifiedResearchOutcome`; `SourceLocator`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m008): couvrir presentation citations statuts`
- Commit GREEN: `feat(m008): presenter citations statuts produit`
