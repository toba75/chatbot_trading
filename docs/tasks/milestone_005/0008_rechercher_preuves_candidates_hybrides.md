# T-008 - Rechercher des preuves candidates hybrides

## Milestone
- Nom: M-005 - Projection de connaissance recherchable.
- Source: livrables M-005 fusion hybride, reranking derrière un port, scores, citations et provenance.
- Objectif métier: retourner des passages candidats traçables, non des faits vérifiés.

## Contexte DDD
- Domaine: accès aux connaissances.
- Bounded context: KA.
- Objectif métier: permettre à RA et EG de demander des preuves candidates via `KnowledgeSearchPort`.
- Langage ubiquitaire: `SearchKnowledge`, `SearchRequest`, `SearchResponse`, `RetrievalCandidate`, `SearchScoreBundle`, `SearchTracePolicy`, `SearchTraceStore`, trace de fusion, reranking, diversification.
- Invariants critiques: chaque candidat contient `SourceLocator`, `content_hash`, scores distincts, version de projection, avertissement de fraîcheur et trace de fusion; les paramètres de recherche et versions de modèles sont journalisés; un score n'est jamais un verdict de vérité.
- Garde-fous: pas de recherche sur projection non `SEARCHABLE`; pas de filtre ignoré; pas de reranking silencieusement absent si demandé par le profil; pas de recherche auditable sans trace persistée.

## Blocages Ou Préconditions
- État GREEN/RED connu: projection `SEARCHABLE` disponible après T-007.
- Présence des milestones amont dans master: M-001 fournit les contrats de références; M-004 rend les localisateurs résolvables.
- Décisions manquantes: aucune si la recherche hybride applique ADR-005.
- Risques: recherche dense seule par facilité; citations non ouvrables; fusion non auditée; RA contournant le port.

## Tâches
### T-008 - Rechercher des preuves candidates hybrides
- But métier: fournir à RA et EG des preuves candidates ordonnées et auditables sans dépendance Qdrant.
- Portée DDD: `KnowledgeSearchPort`, politiques `HybridRetrievalPolicy`, `ParentContextExpansionPolicy`, `SearchTracePolicy`, `SearchTraceStore`, reranking, diversification et réponse de recherche.
- Scénario BDD:
  - Given une projection `SEARCHABLE`.
  - When une recherche retourne un passage.
  - Then le passage contient un `SourceLocator` résolvable, un `content_hash` cohérent, des scores distincts, une trace de fusion et une trace de recherche persistée avec les paramètres et versions utilisés.
- Tests d'acceptation à écrire: `uv run --locked gate`, couvrant recherche dense+sparse, fusion, reranking, filtre, diversification, locator résolvable, refus projection stale et trace persistée.
- Tests unitaires à écrire: tests de `SearchRequest`, `SearchResponse`, `RetrievalCandidate`, `SearchScoreBundle`, fusion RRF déterministe, expansion parent, politique de fraîcheur, `SearchTracePolicy` et `SearchTraceStore`.
- Implémentation attendue: créer l'application `search_knowledge.py`, les ports de recherche, reranking, résolution de locator et stockage de trace, puis retourner une réponse indépendante de Qdrant avec avertissements de fraîcheur.
- Invariants et garde-fous: aucun score global sans détail dense/sparse/rerank; aucun candidat sans citation; aucun fallback vers une projection stale; aucune conclusion métier dans KA; aucune recherche auditable sans versions de projection, modèles, profils et filtres dans la trace.
- Dépendances: T-007; ADR-005; DDD-ADR-003; DDD-ADR-004; M-004 T-007.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m005): couvrir la recherche hybride tracable`
- Commit GREEN: `feat(m005): rechercher des preuves candidates hybrides`
