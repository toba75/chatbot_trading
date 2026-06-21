# T-005 - Définir l'achèvement transverse vérifiable

## Milestone
- Nom: M-000 - Gouvernance exécutable.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, livrable `définition d'achèvement transverse`, et spécification v4.1, sections 20 et 21.
- Objectif métier: donner à chaque milestone une règle de clôture vérifiable, orientée BDD/TDD et traçabilité.

## Contexte DDD
- Domaine: gouvernance de livraison.
- Bounded context: transverse.
- Objectif métier: empêcher qu'un milestone soit déclaré terminé sans preuves de scénario, tests, validation, ADR et traçabilité.
- Langage ubiquitaire: définition de terminé, gate, scénario d'acceptation, test RED, test GREEN, lint, ADR, traçabilité.
- Invariants critiques: une tâche terminée possède une preuve RED et une preuve GREEN; une décision structurante possède une ADR; une exigence touchée est reliée à la matrice; aucune validation échouée n'est ignorée.
- Garde-fous: checklist contrôlable; champs obligatoires; refus d'une clôture sans preuve.

## Blocages Ou Préconditions
- État GREEN/RED connu: aucune définition d'achèvement transverse dédiée n'est visible dans le dépôt.
- Présence des milestones amont dans master: M-000 n'a aucune dépendance amont.
- Décisions manquantes: aucune ADR requise si la définition reprend les règles déjà présentes dans AGENTS et la spécification.
- Risques: créer une checklist décorative non exécutable; accepter un GREEN logiciel qui masque un test scientifique ou documentaire manquant.

## Tâches
### T-005 - Définir l'achèvement transverse vérifiable
- But métier: formaliser une définition de terminé qui protège les futurs milestones contre les validations partielles.
- Portée DDD: gouvernance transverse; applicable aux tâches SP, KA, EG, RA, CV, SD, EX et plateforme.
- Scénario BDD:
  - Given une tâche de milestone candidate à la clôture.
  - When la définition d'achèvement transverse est évaluée.
  - Then les preuves BDD, ATDD, TDD, ADR, traçabilité, tests et lint sont présentes ou la clôture est refusée explicitement.
- Tests d'acceptation à écrire: un test qui échoue si la définition d'achèvement ne contient pas les gates BDD, ATDD, TDD, commit RED, commit GREEN, ADR, traçabilité, tests et lint.
- Tests unitaires à écrire: tests du validateur de sections obligatoires, de la liste des gates et du refus des sections vides.
- Implémentation attendue: créer un document de définition d'achèvement transverse et un validateur strict; intégrer les critères de la section 21 sans redéfinir les ADR acceptées.
- Invariants et garde-fous: aucun milestone ne peut être marqué terminé si la validation M-000 échoue; pas de dérogation implicite; toute exception doit être documentée comme blocage ou décision préalable.
- Dépendances: T-001; T-004; AGENTS; section 20 et section 21 de la spécification.
- Commandes de validation: future commande `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_definition_of_done.ps1`; puis `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1` après T-006.
- Commit RED: `test(m000): couvrir la définition d'achèvement transverse`.
- Commit GREEN: `feat(m000): publier l'achèvement transverse vérifiable`.
