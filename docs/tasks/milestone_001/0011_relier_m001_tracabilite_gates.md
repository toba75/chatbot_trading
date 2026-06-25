# T-011 - Relier M-001 à la traçabilité et aux gates

## Milestone
- Nom: M-001 - Frontières DDD et contrats publiés.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, sortie attendue `l'architecture peut accueillir les comportements métier sans mélanger les modèles`, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 20 et 21.
- Objectif métier: prouver que les frontières, contrats et tests M-001 sont reliés aux exigences et décisions d'architecture.

## Contexte DDD
- Domaine: gouvernance de livraison et traçabilité de contrats DDD.
- Bounded context: transverse.
- Objectif métier: rendre M-001 clôturable seulement si les exigences, tests, code, documentation et ADR sont reliés.
- Langage ubiquitaire: matrice de traçabilité, exigence M-001, test de contrat, test d'architecture, ADR, gate, définition de terminé.
- Invariants critiques: chaque exigence M-001 touchée a une ligne de traçabilité; chaque ligne pointe vers un test et une commande; une absence d'ADR est justifiée; les gates standard restent GREEN.
- Garde-fous: ne pas déclarer M-001 terminé sur des tests isolés; ne pas ignorer `scripts/test.ps1` ou `scripts/lint.ps1`; ne pas modifier le sens d'une ADR acceptée.

## Blocages Ou Préconditions
- État GREEN/RED connu: toutes les tâches T-001 à T-010 doivent être GREEN avant clôture de cette tâche.
- Présence des milestones amont dans master: M-000 est présent dans `master`.
- Décisions manquantes: à réévaluer après T-010; toute décision structurante nouvelle doit créer une ADR depuis `docs/adr/TEMPLATE.md` et mettre à jour `docs/adr/index.md`.
- Risques: oublier une exigence de contrat dans la matrice; référencer un test qui n'exécute pas réellement la gate; accepter une couverture partielle sans statut explicite.

## Tâches
### T-011 - Relier M-001 à la traçabilité et aux gates
- But métier: fournir la preuve finale que M-001 a stabilisé les frontières DDD sans mélange de modèles.
- Portée DDD: traçabilité des exigences M-001, liens vers contrats, tests de contrat, tests d'architecture, ADR existantes ou nouvelles, définition de terminé transverse.
- Scénario BDD:
  - Given les contrats publiés et tests d'architecture M-001 sont implémentés.
  - When les gates de clôture sont exécutées.
  - Then chaque exigence M-001 est reliée à une preuve vérifiable et la clôture est refusée si une preuve manque.
- Tests d'acceptation à écrire: un test de traçabilité qui échoue tant qu'une exigence M-001 de contrat ou d'architecture n'a pas de ligne dans `docs/traceability/matrix.md`.
- Tests unitaires à écrire: tests du validateur de matrice pour statuts M-001, liens vers tests de contrat, liens vers code de contrat et justification ADR.
- Implémentation attendue: mettre à jour `docs/traceability/matrix.md`, compléter les validations de traçabilité si nécessaire et documenter les résultats de clôture dans `docs/tasks/milestone_001/journal.md`.
- Invariants et garde-fous: aucune ligne de matrice avec chemin introuvable; aucune commande non vérifiable; aucun statut `Couvert` sans test exécuté; aucun contournement de la définition d'achèvement.
- Dépendances: T-001; T-002; T-003; T-004; T-005; T-006; T-007; T-008; T-009; T-010; `docs/governance/definition_of_done.md`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_definition_of_done.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m001): couvrir la tracabilite des contrats publies`.
- Commit GREEN: `docs(m001): relier m001 aux gates et a la tracabilite`.
