# T-007 - Valider les sauvegardes chiffrées et la restauration

## Milestone
- Nom: M-013 - Durcissement et acceptation V1.
- Source: livrables M-013 `sauvegardes chiffrées et test de restauration`, critères V1 et règles de propriété des données.
- Objectif métier: garantir que les artefacts V1 peuvent être restaurés localement sans perte de preuve, d'identité ni de séparation des plans physiques.

## Contexte DDD
- Domaine: durcissement opérationnel et acceptation V1.
- Bounded context: plateforme locale, avec données possédées par SP, KA, EG, RA, CV, SD, EX et EV.
- Objectif métier: restaurer un état V1 auditable tout en conservant les identifiants stables, les artefacts immuables et les résultats défavorables.
- Langage ubiquitaire: sauvegarde chiffrée, manifeste de sauvegarde, restauration, vérification d'intégrité, clé hors dépôt, original immuable, projection régénérable, résultat conservé.
- Invariants critiques: la sauvegarde exclut les secrets en clair; la restauration vérifie les hashes; les projections régénérables sont identifiées; les résultats négatifs et supersédés restent consultables; le Spark ne reçoit pas de stockage métier.
- Garde-fous: pas de clé dans Git; pas de sauvegarde partielle déclarée complète; pas de restauration qui écrase silencieusement; pas de corpus copié sur Spark; pas de suppression de résultat défavorable.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-006.
- Présence des milestones amont dans master: M-012 présent dans `master`.
- Décisions manquantes: ADR requise si le format de sauvegarde ou la politique de chiffrement devient une décision structurante durable.
- Risques: valider seulement la création d'archive; oublier Qdrant ou les artefacts canoniques; restaurer sans vérifier les liens de traçabilité; exposer une clé ou un secret dans les logs.

## Tâches
### T-007 - Valider les sauvegardes chiffrées et la restauration
- But métier: prouver que la V1 personnelle est exploitable après incident local.
- Portée DDD: manifestes de sauvegarde, périmètre des données par contexte, chiffrement, restauration dans un environnement isolé, contrôle d'intégrité, projections régénérables, rapports de restauration et preuve de non-exposition Spark.
- Scénario BDD:
  - Given une instance V1 contient corpus, versions canoniques, claims, réponses, conversations, stratégies, expériences, décisions et écarts V1.
  - When une sauvegarde chiffrée est restaurée dans un environnement local isolé.
  - Then les identifiants stables, artefacts immuables, résultats négatifs et décisions restent vérifiables sans secret en clair ni stockage métier sur Spark.
- Tests d'acceptation à écrire: `tests/m013/validate_backup_restore_acceptance.ps1`, qui échoue si une catégorie d'artefact V1 manque, si la clé est versionnée, si un hash restauré diverge, si un résultat négatif disparaît, si une projection régénérable est traitée comme source ou si la restauration exige le Spark pour les données métier.
- Tests unitaires à écrire: tests de `scripts/validate_m013_backup_restore.ps1` pour manifeste incomplet, archive non chiffrée, secret détecté, catégorie de contexte absente, hash absent, projection non marquée régénérable, restauration destructive, rapport sans commande et chemin Spark interdit.
- Implémentation attendue: créer le contrat de manifeste de sauvegarde, le script ou validateur de restauration M-013, les fixtures de restauration, `docs/governance/m013_backup_restore_drill.md`, les tests d'intégrité et l'enrôlement dans les gates.
- Invariants et garde-fous: aucune clé ou secret dans Git; aucune donnée métier sur Spark; aucune restauration sans vérification; aucune suppression de versions négatives ou supersédées; aucune projection traitée comme autorité.
- Dépendances: T-006; SP; KA; EG; RA; CV; SD; EX; EV; DDD-ADR-006; DDD-ADR-010.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_backup_restore_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_backup_restore_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_backup_restore.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m013): couvrir restauration sauvegardes`
- Commit GREEN: `feat(m013): valider sauvegardes restauration`
