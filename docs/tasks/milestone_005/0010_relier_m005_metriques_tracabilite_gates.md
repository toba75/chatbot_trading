# T-010 - Relier M-005 aux métriques, à la traçabilité et aux gates

## Milestone
- Nom: M-005 - Projection de connaissance recherchable.
- Source: livrables M-005 métriques Recall@k, MRR, nDCG initiales, recherche renvoyant scores, citations et provenance, gates de gouvernance.
- Objectif métier: clôturer M-005 avec des preuves exécutables et une qualité de recherche mesurable.

## Contexte DDD
- Domaine: accès aux connaissances et gouvernance d'exécution.
- Bounded context: KA, avec gates transverses.
- Objectif métier: prouver que la projection et la recherche sont traçables, mesurables et prêtes pour les contextes RA et EG.
- Langage ubiquitaire: Recall@k, MRR, nDCG, trace de recherche, preuve candidate, exigence couverte, gate GREEN.
- Invariants critiques: aucune exigence M-005 ne peut être déclarée couverte sans test, commande, code et ADR; les métriques initiales ne sont pas des seuils métier définitifs; les signaux ne contiennent pas de texte documentaire complet.
- Garde-fous: ne pas publier de clôture sans métriques initiales; ne pas qualifier la vérité d'une preuve candidate; ne pas modifier une ADR acceptée pour justifier un écart.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 à T-009 doivent être GREEN.
- Présence des milestones amont dans master: M-000 à M-004 requis pour la matrice de traçabilité complète.
- Décisions manquantes: ADR obligatoire si les seuils Recall/MRR/nDCG deviennent des objectifs d'acceptation V1 avant calibration M-012.
- Risques: métriques décoratives non reproductibles; exigences M-005 absentes de la matrice; logs contenant du contenu documentaire.

## Tâches
### T-010 - Relier M-005 aux métriques, à la traçabilité et aux gates
- But métier: rendre la sortie M-005 vérifiable avant que RA et EG consomment les preuves candidates.
- Portée DDD: matrice de traçabilité M-005, signaux d'audit KA, métriques initiales de recherche, validations PowerShell et enrôlement dans `scripts/test.ps1`.
- Scénario BDD:
  - Given les comportements M-005 sont implémentés et testés.
  - When les gates de clôture M-005 s'exécutent.
  - Then chaque exigence M-005 est reliée à une preuve et les métriques Recall@k, MRR et nDCG initiales sont publiées comme mesures non définitives.
- Tests d'acceptation à écrire: `tests/m005/validate_m005_traceability_acceptance.ps1`, couvrant exigences M-005, commandes, ADR, métriques et absence de contenu documentaire dans les signaux.
- Tests unitaires à écrire: tests du validateur de traçabilité M-005, calcul déterministe de métriques sur fixture, refus de métrique sans jeu de questions et refus de log contenant un passage complet.
- Implémentation attendue: mettre à jour `docs/traceability/matrix.md`, créer les signaux d'audit KA, publier les fixtures de mesure initiale, enrôler les tests M-005 dans `scripts/test.ps1` et vérifier `scripts/lint.ps1`.
- Invariants et garde-fous: aucun GREEN implicite; aucune métrique sans corpus/fixture identifiée; aucune donnée sensible ou texte intégral dans logs et métriques; aucune suppression de test existant pour réduire le coût de la gate.
- Dépendances: T-001 à T-009; ADR-005; ADR-006; ADR-010; DDD-ADR-004; DDD-ADR-008.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_m005_traceability_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_m005_traceability_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m005): couvrir la tracabilite de projection`
- Commit GREEN: `docs(m005): relier m005 aux gates et metriques`
