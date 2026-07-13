# T-005 - Publier le contrat du gateway LLM

## Milestone
- Nom: M-002 - Plateforme locale sûre.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, livrable `contract test compatible OpenAI entre llm-gateway et vLLM Spark`, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 13, 15, 16 et 20.
- Objectif métier: donner aux contextes un port d'inférence stable sans dépendance directe au protocole vLLM.

## Contexte DDD
- Domaine: frontière d'inférence technique.
- Bounded context: `platform.llm_gateway`, consommé par les cas d'usage sans importer le SDK vLLM dans le domaine.
- Objectif métier: traduire une demande d'inférence structurée vers l'API compatible OpenAI privée et retourner un résultat ou une erreur explicite.
- Langage ubiquitaire: demande d'inférence, modèle servi, appel compatible OpenAI, TLS, clé d'API, schéma de sortie, `trace_id`, `request_id`, `idempotency_key`.
- Invariants critiques: seul `llm-gateway` appelle le Spark; le navigateur et les bounded contexts n'appellent pas vLLM; le gateway ne décide pas l'état métier; les sorties JSON sont validées syntaxiquement avant usage.
- Garde-fous: ne pas exposer le client vLLM dans `domain/`; ne pas accepter une réponse sans provenance minimale; ne pas remplacer TLS par HTTP en cas d'erreur.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-004 doit être GREEN.
- Présence des milestones amont dans master: M-000 et M-001 sont présents dans `master`.
- Décisions manquantes: aucune si ADR-008 est appliquée sans changer le chemin unique; une ADR est requise si un provider supplémentaire est ajouté.
- Risques: coupler les contextes au protocole OpenAI; considérer une réponse JSON valide comme décision métier; journaliser le prompt complet.

## Tâches
### T-005 - Publier le contrat du gateway LLM
- But métier: permettre aux futures capacités métier d'appeler Gemma sans connaître vLLM ni accéder directement au Spark.
- Portée DDD: port technique `LocalLanguageModelGateway`, contrat de requête/réponse, provenance de modèle, erreurs explicites et test de compatibilité OpenAI.
- Scénario BDD:
  - Given un cas d'usage demande une inférence Gemma avec schéma de sortie et identifiants de corrélation.
  - When le gateway transmet l'appel vers vLLM Spark.
  - Then la réponse compatible OpenAI est traduite en résultat structuré avec provenance, ou en erreur technique explicite sans décision métier.
- Tests d'acceptation à écrire: un contract test avec double vLLM compatible OpenAI qui vérifie modèle servi, schéma de sortie, TLS requis, clé d'API requise et absence d'appel direct hors gateway.
- Tests unitaires à écrire: tests de construction de requête, validation de configuration obligatoire, provenance minimale, refus d'un schéma absent, refus d'un résultat sans `model_revision` et masquage des secrets.
- Implémentation attendue: créer le port et l'adaptateur minimal du gateway, les objets de contrat et les tests contre un double HTTP contrôlé.
- Invariants et garde-fous: aucune URL par défaut; aucun provider distant silencieux; aucun import vLLM dans `domain/`; aucune décision métier dans le gateway.
- Dépendances: T-004; ADR-008; ADR-009; `app/platform/llm_gateway`; tests d'architecture M-001.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m002): couvrir le contrat gateway llm`.
- Commit GREEN: `feat(m002): publier le contrat gateway llm`.
