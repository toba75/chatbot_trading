# T-010 - Exposer la commande de recherche approfondie

## Milestone
- Nom: M-009 - Recherche approfondie multi-sources.
- Source: plan M-009 et spécification v4.1, API fonctionnelle et conversation orchestrée.
- Objectif métier: rendre la recherche approfondie appelable par l'API produit et par CV sans contourner les invariants RA.

## Contexte DDD
- Domaine: recherche et réponse vérifiée approfondie.
- Bounded context: RA, avec intégration CV.
- Objectif métier: exposer `POST /v1/research/deep` comme commande publique stricte de recherche approfondie.
- Langage ubiquitaire: `RunDeepResearchHandler`, endpoint de recherche approfondie, `ResolvedQuestion`, `ResearchMandate`, idempotence, contrat public, statut documentaire.
- Invariants critiques: une question autonome et un mandat explicite sont obligatoires; le mode approfondi est explicite; le contrat public n'expose pas KA, EG, Qdrant ou prompt.
- Garde-fous: aucun fallback vers `POST /v1/answer`; aucun mode par défaut; aucun champ `prompt_override`; aucun statut forcé par payload.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-009 terminé.
- Présence des milestones amont dans master: M-008 présent, notamment routage conversationnel vers `RECHERCHE_APPROFONDIE`.
- Décisions manquantes: aucune si l'endpoint applique le contrat RA; ADR requise si une façade centrale devient propriétaire de règles RA.
- Risques: dupliquer CV dans RA; accepter une requête sans mandat; exposer des champs de stockage; rendre la recherche approfondie non idempotente.

## Tâches
### T-010 - Exposer la commande de recherche approfondie
- But métier: permettre à l'utilisateur et à CV de lancer une recherche approfondie vérifiée.
- Portée DDD: adaptateur HTTP RA, DTO public strict, handler `RunDeepResearchHandler`, mapping des erreurs publiques, idempotence et réponse contenant statut, citations, contradictions, lacunes et synthèse.
- Scénario BDD:
  - Given CV envoie une question résolue avec mode `RECHERCHE_APPROFONDIE` et mandat explicite.
  - When `POST /v1/research/deep` est appelé.
  - Then RA exécute le flux approfondi et retourne une réponse publique sans exposer stockage interne, prompt ou statut forcé.
- Tests d'acceptation à écrire: `tests/m009/validate_deep_research_http_acceptance.ps1`, qui échoue tant que l'endpoint public n'exécute pas le workflow M-009.
- Tests unitaires à écrire: tests pour mandat absent, mode absent, mode simple refusé, champ interdit, idempotency_key absent, payload CV valide, erreur de couverture insuffisante, conflit non résolu, réponse supportée et absence de détail Qdrant ou EG.
- Implémentation attendue: créer `app/research_answering/adapters/deep_research_http.py`, créer ou compléter `RunDeepResearchHandler`, exposer le DTO public et connecter le mode CV sans importer le domaine CV dans RA.
- Invariants et garde-fous: aucun fallback de mode; aucun accès direct au LLM; aucun stockage interne dans le JSON public; aucune publication sans `EvidenceSet` scellé.
- Dépendances: T-009; M-008 `ConversationMode.RECHERCHE_APPROFONDIE`; `AnswerQuestionResult`; `VerifiedResearchOutcome`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_deep_research_http_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_deep_research_http_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m009): couvrir contrat http recherche approfondie`
- Commit GREEN: `feat(m009): exposer recherche approfondie http`

