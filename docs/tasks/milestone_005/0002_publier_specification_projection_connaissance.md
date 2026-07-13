# T-002 - Publier la spécification de projection de connaissance

## Milestone
- Nom: M-005 - Projection de connaissance recherchable.
- Source: plan M-005 et spécification v4.1, sections KA, projections régénérables, indexation, recherche hybride, API et critères V1.
- Objectif métier: publier le contrat exécutable du bounded context KA avant toute implémentation de projection ou de recherche.

## Contexte DDD
- Domaine: accès aux connaissances.
- Bounded context: KA.
- Objectif métier: définir comment KA construit des projections dérivées et retourne des preuves candidates sans devenir source de vérité.
- Langage ubiquitaire: `KnowledgeProjection`, `ProjectionStatus`, `SearchKnowledge`, `RequestKnowledgeProjection`, preuve candidate, `SearchScoreBundle`, `SearchTracePolicy`, `SearchTraceStore`, trace de fusion, fraîcheur.
- Invariants critiques: Qdrant reste une projection; chaque résultat contient un `SourceLocator` résolvable et un `content_hash` cohérent; une projection `STALE` ne doit pas être utilisée silencieusement.
- Garde-fous: aucun claim EG dans l'index documentaire; aucun accès direct de RA à Qdrant; aucun score de similarité traité comme verdict de vérité.

## Blocages Ou Préconditions
- État GREEN/RED connu: précondition M-005 attendue GREEN après T-001.
- Présence des milestones amont dans master: M-004 requis et présent.
- Décisions manquantes: aucune si la spécification applique ADR-005, ADR-006, DDD-ADR-004, DDD-ADR-008 et ADR-010 sans en changer le sens.
- Risques: spécification trop technique centrée sur Qdrant; oubli des états de projection; absence de scénario mesurable pour filtres, fraîcheur et métriques.

## Tâches
### T-002 - Publier la spécification de projection de connaissance
- But métier: rendre M-005 implémentable par comportements vérifiables, dans le langage KA.
- Portée DDD: mission KA, agrégat `KnowledgeProjection`, états, objets-valeur, politiques, ports, événements KA, API publiée `POST /v1/documents/{document_id}/index` et `POST /v1/search`, erreurs publiques, métriques et exclusions M-006/M-007.
- Scénario BDD:
  - Given une version canonique M-004 publiée.
  - When la spécification M-005 est publiée.
  - Then chaque comportement de projection et recherche nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue tant que `docs/specs/m005_projection_connaissance_recherchable.md` et son validateur n'existent pas.
- Tests unitaires à écrire: tests de `uv run --locked gate` pour sections manquantes, comportements incomplets, ADR absente, endpoint d'indexation absent, événements KA absents, `SearchTraceStore` absent, projection Qdrant traitée comme source, claim stocké dans l'index et accès RA direct à Qdrant.
- Implémentation attendue: créer `docs/specs/m005_projection_connaissance_recherchable.md`, créer `uv run --locked gate`, enrôler la validation dans les gates et relier les exigences M-005 à la matrice de traçabilité, en couvrant explicitement `KnowledgeProjectionBecameSearchable` et la journalisation des paramètres de recherche.
- Invariants et garde-fous: aucune décision structurante implicite; pas de fallback lexical ou dense silencieux; pas de seuil métier non justifié; pas de dépendance applicative publique à une collection Qdrant.
- Dépendances: T-001; ADR-005; ADR-006; DDD-ADR-004; DDD-ADR-008; ADR-010; `docs/tasks/README.md`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m005): couvrir la specification de projection`
- Commit GREEN: `docs(m005): publier la specification de projection`
