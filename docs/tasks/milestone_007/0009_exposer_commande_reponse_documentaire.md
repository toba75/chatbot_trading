# T-009 - Exposer la commande publique de réponse documentaire

## Milestone
- Nom: M-007 - Réponse documentaire vérifiée.
- Source: plan M-007 et spécification v4.1, surface HTTP `POST /v1/answer`, règle de façade et erreurs métier.
- Objectif métier: exposer RA par un contrat public strict sans déplacer la logique de domaine dans une façade HTTP.

## Contexte DDD
- Domaine: recherche et réponse vérifiée.
- Bounded context: RA.
- Objectif métier: permettre à un client de demander une réponse documentaire et de recevoir statut, citations, lacunes et trace sans détail interne.
- Langage ubiquitaire: `AnswerQuestionHandler`, `POST /v1/answer`, `ANSWER_ASSERTION_UNSUPPORTED`, `CURRENT_DATA_REQUIRED`, `EvidenceSet`, `VerifiedResearchOutcome`, trace de réponse.
- Invariants critiques: l'endpoint délègue à RA; les erreurs publiques sont stables; le corps public n'expose pas prompt, brouillon interne, repository ou payload complet de preuve.
- Garde-fous: aucun contrôleur central avec règles métier; aucun fallback vers recherche directe Qdrant; aucun statut implicite en cas de champ absent.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-003 à T-008 terminés selon les chemins de réponse exposés.
- Présence des milestones amont dans master: M-006 présent.
- Décisions manquantes: aucune si l'adaptateur reste une façade de composition; ADR requise si une API compatible OpenAI modifie le contrat RA public de M-007.
- Risques: fuite de détails internes; authentification ou contexte ignoré; endpoint qui publie un brouillon; mapping d'erreur ambigu.

## Tâches
### T-009 - Exposer la commande publique de réponse documentaire
- But métier: rendre la réponse documentaire utilisable par l'API sans affaiblir les invariants RA.
- Portée DDD: adaptateur public `AnswerHttpAdapter`, commande `AnswerQuestion`, handler `AnswerQuestionHandler`, contrats d'entrée/sortie, erreurs publiques et mapping des statuts RA.
- Scénario BDD:
  - Given une requête `POST /v1/answer` contient une question autonome, un mandat et une clé d'idempotence.
  - When RA produit une réponse vérifiée, partielle, conflictuelle, insuffisante ou abstinente.
  - Then la réponse publique expose le statut documentaire, les citations ouvrables, les lacunes et la trace sans prompt ni détail de stockage.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue tant que l'endpoint RA public n'expose pas les statuts et erreurs M-007.
- Tests unitaires à écrire: tests pour méthode ou chemin invalide, question absente, mandat absent, idempotence absente, champ interdit, contexte non autorisé, erreur `ANSWER_ASSERTION_UNSUPPORTED`, erreur `CURRENT_DATA_REQUIRED`, fuite de prompt, fuite de repository et accès direct à KA/EG/SP depuis l'adaptateur.
- Implémentation attendue: ajouter l'adaptateur HTTP minimal RA, les DTO publics, le mapping strict des erreurs, les réponses publiques et l'enrôlement dans les tests de contrat.
- Invariants et garde-fous: aucune logique métier dans l'adaptateur; aucun fallback en cas de handler absent; aucun corps interne publié; aucun accès direct Qdrant, repository EG ou table SP.
- Dépendances: T-003; T-004; T-007; T-008; ADR-010; `VerifiedResearchOutcome`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m007): couvrir contrat http reponse documentaire`
- Commit GREEN: `feat(m007): exposer commande reponse documentaire`
