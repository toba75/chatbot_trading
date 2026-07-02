# T-005 - Résoudre les claims vérifiés et les dépendances indépendantes

## Milestone
- Nom: M-009 - Recherche approfondie multi-sources.
- Source: spécification v4.1 sections 7, 8 et 12, ADR-006, DDD-ADR-005 et spécification M-009 publiée par T-002.
- Objectif métier: fonder l'analyse approfondie sur des claims vérifiés et sur des confirmations indépendantes, pas sur le nombre brut de mentions.

## Contexte DDD
- Domaine: gouvernance des preuves consommée par recherche approfondie.
- Bounded context: RA consommant EG par contrat public.
- Objectif métier: intégrer claims, preuves admissibles, groupes de dépendance et versions de vérification sans lire le registre EG interne.
- Langage ubiquitaire: claim vérifié, `VerifiedClaimRef`, preuve admissible, groupe de dépendance, confirmation indépendante, portée, limite, relation de claims, source primaire, source secondaire.
- Invariants critiques: seuls les claims `VERIFIED` peuvent soutenir une synthèse finale; chaque preuve acceptée doit être attachée au claim publié; les groupes de dépendance sont explicites; un document secondaire ne compte pas comme confirmation indépendante de l'étude primaire.
- Garde-fous: aucune lecture directe de table EG; aucune confirmation déduite de la fréquence de citation; aucune perte de portée, modalité ou limite du claim.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-004 terminé.
- Présence des milestones amont dans master: M-008 présent.
- Décisions manquantes: aucune si EG reste propriétaire du registre; ADR requise si RA devait matérialiser un registre de claims concurrent.
- Risques: dupliquer la logique EG dans RA; compter plusieurs éditions comme preuves indépendantes; élargir une conclusion au-delà des claims vérifiés.

## Tâches
### T-005 - Résoudre les claims vérifiés et les dépendances indépendantes
- But métier: qualifier l'ensemble de preuves approfondi par claims vérifiés, dépendances et confirmations indépendantes.
- Portée DDD: port `VerifiedClaimCatalog`, lecture publique EG, `DependencyGroup`, `SourceIndependencePolicy`, agrégation RA des claims par obligation, conservation de `claim_version`, `verification_case_id` et `dependency_group_id`.
- Scénario BDD:
  - Given trois documents reprennent la même étude primaire pour soutenir un claim.
  - When RA résout les claims vérifiés et leurs dépendances.
  - Then une seule confirmation indépendante est comptée et la synthèse conserve la dépendance documentaire.
- Tests d'acceptation à écrire: `tests/m009/validate_verified_claim_dependency_resolution_acceptance.ps1`, qui échoue tant que RA ne publie pas les dépendances indépendantes associées au jeu de preuves.
- Tests unitaires à écrire: tests de résolution pour claim non vérifié, evidence_ref non attachée, groupe de dépendance absent, groupe dupliqué, version de claim absente, confirmation indépendante incohérente et lecture EG interne interdite.
- Implémentation attendue: créer ou étendre un composant RA de résolution publique des claims, utiliser `ReadPublicClaimHandler` ou le port EG existant, produire une structure de dépendances RA consultable par la synthèse et préserver les invariants M-006/M-007.
- Invariants et garde-fous: seuls les claims vérifiés soutiennent la conclusion; aucune confirmation par fréquence brute; aucune mutation EG depuis RA; aucune perte de version.
- Dépendances: T-004; `app/evidence_governance/application/read_claims.py`; `app/evidence_governance/domain/dependency_group.py`; `app/research_answering/application/collect_evidence.py`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_verified_claim_dependency_resolution_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_verified_claim_dependency_resolution_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m006\validate_dependency_group_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`.
- Commit RED: `test(m009): couvrir dependances claims verifiees`
- Commit GREEN: `feat(m009): resoudre dependances claims verifiees`
