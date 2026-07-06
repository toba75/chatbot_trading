# T-010 - Publier les runbooks et la documentation utilisateur

## Milestone
- Nom: M-013 - Durcissement et acceptation V1.
- Source: livrables M-013 `runbooks d'exploitation locale` et `documentation utilisateur`, critères V1 et définition de terminé.
- Objectif métier: permettre à l'utilisateur d'exploiter la V1 localement, comprendre les statuts et agir sur les incidents sans inventer de comportement alternatif.

## Contexte DDD
- Domaine: durcissement opérationnel et acceptation V1.
- Bounded context: documentation produit et exploitation locale, couvrant tous les contextes.
- Objectif métier: publier les procédures concrètes pour lancer, arrêter, sauvegarder, restaurer, auditer, diagnostiquer et utiliser les parcours V1.
- Langage ubiquitaire: runbook, procédure locale, incident, restauration, écart V1, statut documentaire, mode conversationnel, recherche approfondie, stratégie candidate, expérience reproductible.
- Invariants critiques: chaque runbook référence une commande ou une preuve; les limitations V1 sont visibles; les écarts non acceptés sont nommés; les procédures ne décrivent aucun fallback silencieux; les secrets restent hors documentation.
- Garde-fous: pas de promesse de rentabilité; pas de procédure qui contourne les gates; pas de commande destructive sans précondition explicite; pas d'instruction de publier un service interne.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-009.
- Présence des milestones amont dans master: M-012 présent dans `master`.
- Décisions manquantes: aucune si les runbooks documentent les décisions existantes; ADR requise si une procédure introduit une nouvelle topologie ou politique.
- Risques: documentation marketing au lieu de procédures opérables; oubli des écarts V1; procédure de récupération non testée; divulgation de secrets ou chemins locaux sensibles.

## Tâches
### T-010 - Publier les runbooks et la documentation utilisateur
- But métier: rendre la V1 exploitable par son utilisateur cible après durcissement.
- Portée DDD: démarrage local, arrêt, sauvegarde, restauration, audit réseau, panne Spark, monitoring, ingestion PDF, conversation, recherche approfondie, stratégie, backtest, statuts publics, limites et écarts V1.
- Scénario BDD:
  - Given la V1 possède des gates, sauvegardes, monitoring et décisions d'écarts.
  - When l'utilisateur suit les runbooks et la documentation V1.
  - Then chaque action critique référence une commande vérifiée, expose les statuts attendus et ne propose aucun fallback silencieux.
- Tests d'acceptation à écrire: `tests/m013/validate_runbooks_user_docs_acceptance.ps1`, qui échoue si un runbook critique manque, si une commande référencée n'existe pas, si un écart V1 non accepté est absent, si une procédure expose Spark publiquement, si une sauvegarde n'est pas reliée au drill ou si une promesse de rentabilité apparaît.
- Tests unitaires à écrire: tests de `scripts/validate_m013_runbooks.ps1` pour document absent, commande absente, secret détecté, fallback textuel, procédure destructive sans précondition, écart non mentionné, statut public absent, runbook panne Spark absent et lien de preuve cassé.
- Implémentation attendue: créer les runbooks sous `docs/runbooks/`, créer ou compléter la documentation utilisateur V1, publier `docs/governance/m013_documentation_index.md`, créer le validateur documentaire M-013 et relier les documents à la traçabilité.
- Invariants et garde-fous: aucun secret; aucune commande destructive sans garde-fou; aucun fallback; aucune promesse financière; aucun service interne publié; aucune limitation V1 cachée.
- Dépendances: T-009; `docs/governance/m013_security_audit.md`; `docs/governance/m013_backup_restore_drill.md`; `docs/governance/m013_v1_gap_decisions.md`; `docs/governance/m013_local_monitoring.md`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_runbooks_user_docs_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_runbooks_user_docs_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_runbooks.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m013): couvrir runbooks documentation v1`
- Commit GREEN: `docs(m013): publier runbooks documentation v1`
