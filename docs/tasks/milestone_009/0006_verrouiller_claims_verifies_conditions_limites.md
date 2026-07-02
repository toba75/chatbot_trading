# T-006 - Verrouiller les claims vérifiés avec conditions et limites

## Milestone
- Nom: M-009 - Recherche approfondie multi-sources.
- Source: plan M-009, spécification v4.1 sections EG et RA, et contrats `VerifiedClaimRef`.
- Objectif métier: comparer uniquement des affirmations vérifiées dont la portée, les conditions et les limites restent disponibles.

## Contexte DDD
- Domaine: gouvernance des preuves consommée par recherche approfondie.
- Bounded context: RA consommant EG par contrat publié.
- Objectif métier: utiliser les claims vérifiés comme unités comparables sans lire ni muter le registre interne EG.
- Langage ubiquitaire: `VerifiedClaimRef`, claim vérifié, portée, conditions, limites, dépendances, version de claim, catalogue EG.
- Invariants critiques: une affirmation sans preuve directe ne devient pas `VERIFIED`; les conditions et limites d'un claim sont conservées; RA verrouille exactement les versions utilisées.
- Garde-fous: aucun accès au stockage interne EG; aucune comparaison de claims sans portée; aucune mutation de claim depuis RA; aucun élargissement silencieux de version.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-005 terminé.
- Présence des milestones amont dans master: M-006 présent avec claims vérifiables et relations de portée.
- Décisions manquantes: aucune si RA consomme seulement `VerifiedClaimCatalog`; ADR requise si RA devient propriétaire d'un graphe durable de claims.
- Risques: comparer des claims non vérifiés; perdre les dépendances entre sources; utiliser la dernière version disponible au lieu de la version scellée.

## Tâches
### T-006 - Verrouiller les claims vérifiés avec conditions et limites
- But métier: fonder la comparaison multi-sources sur des claims vérifiés et versionnés.
- Portée DDD: port `VerifiedClaimCatalog`, verrouillage `(claim_id, claim_version)`, conservation des conditions, limites, dépendances et evidence refs admises dans le `EvidenceSet`.
- Scénario BDD:
  - Given deux preuves candidates produisent des claims vérifiés avec horizons et limites différents.
  - When RA prépare l'analyse multi-sources.
  - Then les versions exactes des claims, leurs conditions, leurs limites et leurs preuves admises sont verrouillées dans le cas de recherche.
- Tests d'acceptation à écrire: `tests/m009/validate_verified_claim_locking_acceptance.ps1`, qui échoue tant que RA ne verrouille pas les versions de claims vérifiés consommées.
- Tests unitaires à écrire: tests pour claim non vérifié, version absente, version différente, condition absente, limite absente, evidence ref hors `EvidenceSet`, dépendance manquante et lecture de stockage EG interdite.
- Implémentation attendue: étendre les DTO RA de claims vérifiés, enrichir le `EvidenceSet` ou le `ResearchCase` avec les versions de claims utilisées et adapter le port `VerifiedClaimCatalog` sans dépendance au registre interne EG.
- Invariants et garde-fous: aucune comparaison sans version; aucune preuve non admise exposée; aucune mutation EG; aucun fallback vers un claim plus récent.
- Dépendances: T-005; M-006; `VerifiedClaimRef`; `VerifiedClaimCatalog`; `EvidenceSet`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_verified_claim_locking_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_verified_claim_locking_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m009): couvrir verrouillage claims verifies`
- Commit GREEN: `feat(m009): verrouiller claims verifies`

