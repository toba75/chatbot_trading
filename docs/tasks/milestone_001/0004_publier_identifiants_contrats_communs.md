# T-004 - Publier les identifiants opaques et versions de contrats

## Milestone
- Nom: M-001 - Frontières DDD et contrats publiés.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, livrable `contrats publiés versionnés`, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 2, 4, 15, 20 et 21.
- Objectif métier: garantir que les contrats intercontextes utilisent des identifiants de domaine stables et des versions explicites.

## Contexte DDD
- Domaine: langage publié intercontexte.
- Bounded context: transverse, consommé par SP, KA, EG, RA, CV, SD et EX.
- Objectif métier: empêcher qu'un chemin de fichier, un titre, un hash de prompt ou un identifiant de projection devienne une identité métier principale.
- Langage ubiquitaire: identifiant opaque, `schema_version`, contrat publié, compatibilité en lecture, fixture de contrat, version d'artefact.
- Invariants critiques: chaque contrat a une version; chaque identifiant respecte son préfixe de domaine; aucun identifiant technique n'est accepté comme identité métier principale.
- Garde-fous: aucune conversion implicite de chaîne libre; aucun préfixe par défaut; aucune compatibilité déclarée sans fixture.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 doit être GREEN; T-002 fournit le catalogue de contrats attendu.
- Présence des milestones amont dans master: M-000 est présent dans `master`.
- Décisions manquantes: aucune ADR nouvelle si les règles appliquent les identifiants et contrats publiés de la spécification v4.1.
- Risques: construire les contrats métier avec des types primitifs ambigus; accepter un identifiant Qdrant comme identité de domaine; oublier la politique de versioning.

## Tâches
### T-004 - Publier les identifiants opaques et versions de contrats
- But métier: fournir les primitives contractuelles communes qui rendent les échanges stables entre contextes.
- Portée DDD: identifiants `DOC`, `CSRC`, `CVER`, `PROJ`, `CLM`, `VER`, `DEP`, `RSC`, `EVS`, `ANS`, `CONV`, `TURN`, `STRAT`, `SVER`, `EXP` et `DATA`, plus version de schéma.
- Scénario BDD:
  - Given un contexte publie un contrat pour un autre contexte.
  - When le contrat est sérialisé et validé.
  - Then chaque identité métier est opaque, préfixée, versionnée et indépendante des chemins ou identifiants techniques.
- Tests d'acceptation à écrire: un test de contrat qui sérialise une fixture minimale versionnée et refuse un contrat sans `schema_version` ou avec identifiant technique comme identité principale.
- Tests unitaires à écrire: tests de création et parsing strict des identifiants, refus de préfixe inconnu, refus de valeur vide, refus de chemin de fichier et round-trip de version de schéma.
- Implémentation attendue: créer les primitives de contrats partagées, leurs fixtures et la politique de versioning de lecture compatible.
- Invariants et garde-fous: aucune valeur par défaut pour `schema_version`; aucune correction automatique de préfixe; aucun fallback vers chaîne brute.
- Dépendances: T-002; T-003; section 2 de la spécification v4.1.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_contract_identity_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_contract_identity_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`.
- Commit RED: `test(m001): couvrir les identifiants opaques des contrats`.
- Commit GREEN: `feat(m001): publier les identifiants opaques versionnés`.
