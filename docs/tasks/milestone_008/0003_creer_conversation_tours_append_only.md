# T-003 - Créer les conversations et tours append-only

## Milestone
- Nom: M-008 - Conversation produit.
- Source: spécification M-008, agrégats `Conversation` et `ConversationTurn`, commandes `CreateConversation` et `AppendUserTurn`.
- Objectif métier: permettre à l'utilisateur de démarrer une conversation locale et d'ajouter des tours sans altérer l'historique.

## Contexte DDD
- Domaine: conversation produit fondée sur preuves.
- Bounded context: CV.
- Objectif métier: conserver une continuité interactionnelle fiable, consultable et append-only.
- Langage ubiquitaire: `Conversation`, `ConversationTurn`, conversation active, tour utilisateur, tour assistant, append-only, préférences, mandat par défaut, `ConversationCreated`, `UserTurnAppended`.
- Invariants critiques: chaque tour appartient à une conversation existante; un tour déjà enregistré n'est pas modifié; l'agrégat `Conversation` ne charge pas l'intégralité des tours; une conversation archivée ne reçoit plus de nouveau tour utilisateur.
- Garde-fous: aucun identifiant généré implicitement par défaut; aucune mutation rétroactive du message; aucune suppression cascade vers RA, EG, KA, SD ou EX.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 et T-002 terminés.
- Présence des milestones amont dans master: M-007 présent.
- Décisions manquantes: aucune pour un repository mémoire strict; ADR requise si une persistance durable ou une politique de purge est introduite au-delà de la spécification.
- Risques: créer un modèle de session générique sans invariants métier; stocker les tours dans `Conversation` au lieu de respecter le log append-only; accepter des tours sans conversation.

## Tâches
### T-003 - Créer les conversations et tours append-only
- But métier: donner au produit un fil conversationnel fiable et traçable.
- Portée DDD: agrégat `Conversation`, agrégat `ConversationTurn`, commandes de création et d'ajout, événements de domaine, repositories CV et adaptateurs mémoire stricts.
- Scénario BDD:
  - Given une conversation active existe pour un mandat documentaire.
  - When l'utilisateur ajoute un message dans cette conversation.
  - Then un nouveau tour append-only est créé avec son ordre, son horodatage et son appartenance à la conversation sans modifier les tours précédents.
- Tests d'acceptation à écrire: `tests/m008/validate_conversation_turn_append_only_acceptance.ps1`, qui échoue tant qu'une conversation ne peut pas recevoir un tour append-only vérifiable.
- Tests unitaires à écrire: tests de création de conversation, unicité d'identité, refus de tour sans conversation, refus de modification d'un tour enregistré, refus d'ajout dans une conversation archivée et ordre strict des tours.
- Implémentation attendue: créer `app/conversation/domain/conversation.py`, `app/conversation/application/start_conversation.py`, `app/conversation/application/append_turn.py`, `app/conversation/adapters/in_memory_conversation_repository.py` et `app/conversation/adapters/in_memory_turn_repository.py`.
- Invariants et garde-fous: aucun fallback de conversation anonyme; aucun tour orphelin; aucune réécriture d'historique; aucun accès direct aux repositories RA ou EG.
- Dépendances: T-002; `app/context_registry.json`; `scripts/validate_architecture_boundaries.ps1`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_conversation_turn_append_only_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_conversation_turn_append_only_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_architecture_boundaries.ps1 -AppRoot .\app -ContextRegistryPath .\app\context_registry.json -SpecificationPath .\docs\specs\m001_frontieres_ddd_contrats_publies.md`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`.
- Commit RED: `test(m008): couvrir conversations tours append only`
- Commit GREEN: `feat(m008): creer conversations tours append only`

