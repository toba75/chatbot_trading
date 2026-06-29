# T-009 - Exposer les commandes de claims et de preuves

## Milestone
- Nom: M-006 - Claims vérifiables.
- Source: plan M-006 et spécification v4.1, endpoints `POST /v1/claims/extract`, `POST /v1/claims/{id}/verify` et `GET /v1/claims/{id}/evidence`.
- Objectif métier: rendre EG utilisable par les contextes aval sans exposer son modèle interne ni ses stockages.

## Contexte DDD
- Domaine: gouvernance des preuves.
- Bounded context: EG.
- Objectif métier: fournir des commandes explicites pour extraire, vérifier et consulter les preuves d'un claim.
- Langage ubiquitaire: `ExtractClaimsFromEvidenceHandler`, `VerifyClaimHandler`, `GetClaimEvidence`, `EvidenceRef`, `SourceLocator`, `VerifiedClaimRef`, erreurs publiques, commande idempotente.
- Invariants critiques: l'API ne publie que des états cohérents; `GET evidence` ne retourne que des preuves rattachées avec `SourceLocator` résolvable; `verify` ne contourne pas `ClaimVerificationPolicy`.
- Garde-fous: pas d'accès direct au repository depuis RA; pas de détails de prompt dans la réponse publique; pas de fallback vers extraction si `verify` reçoit un claim inconnu.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-008 attendue GREEN.
- Présence des milestones amont dans master: M-004 et M-005 requis et présents.
- Décisions manquantes: aucune si les endpoints restent des adaptateurs minces vers les handlers EG.
- Risques: fuite du modèle interne EG; erreurs HTTP ambiguës; commande non idempotente qui duplique des claims.

## Tâches
### T-009 - Exposer les commandes de claims et de preuves
- But métier: permettre à l'utilisateur ou aux contextes aval de déclencher et consulter la vérification sans écrire directement dans EG.
- Portée DDD: adaptateur HTTP EG, handlers applicatifs, contrats publics, erreurs stables et publication de `VerifiedClaimRef`.
- Scénario BDD:
  - Given un claim possède une vérification acceptée et des preuves directes.
  - When `GET /v1/claims/{claim_id}/evidence` est appelé.
  - Then l'API retourne les `EvidenceRef` résolvables sans exposer de stockage ni de prompt interne.
- Tests d'acceptation à écrire: `tests/m006/validate_claim_http_contract_acceptance.ps1`, couvrant extraction, vérification, lecture de claim, lecture de preuves `EvidenceRef` avec `SourceLocator` résolvable et erreurs publiques.
- Tests unitaires à écrire: tests de mapping HTTP, claim inconnu, idempotence de commande, payload invalide, absence de preuve, `SourceLocator` absent ou non résolvable, statut non publiable et masquage des détails internes.
- Implémentation attendue: créer l'adaptateur `app/evidence_governance/adapters/claim_http.py`, câbler les handlers applicatifs et définir les erreurs publiques stables de M-006.
- Invariants et garde-fous: aucune logique métier dans l'adaptateur; aucune valeur par défaut pour politique de vérification; aucune conversion silencieuse de payload; aucune preuve publique sans `SourceLocator` publié.
- Dépendances: T-008; ADR-006; ADR-010; DDD-ADR-003; DDD-ADR-005.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m006\validate_claim_http_contract_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m006\validate_claim_http_contract_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m006): couvrir contrat http claims`
- Commit GREEN: `feat(m006): exposer commandes claims evidence`
