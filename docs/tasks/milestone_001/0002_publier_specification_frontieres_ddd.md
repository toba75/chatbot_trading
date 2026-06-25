# T-002 - Publier la spécification des frontières DDD

## Milestone
- Nom: M-001 - Frontières DDD et contrats publiés.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M-001 - Frontières DDD et contrats publiés`, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 2, 4, 13, 14, 15 et 21.
- Objectif métier: donner aux sept bounded contexts une frontière explicite et un langage publié stable.

## Contexte DDD
- Domaine: langage publié et conception de frontières intercontextes.
- Bounded context: transverse, avec SP, KA, EG, RA, CV, SD et EX comme contextes concernés.
- Objectif métier: transformer la carte DDD normative en spécification exécutable avant les contrats et modules.
- Langage ubiquitaire: bounded context, responsabilité exclusive, langage publié, propriétaire de données, contrat versionné, façade applicative, anti-corruption layer.
- Invariants critiques: chaque contexte possède une responsabilité exclusive; un contrat expose le minimum nécessaire; un contexte ne lit pas le modèle interne d'un autre contexte.
- Garde-fous: partir des sections canoniques de la spécification v4.1; ne pas inventer de contexte; ne pas créer de persistance concrète avant le contrat de domaine.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend du retour GREEN de T-001; le RED de `validate_task_system.ps1` doit être traité avant clôture de cette tâche.
- Présence des milestones amont dans master: M-000 est présent dans `master` avec les tâches, ADR, matrice et gates M-000.
- Décisions manquantes: aucune ADR nouvelle n'est requise si la tâche matérialise DDD-ADR-001, DDD-ADR-002, DDD-ADR-003 et les décisions existantes sans en changer le sens.
- Risques: recopier la spécification sans critères testables; mélanger contexte métier et adaptateur de plateforme; publier une frontière sans responsabilité propriétaire.

## Tâches
### T-002 - Publier la spécification des frontières DDD
- But métier: fournir une référence M-001 détaillée qui relie responsabilités, relations, contrats, invariants et critères d'acceptation.
- Portée DDD: context map, glossaire M-001, responsabilités exclusives, relations SP vers KA et EG, KA vers RA, EG vers RA et SD, RA vers SD, SD vers EX, CV vers RA/SD/EX.
- Scénario BDD:
  - Given les sept bounded contexts sont définis dans la spécification v4.1.
  - When la spécification M-001 est publiée.
  - Then chaque communication intercontexte nomme son contrat publié, son producteur, son consommateur et le modèle interne qui reste interdit.
- Tests d'acceptation à écrire: un test documentaire qui échoue tant que la spécification M-001 ne liste pas les sept contextes, leurs responsabilités exclusives, leurs relations et les contrats attendus.
- Tests unitaires à écrire: tests du parseur de spécification refusant un contexte manquant, une relation sans contrat, un propriétaire de données vide ou une relation non présente dans la context map v4.1.
- Implémentation attendue: créer `docs/specs/m001_frontieres_ddd_contrats_publies.md` avec contexte DDD, langage ubiquitaire, contrats, règles de dépendance, invariants et critères d'acceptation M-001.
- Invariants et garde-fous: aucune relation implicite; aucune table ou classe interne citée comme contrat; aucune extension de périmètre vers UI, connecteurs externes ou persistance opérationnelle.
- Dépendances: T-001; `docs/specs/plan_implementation_milestones_workstreams.md`; `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`; `docs/adr/index.md`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_m001_specification_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_m001_specification_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`.
- Commit RED: `test(m001): couvrir la spécification des frontières ddd`.
- Commit GREEN: `docs(m001): publier la spécification des frontières ddd`.
