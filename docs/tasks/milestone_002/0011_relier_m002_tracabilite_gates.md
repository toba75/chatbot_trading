# T-011 - Relier M-002 à la traçabilité et aux gates

## Milestone
- Nom: M-002 - Plateforme locale sûre.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, sortie attendue M-002, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 20 et 21.
- Objectif métier: prouver que la plateforme locale sûre est couverte par tests, ADR, code, configuration et gates standard.

## Contexte DDD
- Domaine: gouvernance de livraison et traçabilité de plateforme.
- Bounded context: transverse, avec preuves pour `platform`.
- Objectif métier: rendre M-002 clôturable seulement si les règles de topologie, gateway, outbox, jobs, sécurité et observabilité sont reliées à des preuves vérifiables.
- Langage ubiquitaire: matrice de traçabilité, exigence M-002, gate, test de contrat, test de processus, test d'architecture, ADR, définition de terminé.
- Invariants critiques: chaque exigence M-002 a une ligne de matrice; chaque ligne pointe vers une commande exécutable; chaque décision structurante cite une ADR; les gates `test` et `lint` restent GREEN.
- Garde-fous: ne pas marquer `Couvert` sans test exécuté; ne pas citer une ADR absente; ne pas ignorer une exigence de sécurité réseau.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 à T-010 doivent être GREEN avant clôture.
- Présence des milestones amont dans master: M-000 et M-001 sont présents dans `master`.
- Décisions manquantes: à réévaluer après T-010; toute décision structurante nouvelle doit créer une ADR depuis `docs/adr/TEMPLATE.md` et mettre à jour `docs/adr/index.md`.
- Risques: oublier la trace d'un contrôle réseau; référencer un test qui n'exécute pas la gate; clôturer M-002 sans preuve de panne Spark explicite.

## Tâches
### T-011 - Relier M-002 à la traçabilité et aux gates
- But métier: fournir la preuve finale que la plateforme locale peut exécuter traitements, jobs et inférences sans exposition publique ni panne masquée.
- Portée DDD: matrice `REQ-M002-*`, journal M-002, définition de terminé, ADR applicables, gates PowerShell et contrôles d'architecture.
- Scénario BDD:
  - Given les composants M-002 sont implémentés et testés.
  - When les gates de clôture sont exécutées.
  - Then chaque exigence M-002 est reliée à une preuve et la clôture est refusée si un test, une ADR ou une commande manque.
- Tests d'acceptation à écrire: un test de traçabilité M-002 qui échoue tant qu'une exigence de plateforme n'a pas de ligne dans `docs/traceability/matrix.md` avec test, commande, code ou configuration, et ADR ou justification.
- Tests unitaires à écrire: tests du validateur de matrice pour statuts M-002, preuves de configuration, preuves de sécurité réseau, ADR multiples et commandes introuvables.
- Implémentation attendue: mettre à jour `docs/traceability/matrix.md`, compléter les validateurs si nécessaire et documenter la clôture dans `docs/tasks/milestone_002/journal.md`.
- Invariants et garde-fous: aucune preuve manquante; aucune commande non exécutable; aucun statut `Couvert` sans artefact; aucune modification silencieuse d'une ADR acceptée.
- Dépendances: T-001; T-002; T-003; T-004; T-005; T-006; T-007; T-008; T-009; T-010; `docs/governance/definition_of_done.md`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_definition_of_done.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m002): couvrir la tracabilite plateforme`.
- Commit GREEN: `docs(m002): relier m002 aux gates et a la tracabilite`.
