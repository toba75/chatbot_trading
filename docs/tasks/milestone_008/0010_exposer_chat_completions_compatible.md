# T-010 - Exposer le contrat compatible chat completions

## Milestone
- Nom: M-008 - Conversation produit.
- Source: spécification v4.1, endpoint compatible `POST /v1/chat/completions`.
- Objectif métier: permettre l'intégration de clients de chat existants sans perdre les preuves, statuts et tours CV.

## Contexte DDD
- Domaine: conversation produit fondée sur preuves.
- Bounded context: CV.
- Objectif métier: adapter une requête compatible chat vers les commandes CV sans faire de l'API externe le modèle de domaine.
- Langage ubiquitaire: compatibilité chat, conversation locale, message utilisateur, assistant, `conversation_id`, statut documentaire, citation, idempotence, contrat public.
- Invariants critiques: le contrat compatible ne contourne pas `Conversation`; aucun `prompt_override` ne force un statut documentaire; les statuts et citations restent disponibles dans l'extension produit depuis le DTO de résultat documentaire public RA; les champs non supportés sont refusés explicitement.
- Garde-fous: aucun fallback vers un chat générique; aucune réponse sans tour CV; aucune perte silencieuse de preuve; aucune exposition directe de vLLM ou du Spark.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-009 terminé.
- Présence des milestones amont dans master: M-007 présent.
- Décisions manquantes: ADR requise si la compatibilité OpenAI devient un contrat public stable avec garanties au-delà de l'adaptateur local.
- Risques: copier un schéma externe dans le domaine; accepter des options non supportées; produire une réponse chat sans `VerifiedResearchOutcome`; supposer que les citations sont des champs du contrat `VerifiedResearchOutcome`.

## Tâches
### T-010 - Exposer le contrat compatible chat completions
- But métier: rendre le chatbot local consommable par des clients existants tout en conservant la chaîne de preuve CV et RA.
- Portée DDD: adaptateur HTTP `POST /v1/chat/completions`, mapping vers conversation existante ou création explicite, validation stricte des champs acceptés, extension de réponse avec statuts et citations issus du DTO de présentation CV.
- Scénario BDD:
  - Given un client appelle `/v1/chat/completions` avec un `conversation_id` et un message utilisateur.
  - When CV traite la requête compatible.
  - Then un tour CV est créé et la réponse expose le texte assistant avec statut documentaire et citations dans les champs produit.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue tant que l'endpoint compatible ne crée pas de tour CV traçable.
- Tests unitaires à écrire: tests de payload minimal valide, champ non supporté, conversation absente, absence d'idempotence, mapping des rôles, conservation des citations depuis le DTO public RA, refus de `prompt_override`, refus d'un accès direct au LLM et absence d'hypothèse de champ `citations` dans `VerifiedResearchOutcome`.
- Implémentation attendue: créer `app/conversation/adapters/chat_completions_http.py` et les DTO de compatibilité stricts.
- Invariants et garde-fous: aucun mode chat générique; aucun statut documentaire inventé; aucun champ externe accepté silencieusement; aucune dépendance au protocole vLLM dans le domaine CV.
- Dépendances: T-009; `app/conversation/adapters/conversation_http.py`; `app/platform/llm_gateway` uniquement derrière les ports applicatifs autorisés.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m008): couvrir contrat chat completions`
- Commit GREEN: `feat(m008): exposer chat completions compatible`
