# T-010 - Relier M-006 aux métriques, à la traçabilité et aux gates

## Milestone
- Nom: M-006 - Claims vérifiables.
- Source: plan M-006 et spécification v4.1, sections métriques de gouvernance des preuves, traçabilité et critères de définition d'achèvement.
- Objectif métier: rendre la livraison M-006 vérifiable, mesurable et rattachée aux ADR.

## Contexte DDD
- Domaine: gouvernance des preuves.
- Bounded context: EG, avec preuves de gouvernance transverse.
- Objectif métier: publier les signaux permettant d'auditer claims vérifiés, rejetés, en revue, sans preuve directe et supersédés.
- Langage ubiquitaire: taux de claims vérifiés, proportion sans preuve directe, distribution des verdicts, groupes de dépendance, taux de supersession, délai de vérification, matrice de traçabilité.
- Invariants critiques: chaque exigence M-006 possède un test et une commande; les métriques n'exposent pas le contenu documentaire; les ADR applicables sont explicites.
- Garde-fous: pas de compteur dérivé de logs de payload; pas de statut `Couvert` sans commande GREEN; pas de métrique qui mélange mention documentaire et confirmation indépendante.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-009 attendue GREEN.
- Présence des milestones amont dans master: M-004 et M-005 requis et présents.
- Décisions manquantes: aucune pour les métriques initiales; ADR requise si une politique de rétention ou d'observabilité durable change.
- Risques: traçabilité incomplète; signaux d'audit exposant des claims complets; gate M-006 non enrôlé dans `uv run --locked gate`.

## Tâches
### T-010 - Relier M-006 aux métriques, à la traçabilité et aux gates
- But métier: prouver que les claims vérifiables sont livrés avec leurs preuves, métriques et validations reproductibles.
- Portée DDD: métriques applicatives EG, matrice de traçabilité M-006, enrôlement des validators, signaux d'audit sans payload documentaire.
- Scénario BDD:
  - Given les comportements M-006 sont implémentés et testés.
  - When la matrice de traçabilité et les gates sont exécutés.
  - Then chaque exigence M-006 est rattachée à un test GREEN, une commande de validation et une ADR ou justification explicite.
- Tests d'acceptation à écrire: `uv run --locked gate`, couvrant exigences M-006, métriques EG et enrôlement des validators.
- Tests unitaires à écrire: tests de calcul des métriques sans payload, compteur de verdicts, proportion sans preuve directe, groupes de dépendance, supersession et délai de vérification.
- Implémentation attendue: créer les métriques EG, mettre à jour `docs/traceability/matrix.md`, enrôler les validations M-006 dans `uv run --locked gate` et `uv run --locked gate`, puis produire les preuves GREEN finales.
- Invariants et garde-fous: aucune métrique contenant texte de claim complet; aucun statut de traçabilité sans test; aucune validation M-006 hors gates de dépôt.
- Dépendances: T-009; ADR-006; ADR-010; DDD-ADR-005; DDD-ADR-010; `docs/governance/definition_of_done.md`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m006): couvrir tracabilite metriques gates`
- Commit GREEN: `test(m006): relier metriques tracabilite gates`
