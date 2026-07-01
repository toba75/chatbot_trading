# T-009 - Exposer les endpoints de conversation et l'archivage

## Milestone
- Nom: M-008 - Conversation produit.
- Source: spécification v4.1, API `/v1/conversations`, consultation de tours et `ConversationRetentionPolicy`.
- Objectif métier: permettre au produit de créer, consulter, alimenter et archiver une conversation sans supprimer les connaissances associées.

## Contexte DDD
- Domaine: conversation produit fondée sur preuves.
- Bounded context: CV.
- Objectif métier: publier le contrat HTTP interne de conversation en conservant les frontières DDD.
- Langage ubiquitaire: endpoint conversation, consultation de tours, archivage, suppression produit, `ConversationArchived`, tour append-only, `CONVERSATION_NOT_FOUND`, `CONVERSATION_ARCHIVED`.
- Invariants critiques: `DELETE /v1/conversations/{conversation_id}` archive ou supprime la vue CV selon politique explicite sans cascade vers RA, EG, KA, SD ou EX; les tours restent consultables selon le statut autorisé; les requêtes invalides échouent explicitement.
- Garde-fous: aucun fallback de conversation; aucune suppression cascade de claims ou réponses vérifiées; aucun champ interne RA, KA, EG ou SP accepté dans le corps public.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-008 terminé.
- Présence des milestones amont dans master: M-007 présent.
- Décisions manquantes: ADR requise si une suppression physique, une durée de rétention ou une purge administrative durable est décidée.
- Risques: exposer un contrat API trop proche des modèles internes; laisser un message créer implicitement une conversation; archiver en supprimant des résultats métier aval.

## Tâches
### T-009 - Exposer les endpoints de conversation et l'archivage
- But métier: rendre la conversation utilisable par le produit local avec des erreurs explicites et une rétention maîtrisée.
- Portée DDD: adaptateur HTTP CV pour `POST /v1/conversations`, `GET /v1/conversations/{conversation_id}`, `GET /v1/conversations/{conversation_id}/turns`, `POST /v1/conversations/{conversation_id}/messages` et `DELETE /v1/conversations/{conversation_id}`.
- Scénario BDD:
  - Given une conversation contient un tour rattaché à une réponse vérifiée.
  - When l'utilisateur archive la conversation.
  - Then la conversation passe en statut archivé sans supprimer la réponse vérifiée ni les preuves référencées.
- Tests d'acceptation à écrire: `tests/m008/validate_conversation_http_contract_acceptance.ps1`, qui échoue tant que les endpoints internes de conversation et l'archivage sans cascade ne sont pas contrôlés.
- Tests unitaires à écrire: tests de payload invalide, conversation absente, conversation archivée, message sans idempotency key, consultation de tours ordonnés, archive sans cascade et refus de champs internes.
- Implémentation attendue: créer `app/conversation/adapters/conversation_http.py`, relier les handlers CV et publier les erreurs publiques M-008.
- Invariants et garde-fous: aucune création implicite depuis `POST /messages`; aucune cascade hors CV; aucune erreur masquée; aucune exposition de repository interne.
- Dépendances: T-003 à T-008; `ADR-010`; `DDD-ADR-002`; `DDD-ADR-008`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_conversation_http_contract_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_conversation_http_contract_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m008): couvrir contrat http conversation`
- Commit GREEN: `feat(m008): exposer endpoints conversation archive`

