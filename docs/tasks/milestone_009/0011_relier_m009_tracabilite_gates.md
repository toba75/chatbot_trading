# T-011 - Relier M-009 à la traçabilité et aux gates

## Milestone
- Nom: M-009 - Recherche approfondie multi-sources.
- Source: plan M-009, spécification v4.1 sections 20 et 21, convention des tâches, et définition d'achèvement transverse.
- Objectif métier: clôturer M-009 avec des preuves de conformité auditables.

## Contexte DDD
- Domaine: gouvernance d'achèvement de la recherche approfondie.
- Bounded contexts: RA principalement, EG et CV par intégration.
- Objectif métier: démontrer que la recherche approfondie multi-sources est spécifiée, testée, implémentée, observable et reliée aux décisions d'architecture applicables.
- Langage ubiquitaire: matrice de traçabilité, gate, preuve d'exécution, exigence M-009, métrique de couverture, `ResearchCase`, `EvidenceSet`, contradiction, lacune, endpoint approfondi.
- Invariants critiques: chaque exigence M-009 possède test, commande, ADR ou justification; les tests M-009 sont enrôlés dans `uv run --locked gate`; `uv run --locked gate` enrôle la spécification M-009; les frontières RA/EG/CV restent contrôlées.
- Garde-fous: aucune exigence sans test; aucune gate ignorée après l'endpoint; aucune trace contenant payload sensible; aucune modification silencieuse d'ADR acceptée.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 à T-010 terminées.
- Présence des milestones amont dans master: M-008 présent.
- Décisions manquantes: aucune si les ADR existantes sont appliquées; toute décision de remplacement doit créer une nouvelle ADR et mettre à jour `docs/adr/index.md`.
- Risques: oublier l'enrôlement global des tests M-009; laisser CV router un mode sans gate RA; ne pas revalider les frontières d'architecture après intégration EG/CV.

## Tâches
### T-011 - Relier M-009 à la traçabilité et aux gates
- But métier: prouver que M-009 est terminé, vérifiable et conforme aux règles projet.
- Portée DDD: matrice `docs/traceability/matrix.md`, enrôlement `uv run --locked gate`, enrôlement `uv run --locked gate`, journal de milestone, validateurs M-009, preuves de métriques, contrôles d'architecture RA/EG/CV et documentation de clôture.
- Scénario BDD:
  - Given les comportements M-009 sont implémentés et testés.
  - When la matrice de traçabilité et les gates sont exécutées.
  - Then chaque exigence M-009 est rattachée à un test GREEN, une commande de validation, une ADR ou justification explicite, et une preuve d'observabilité sans payload sensible.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue tant que M-009 n'est pas relié à la matrice et aux gates.
- Tests unitaires à écrire: tests du validateur de traçabilité M-009 pour exigence absente, test absent, commande absente, ADR absente, métrique absente, endpoint absent, payload sensible et gate non enrôlée.
- Implémentation attendue: compléter `docs/traceability/matrix.md`, enrôler tous les tests et validateurs M-009 dans les scripts de gate, produire ou compléter `docs/tasks/milestone_009/journal.md`, vérifier les frontières d'architecture et documenter les commandes finales.
- Invariants et garde-fous: pas de clôture sans test global GREEN; pas de trace sensible; pas d'ADR modifiée silencieusement; pas de dépendance intercontexte non autorisée.
- Dépendances: T-001 à T-010; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `docs/traceability/matrix.md`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `git diff --check`.
- Commit RED: `test(m009): couvrir tracabilite gates`
- Commit GREEN: `chore(m009): relier tracabilite gates`
