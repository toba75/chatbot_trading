# T-009 - Exposer la commande de recherche Knowledge Access

## Milestone
- Nom: M-005 - Projection de connaissance recherchable.
- Source: livrables M-005 endpoint `POST /v1/search`, contrat KA distinct de `POST /v1/documents/{document_id}/index` et sortie attendue pour RA/EG.
- Objectif métier: rendre la recherche KA disponible derrière un contrat applicatif strict.

## Contexte DDD
- Domaine: accès aux connaissances.
- Bounded context: KA.
- Objectif métier: exposer `SearchKnowledge` sans exposer Qdrant, les embeddings ni les détails de fusion.
- Langage ubiquitaire: requête de recherche, mandat de recherche local, preuve candidate, erreur publique, projection actuelle.
- Invariants critiques: une requête invalide est refusée; une projection absente ou stale produit une erreur explicite; la réponse contient seulement le contrat public KA.
- Garde-fous: aucun champ interne Qdrant dans l'API; aucun historique conversationnel comme preuve; aucune génération de réponse documentaire dans M-005.

## Blocages Ou Préconditions
- État GREEN/RED connu: recherche hybride disponible après T-008.
- Présence des milestones amont dans master: M-002 fournit la file de jobs et l'outillage HTTP local; M-004 fournit les références canoniques.
- Décisions manquantes: aucune si `POST /v1/search` reste dans KA et ne déplace pas les responsabilités RA.
- Risques: API trop proche de Qdrant; erreurs publiques ambiguës; RA intégré prématurément.

## Tâches
### T-009 - Exposer la commande de recherche Knowledge Access
- But métier: permettre à un consommateur interne ou local de demander des preuves candidates par contrat stable.
- Portée DDD: service applicatif `SearchKnowledge`, adaptateur HTTP `POST /v1/search`, erreurs publiques, validation de requête et sérialisation de réponse; l'endpoint d'indexation reste porté par T-003.
- Scénario BDD:
  - Given une projection actuelle est `SEARCHABLE`.
  - When un client appelle `POST /v1/search` avec une requête valide.
  - Then KA retourne des preuves candidates citées, scorées et traçables sans exposer la collection Qdrant.
- Tests d'acceptation à écrire: `tests/m005/validate_search_command_acceptance.ps1`, couvrant succès, requête invalide, projection absente, projection stale, filtre non supporté et absence de champs internes.
- Tests unitaires à écrire: tests de validation de requête, mapping erreurs publiques, sérialisation `SearchResponse` et refus de corps ambigu.
- Implémentation attendue: créer l'adaptateur HTTP KA, les DTO publics de recherche et l'intégration avec le port `KnowledgeSearchPort`.
- Invariants et garde-fous: aucun fallback vers une recherche vide; aucun `200` sur erreur métier; aucun texte documentaire complet dans les logs; aucun endpoint RA livré dans M-005; aucune confusion entre commande d'indexation KA et requête de recherche KA.
- Dépendances: T-008; ADR-010; ADR-005; DDD-ADR-004; conventions HTTP existantes M-003/M-004.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_search_command_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_search_command_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_hybrid_search_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m005): couvrir la commande de recherche`
- Commit GREEN: `feat(m005): exposer la recherche knowledge access`
