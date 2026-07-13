# T-018 - Construire et interroger une projection KA réelle

## Milestone

- Nom: M-013 - Durcissement et acceptation V1, tranche `M13-remediation`.
- Source: `docs/specs/plan_remediation_m13.md`, écarts V1 KA et contrats de recherche de connaissances.
- Objectif métier: prouver que la recherche retrouve les bonnes pages depuis les versions canoniques réelles, avec provenance ouvrable.

## Contexte DDD

- Domaine: assistant personnel de trading et d'investissement fondé sur preuves.
- Bounded context: `knowledge_access`, avec dépendances vers `source_processing` et `evidence_governance`.
- Objectif métier: construire une projection de connaissance réelle depuis le corpus traité, puis mesurer si les pages attendues sont retrouvées.
- Langage ubiquitaire: projection de connaissance, index hybride, embeddings, reranking, `SourceLocator`, rappel attendu, provenance ouvrable, index stale.
- Invariants critiques: chaque candidat porte un locator résoluble; un index vide ne peut pas réussir; un index stale échoue explicitement; la page attendue absente bloque le scénario.
- Garde-fous: pas d'`InMemoryHybridSearch` dans le gate réel; pas de succès vide; pas de candidat sans provenance; pas de remplacement par fixture.

## Blocages Ou Préconditions

- État GREEN/RED connu: le rapport V1 garde KA en écart différé; T-017 doit produire des versions canoniques réelles avant indexation.
- Présence des milestones amont dans master: M-003 à M-013 sont présents dans `master`; les décisions de projection régénérable et de métriques KA restent applicables.
- Décisions manquantes: aucune si les services d'indexation locaux existants sont utilisés; créer une ADR seulement si la topologie ou l'autorité de stockage de KA change.
- Risques: Qdrant indisponible; embeddings ou reranker non déclarés; rappel insuffisant masqué; candidats sans page; mélange entre index réel et index mémoire.

## Tâches

### T-018 - Construire et interroger une projection KA réelle

- But métier: prouver que la recherche retrouve les bonnes pages depuis les versions canoniques.
- Portée DDD: KA, projection de connaissance, embeddings, index hybride, reranking, provenance et métriques de rappel.
- Scénario BDD:
  - Given une version canonique publiée d'un PDF réel.
  - When KA construit l'index et exécute les questions annotées.
  - Then les candidats retournés portent un `SourceLocator` résoluble et le rappel attendu est mesuré.
- Tests d'acceptation à écrire: `uv run --locked gate`.
- Tests unitaires à écrire: projection absente, index stale, candidat sans locator, score sans trace, page attendue non retrouvée, Qdrant indisponible, embeddings non déclarés, reranker remplacé silencieusement.
- Implémentation attendue: brancher l'exécution de gate sur l'index réel et les services réels d'embedding et de reranking déclarés dans la topologie locale.
- Invariants et garde-fous: pas d'`InMemoryHybridSearch` dans le gate réel; pas de succès vide; pas de candidat sans provenance ouvrable; aucun fallback vers recherche mémoire.
- Dépendances: T-017, services d'indexation locaux, décisions KA existantes, `docs/governance/m012_v1_gap_report.md`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m013): couvrir recherche reelle sur corpus`
- Commit GREEN: `feat(m013): interroger projection reelle`
