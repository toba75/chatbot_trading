# T-006 - Sélectionner un mode conversationnel visible et justifié

## Milestone
- Nom: M-008 - Conversation produit.
- Source: spécification M-008, politique `ConversationModeRoutingPolicy` et commande `SelectConversationMode`.
- Objectif métier: choisir explicitement le mode de traitement d'une demande utilisateur sans repli silencieux.

## Contexte DDD
- Domaine: conversation produit fondée sur preuves.
- Bounded context: CV.
- Objectif métier: rendre visible si un tour relève du documentaire, de l'approfondi, de la comparaison, de la stratégie, du calcul, du backtest ou de la clarification.
- Langage ubiquitaire: mode conversationnel, `CHAT_DOCUMENTAIRE`, `RECHERCHE_APPROFONDIE`, `COMPARAISON`, `CONCEPTION_STRATEGIE`, `CALCUL`, `BACKTEST`, `CLARIFICATION_INTERNE`, justification de routage, `ConversationModeSelected`.
- Invariants critiques: le mode sélectionné et sa justification sont enregistrés dans le tour; un mode indisponible n'est pas remplacé silencieusement; l'utilisateur peut forcer un mode autorisé; CV ne modifie pas les agrégats RA, SD ou EX.
- Garde-fous: aucun fallback vers documentaire; aucun mode par défaut implicite; aucune exécution de stratégie ou de backtest avant les milestones dédiés.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-005 terminé.
- Présence des milestones amont dans master: M-007 présent.
- Décisions manquantes: ADR requise si les modes publics ou leur compatibilité deviennent un contrat externe durable différent de la spécification.
- Risques: router par mots-clés sans justification; traiter un backtest comme une réponse documentaire; masquer l'indisponibilité des modes M-009 à M-011.

## Tâches
### T-006 - Sélectionner un mode conversationnel visible et justifié
- But métier: éviter qu'une demande produit soit exécutée dans le mauvais mode sans signal utilisateur.
- Portée DDD: politique de routage CV, port `ModeClassifier`, commande `SelectConversationMode`, événement `ConversationModeSelected`, erreur publique de mode indisponible et justification synthétique.
- Scénario BDD:
  - Given une question autonome demande de tester une stratégie avec des coûts doublés.
  - When le mode conversationnel est sélectionné.
  - Then le tour enregistre `BACKTEST` avec une justification et ne bascule pas silencieusement vers `CHAT_DOCUMENTAIRE`.
- Tests d'acceptation à écrire: `tests/m008/validate_conversation_mode_routing_acceptance.ps1`, qui échoue tant que les modes documentaire, approfondi, stratégie, calcul, backtest et clarification ne sont pas distingués.
- Tests unitaires à écrire: tests de mode forcé valide, mode forcé interdit, justification absente, mode indisponible, classement comparaison versus approfondi, classement calcul versus backtest et absence de fallback.
- Implémentation attendue: créer `app/conversation/domain/mode_routing.py`, `app/conversation/application/select_mode.py` et un classificateur déterministe local pour les scénarios M-008.
- Invariants et garde-fous: aucun mode implicite; aucune mutation hors CV; aucune exécution d'un contexte aval absent; aucune justification vide.
- Dépendances: T-005; contrats RA publiés; futurs ports `StrategyFacade` et `ExperimentFacade` déclarés mais non exécutés sans disponibilité explicite.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_conversation_mode_routing_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_conversation_mode_routing_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m008): couvrir routage modes conversation`
- Commit GREEN: `feat(m008): selectionner modes conversation justifies`

