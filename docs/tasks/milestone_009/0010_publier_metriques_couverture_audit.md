# T-010 - Publier les métriques de couverture et d'audit M-009

## Milestone
- Nom: M-009 - Recherche approfondie multi-sources.
- Source: spécification v4.1 sections 19, 20 et 21, plan M-009, et spécification M-009 publiée par T-002.
- Objectif métier: rendre observable la qualité de couverture et d'analyse sans journaliser le contenu complet des sources ou réponses.

## Contexte DDD
- Domaine: observabilité métier de la recherche approfondie.
- Bounded context: RA.
- Objectif métier: mesurer couverture, diversité, dépendances, contradictions et lacunes pour auditer les synthèses multi-sources.
- Langage ubiquitaire: métrique de couverture, diversité documentaire, groupe indépendant, contradiction, lacune, statut de support, trace, audit, payload sensible.
- Invariants critiques: les métriques ne contiennent pas le texte complet des preuves, prompts ou réponses; chaque métrique rattache un identifiant de recherche; les versions KA/EG utiles à l'audit sont référencées; les compteurs ne deviennent pas preuve scientifique.
- Garde-fous: aucun payload documentaire complet; aucune donnée personnelle inutile; aucune métrique qui transforme nombre de mentions en consensus; aucune trace sans corrélation.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-004 à T-009 terminées.
- Présence des milestones amont dans master: M-008 présent.
- Décisions manquantes: aucune pour métriques locales déterministes; ADR requise si une solution d'observabilité persistante externe est introduite.
- Risques: fuite de texte source dans les signaux; métriques non enrôlées dans traceability; confusion entre métriques produit et preuve documentaire.

## Tâches
### T-010 - Publier les métriques de couverture et d'audit M-009
- But métier: prouver qu'une recherche approfondie est observable, auditable et respectueuse de la confidentialité locale.
- Portée DDD: `DeepResearchMetricSnapshot`, couverture des obligations, diversité documentaire, groupes de dépendance, contradictions, lacunes, statuts de support, versions de projection, versions de claims, signaux d'audit sans payload sensible.
- Scénario BDD:
  - Given plusieurs recherches approfondies ont produit des statuts différents.
  - When les métriques M-009 sont publiées.
  - Then les signaux exposent couverture, diversité, contradictions, lacunes et statuts sans contenir les textes complets de sources, prompts ou réponses.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue tant que les métriques M-009 ne sont pas publiées et protégées contre les payloads sensibles.
- Tests unitaires à écrire: tests de snapshot pour obligation couverte, obligation manquante, diversité documentaire, groupes indépendants, contradiction bloquante, lacune, version KA/EG absente, payload sensible, compteur non déterministe et taux non fini.
- Implémentation attendue: créer `app/research_answering/application/deep_research_metrics.py`, produire `docs/governance/m009_deep_research_metrics.json`, enrichir les validateurs de trace sans exposer de contenu complet.
- Invariants et garde-fous: pas de prompt complet; pas de source complète; pas de réponse complète; pas de ratio non fini; pas de consensus déduit d'un compteur.
- Dépendances: T-004 à T-009; `app/research_answering/application/traceability_metrics.py`; `tests/m007/fixtures/m007_response_metrics_fixture.json`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m009): couvrir metriques recherche approfondie`
- Commit GREEN: `feat(m009): publier metriques recherche approfondie`
