# T-009 - Exposer l'endpoint de recherche approfondie et le routage CV

## Milestone
- Nom: M-009 - Recherche approfondie multi-sources.
- Source: spécification v4.1 sections 12 et 17, spécification M-008 de conversation produit, et spécification M-009 publiée par T-002.
- Objectif métier: rendre la recherche approfondie accessible par API et par conversation sans fallback de mode.

## Contexte DDD
- Domaine: recherche et réponse vérifiée approfondie exposée au produit.
- Bounded contexts: RA propriétaire de `POST /v1/research/deep`, CV consommateur via le mode `RECHERCHE_APPROFONDIE`.
- Objectif métier: permettre à l'utilisateur de demander explicitement une analyse approfondie depuis le chatbot ou l'API dédiée.
- Langage ubiquitaire: endpoint RA, `DeepResearchRequest`, `AnswerQuestionResult`, `ConversationMode.RECHERCHE_APPROFONDIE`, façade RA, résultat vérifié attaché au tour, erreur publique.
- Invariants critiques: RA possède les règles de recherche; CV ne modifie pas RA; le mode approfondi est disponible seulement quand le handler RA existe; aucun fallback vers réponse documentaire simple n'est appliqué.
- Garde-fous: aucune exposition de stockage RA, KA, EG ou SP; aucun prompt override; aucun champ de support_status imposé par le client; aucune option compatible chat ignorée silencieusement.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-008 terminée.
- Présence des milestones amont dans master: M-008 présent.
- Décisions manquantes: aucune si l'API applique la surface indicative v4.1; ADR requise si une nouvelle façade centralise des règles de domaine hors RA/CV.
- Risques: rendre `RECHERCHE_APPROFONDIE` disponible côté CV avant RA; mélanger adapter HTTP et décision de support; casser `/v1/answer` M-007.

## Tâches
### T-009 - Exposer l'endpoint de recherche approfondie et le routage CV
- But métier: fournir une commande publique explicite pour la recherche approfondie et l'attacher aux conversations.
- Portée DDD: endpoint `POST /v1/research/deep`, validation du payload, erreurs publiques RA, façade CV vers RA, disponibilité du mode `RECHERCHE_APPROFONDIE`, attachement de réponse approfondie au tour.
- Scénario BDD:
  - Given une conversation active et une question résolue demandant une recherche approfondie.
  - When CV sélectionne le mode `RECHERCHE_APPROFONDIE`.
  - Then RA exécute `POST /v1/research/deep` par façade explicite et le tour reçoit un résultat vérifié sans fallback documentaire simple.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue tant que l'endpoint et le routage CV ne publient pas le contrat M-009.
- Tests unitaires à écrire: tests de payload interdit, mandat absent, mode forcé indisponible, fallback documentaire simple refusé, réponse RA sans citations, erreur publique instable, stockage interne exposé et régression `/v1/answer`.
- Implémentation attendue: créer ou étendre `app/research_answering/adapters/answer_http.py` pour `POST /v1/research/deep`, ajouter le workflow RA approfondi, rendre le mode disponible dans l'orchestration CV lorsque la façade RA M-009 est fournie et préserver les endpoints M-008.
- Invariants et garde-fous: RA reste propriétaire du comportement; CV ne lit pas les preuves internes; mode explicite obligatoire; erreurs publiques stables.
- Dépendances: T-008; `app/research_answering/adapters/answer_http.py`; `app/conversation/domain/mode_routing.py`; `app/conversation/application/answer_conversation_turn.py`; `uv run --locked gate`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m009): couvrir endpoint recherche approfondie`
- Commit GREEN: `feat(m009): exposer endpoint recherche approfondie`
