# M-005 - Projection de connaissance recherchable

## Statut

- Milestone: M-005 - Projection de connaissance recherchable.
- ADR consultées: ADR-001, ADR-005, ADR-006, ADR-007, ADR-009, ADR-010, DDD-ADR-003, DDD-ADR-004, DDD-ADR-008.
- ADR: non requise, car M-005 applique les décisions existantes sans changer leur sens.

## Scénario BDD

- Given une version canonique M-004 publiée.
- When la spécification M-005 est publiée.
- Then chaque comportement de projection et recherche nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.

## Mission KA

KA construit des projections de recherche dérivées des versions canoniques publiées et retourne des preuves candidates traçables sans devenir source de vérité documentaire ou registre de claims.

La mission de M-005 est de rendre une version canonique M-004 recherchable par contrat KA. La projection peut être reconstruite, retirée ou marquée obsolète sans modifier la version canonique SP. KA ne rédige pas de réponse, ne vérifie pas de claim et ne décide pas la vérité d'une affirmation.

## Contexte DDD

- Domaine: accès aux connaissances.
- Bounded context: KA.
- Objectif métier: rendre une version canonique interrogeable tout en conservant SP comme source documentaire et EG comme registre des claims.
- Intégrations: KA consomme `CanonicalSourcePublished`, expose `KnowledgeSearchPort` à RA et EG, et publie ses événements via outbox en cohérence éventuelle.
- Garde-fous: Qdrant reste une projection régénérable; aucun claim EG dans l'index documentaire; RA consomme KnowledgeSearchPort sans accès direct à Qdrant; un score n'est pas une vérité métier.

## Langage ubiquitaire KA

| Terme | Sens M-005 |
|---|---|
| KnowledgeProjection | Agrégat KA qui relie une version canonique, un profil et un build régénérable. |
| ProjectionStatus | État observable de projection: REQUESTED, BUILDING, BUILT, INDEXING, SEARCHABLE, STALE, FAILED, RETIRED. |
| SearchKnowledge | Commande de recherche KA qui retourne des preuves candidates. |
| RequestKnowledgeProjection | Commande KA qui demande la construction d'une projection. |
| Preuve candidate | Passage documentaire retrouvable, cité et traçable; ce n'est pas un claim vérifié. |
| SearchScoreBundle | Détail des scores dense, sparse, fusion, rerank et diversification sans verdict de vérité. |
| SearchTracePolicy | Politique qui rend la recherche auditable. |
| SearchTraceStore | Port de persistance de la trace de fusion et des paramètres de recherche. |
| Fraîcheur | Relation explicite entre projection, version canonique, profil, modèles et date de build. |

## Agrégat KnowledgeProjection

| Agrégat | Responsabilité M-005 | Invariants | Événements |
|---|---|---|---|
| KnowledgeProjection | Construire, indexer, rendre recherchable, marquer stale, échouer ou retirer une projection KA. | Une projection ne peut être construite que depuis une version canonique publiée; une projection STALE ne doit pas être utilisée silencieusement; supprimer la projection ne supprime jamais la source canonique. | KnowledgeProjectionRequested; KnowledgeProjectionBuilt; KnowledgeProjectionBecameSearchable; KnowledgeProjectionFailed; KnowledgeProjectionBecameStale; KnowledgeProjectionRetired |

## Objets-valeur KA

| Objet-valeur | Sens M-005 | Invariants |
|---|---|---|
| KnowledgeProjectionId | Identité stable de projection. | Jamais dérivée d'un identifiant Qdrant. |
| CanonicalVersionRef | Référence à la version canonique M-004. | Obligatoire pour toute projection. |
| ProjectionProfile | Profil d'indexation versionné. | Aucun profil par défaut implicite. |
| BuildFingerprint | Empreinte des entrées de build. | Doit permettre une reconstruction idempotente. |
| SourceLocator | Localisateur résolvable de preuve candidate. | Obligatoire dans chaque résultat de recherche. |
| ContentHash | Hash du contenu canonique projeté. | Doit rester cohérent avec SourceLocator. |
| SearchScoreBundle | Scores de recherche détaillés. | Ne contient aucun verdict de vérité. |
| SearchTraceId | Identité de trace de recherche. | Obligatoire pour toute recherche auditable. |

## Politiques normatives M-005

| Politique | Décision | Invariants | ADR |
|---|---|---|---|
| ProjectionEligibilityPolicy | Autorise seulement les versions canoniques publiées et non mises en quarantaine. | Aucune source non canonique n'est indexable. | DDD-ADR-004; DDD-ADR-008 |
| ProjectionFreshnessPolicy | Refuse l'usage silencieux d'une projection STALE lorsqu'une projection actuelle est requise. | La fraîcheur est explicite dans la réponse ou l'erreur. | DDD-ADR-004 |
| HybridRetrievalPolicy | Combine dense, sparse, filtres, fusion, rerank et diversification. | Aucun fallback dense ou lexical silencieux. | ADR-005 |
| SearchTracePolicy | Persiste paramètres, versions, modèles, profils, filtres et trace de fusion. | Aucune recherche auditable sans SearchTraceStore. | ADR-010; DDD-ADR-008 |
| EvidenceCandidatePolicy | Retourne des preuves candidates et jamais des claims vérifiés. | L'index documentaire ne stocke aucun claim EG. | ADR-006 |

## Machine d'états M-005

| État | Portée | Sens M-005 | Transition autorisée |
|---|---|---|---|
| REQUESTED | KnowledgeProjection | La demande est acceptée. | Vers BUILDING ou FAILED. |
| BUILDING | KnowledgeProjection | Les chunks et métadonnées sont construits. | Vers BUILT ou FAILED. |
| BUILT | KnowledgeProjection | La projection documentaire est prête à indexer. | Vers INDEXING, STALE ou RETIRED. |
| INDEXING | KnowledgeProjection | L'index technique est publié. | Vers SEARCHABLE ou FAILED. |
| SEARCHABLE | KnowledgeProjection | La projection peut répondre à SearchKnowledge. | Vers STALE ou RETIRED. |
| STALE | KnowledgeProjection | Une entrée de build ou version amont a changé. | Vers BUILDING ou RETIRED. |
| FAILED | KnowledgeProjection | La construction ou indexation a échoué explicitement. | Vers REQUESTED après nouvelle commande. |
| RETIRED | KnowledgeProjection | La projection n'est plus servie. | Terminale. |

## Ports et adaptateurs KA

| Port | Responsabilité | Interdiction |
|---|---|---|
| CanonicalSourceReader | Lit les références canoniques publiées par SP. | Ne modifie jamais SP. |
| KnowledgeProjectionRepository | Persiste l'agrégat KnowledgeProjection. | Ne stocke pas les claims EG. |
| VectorIndex | Encapsule Qdrant comme projection technique régénérable. | RA et EG ne l'appellent jamais directement. |
| DenseEncoder | Produit les vecteurs denses versionnés. | Aucun modèle par défaut implicite. |
| SparseEncoder | Produit les représentations sparse versionnées. | Aucun fallback silencieux vers dense. |
| KnowledgeSearchPort | Contrat consommé par RA et EG pour obtenir des preuves candidates. | Aucun accès direct à Qdrant. |
| SearchTraceStore | Persiste la trace de fusion et les paramètres de recherche. | Aucune recherche auditable sans trace. |

`QdrantVectorIndex` est l'adaptateur technique injecté derrière `VectorIndex`; RA et EG ne dépendent jamais de `qdrant_client`.

## Événements KA

| Événement | Déclencheur | Payload publié |
|---|---|---|
| KnowledgeProjectionRequested | Une commande d'indexation KA est acceptée. | projection_id; document_id; canonical_version_id; projection_profile_id |
| KnowledgeProjectionBuilt | Chunks, métadonnées et empreinte sont construits. | projection_id; canonical_version_id; build_fingerprint; chunk_count |
| KnowledgeProjectionBecameSearchable | L'index régénérable est publié complètement. | projection_id; canonical_version_id; projection_profile_id; index_generation; published_at |
| KnowledgeProjectionFailed | Une étape échoue explicitement. | projection_id; failed_step; public_error_code; retry_allowed |
| KnowledgeProjectionBecameStale | Une version canonique ou un profil rend la projection obsolète. | projection_id; stale_reason; superseding_input_ref |
| KnowledgeProjectionRetired | Une projection est retirée du service de recherche. | projection_id; retired_reason |
| SearchKnowledgePerformed | Une recherche auditable est exécutée. | search_trace_id; projection_id; query_hash; filters_hash; result_count |

Après publication complète de l'index, la projection exécute obligatoirement
`EXTRACT_BIBLIOGRAPHIC_METADATA`. Le titre, les auteurs, l'année et l'édition
effectivement trouvés sont persistés avec leurs preuves paginées. La projection
ne devient `SEARCHABLE` qu'après cette persistance ; un échec de l'extraction
produit `KnowledgeProjectionFailed` sans fallback.

## API publique KA

| Endpoint | Succès | Erreurs publiques | Corps public |
|---|---|---|---|
| POST /v1/documents/{document_id}/index | 202 INDEXATION_REQUESTED quand la version canonique est acceptée pour projection. | 400 HTTP_REQUEST_INVALID; 404 SOURCE_NOT_FOUND; 409 SOURCE_NOT_CANONICAL; 409 SOURCE_QUARANTINED; 409 PROJECTION_ALREADY_REQUESTED; 422 PROJECTION_PROFILE_INVALID. | document_id; projection_id; projection_status; canonical_version_id. |
| POST /v1/search | 200 SEARCH_COMPLETED quand les preuves candidates sont retournées avec trace. | 400 HTTP_REQUEST_INVALID; 404 PROJECTION_NOT_FOUND; 409 PROJECTION_STALE; 422 FILTER_NOT_SUPPORTED; 422 SEARCH_PROFILE_UNSUPPORTED; 503 SEARCH_INDEX_UNAVAILABLE. | search_trace_id; projection_id; results; warnings; applied_filters. |

### Corps de requête publics

| Endpoint | Champs acceptés | Champs interdits |
|---|---|---|
| POST /v1/documents/{document_id}/index | projection_profile_id; chunking_profile; embedding_model; sparse_profile; index_schema | qdrant_collection; build_fingerprint; canonical_version_id imposé par le client |
| POST /v1/search | projection_id; query_text; filters; search_profile_id; occurred_at | requested_by_context; qdrant_collection; embedding_model; projection_profile_id |

Le contexte consommateur de `POST /v1/search` est fourni par le transport authentifié (`authenticated_context`) et non par le body public. Les seuls contextes autorisés pour la recherche sont RA et EG.

## Erreurs publiques

| Code | Statut HTTP | Sens public |
|---|---|---|
| HTTP_REQUEST_INVALID | 400 | Requête KA invalide. |
| SOURCE_NOT_FOUND | 404 | Source ou document inconnu. |
| SOURCE_NOT_CANONICAL | 409 | La version canonique publiée est absente. |
| SOURCE_QUARANTINED | 409 | La source est explicitement non indexable. |
| PROJECTION_ALREADY_REQUESTED | 409 | Une demande identique existe déjà. |
| PROJECTION_PROFILE_INVALID | 422 | Le profil de projection est invalide. |
| PROJECTION_NOT_FOUND | 404 | Projection absente. |
| PROJECTION_STALE | 409 | Projection obsolète refusée explicitement. |
| FILTER_NOT_SUPPORTED | 422 | Filtre inconnu ou non supporté. |
| SEARCH_PROFILE_UNSUPPORTED | 422 | Profil de recherche non supporté. |
| SEARCH_INDEX_UNAVAILABLE | 503 | Projection technique indisponible sans fallback silencieux. |

## Métriques et traces

| Signal | Type | Invariant |
|---|---|---|
| knowledge_projection_build_total | Métrique | Compte les builds par statut public. |
| knowledge_projection_searchable_total | Métrique | Compte les projections devenues SEARCHABLE. |
| knowledge_projection_failed_total | Métrique | Compte les échecs par code public. |
| knowledge_search_latency_seconds | Métrique | Mesure la latence sans payload documentaire complet. |
| knowledge_search_stale_projection_total | Métrique | Compte les refus de projection STALE. |
| knowledge_search_recall_at_k | Métrique d'évaluation | Mesure initiale M-005, pas seuil métier V1. |
| knowledge_search_mrr | Métrique d'évaluation | Mesure initiale M-005, pas seuil métier V1. |
| knowledge_search_ndcg | Métrique d'évaluation | Mesure initiale M-005, pas seuil métier V1. |
| search_trace_persisted_total | Trace | Prouve la persistance des paramètres, versions, modèles, profils, filtres et trace de fusion. |

## Comportements vérifiables M-005

| Comportement | Invariant | Scénario BDD | Test RED | ADR | Commande |
|---|---|---|---|---|---|
| KA-001 - Spécification exécutable M-005 | La spécification nomme mission KA, KnowledgeProjection, états, politiques, ports, événements, API, erreurs, métriques, exclusions et garde-fous. | Given une version canonique M-004 publiée; When la spécification M-005 est publiée; Then elle est validée par commande uv run --locked gate
| KA-002 - Projection depuis version canonique | Une projection ne naît que depuis une version canonique publiée. | Given une CanonicalSource publiée; When RequestKnowledgeProjection est accepté; Then KnowledgeProjection est REQUESTED sans mutation SP. | T-003 | DDD-ADR-004; DDD-ADR-008; ADR-010 | uv run --locked gate
| KA-003 - Chunking traçable | Chaque chunk conserve SourceLocator et ContentHash. | Given un contenu canonique; When KA découpe le contenu; Then chaque chunk reste relié à la version canonique. | T-004 | ADR-001; ADR-006; DDD-ADR-003; DDD-ADR-004 | uv run --locked gate
| KA-004 - Métadonnées filtrables | Un filtre demandé est appliqué ou refusé explicitement. | Given une projection avec métadonnées; When SearchKnowledge reçoit des filtres; Then les filtres sont appliqués ou refusés. | T-005 | ADR-005; DDD-ADR-004 | uv run --locked gate
| KA-005 - Encodage dense et sparse | Les versions de modèles et paramètres sont obligatoires. | Given une projection construite; When l'encodage démarre; Then dense et sparse sont produits sans fallback silencieux. | T-006 | ADR-005; ADR-007; ADR-009; DDD-ADR-004 | uv run --locked gate
| KA-006 - Index Qdrant régénérable | Qdrant reste une projection technique reconstruisible. | Given des encodages complets; When l'index est publié; Then KnowledgeProjectionBecameSearchable est émis après publication complète. | T-007 | ADR-005; DDD-ADR-004; DDD-ADR-008 | uv run --locked gate
| KA-007 - Recherche hybride traçable | Chaque résultat contient SourceLocator, ContentHash, SearchScoreBundle et trace de fusion. | Given une projection SEARCHABLE; When SearchKnowledge exécute une recherche hybride; Then KA retourne des preuves candidates auditées. | T-008 | ADR-005; ADR-006; DDD-ADR-003; DDD-ADR-004; DDD-ADR-008 | uv run --locked gate
| KA-008 - Commande de recherche publique | Le contrat POST /v1/search masque Qdrant et expose seulement KA. | Given un client appelle POST /v1/search; When la recherche est valide; Then la réponse contient seulement le contrat public KA. | T-009 | ADR-005; ADR-006; ADR-010; DDD-ADR-003; DDD-ADR-004 | uv run --locked gate
| KA-009 - Traçabilité et métriques M-005 | Aucun GREEN n'est implicite et les métriques ne sont pas des seuils V1. | Given les preuves M-005; When les gates s'exécutent; Then test, lint, traceability et validate_m005_specification sont enrôlés. | T-010 | ADR-005; ADR-006; ADR-010; DDD-ADR-004; DDD-ADR-008 | uv run --locked gate

## Commandes de validation

```console
uv run --locked gate
uv run --locked gate
uv run --locked gate
uv run --locked gate
uv run --locked gate
uv run --locked gate
```

## Exclusions M-006 et M-007

- M-005 ne crée, ne vérifie et ne stocke aucun claim EG.
- M-005 ne produit aucune réponse RA, aucune synthèse et aucun verdict de vérité.
- M-005 ne publie pas `POST /v1/claims/extract`, `POST /v1/claims/{id}/verify`, `POST /v1/answer` ou `POST /v1/research/deep`.
