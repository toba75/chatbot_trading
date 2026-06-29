# T-008 - Conserver les claims rejetés et supersédés

## Milestone
- Nom: M-006 - Claims vérifiables.
- Source: plan M-006, ADR-006, DDD-ADR-010 et spécification v4.1 sur la conservation des claims rejetés ou supersédés.
- Objectif métier: conserver l'audit des décisions négatives et des versions remplacées.

## Contexte DDD
- Domaine: gouvernance des preuves.
- Bounded context: EG.
- Objectif métier: empêcher qu'un rejet, une limite ou une supersession efface l'historique de vérification.
- Langage ubiquitaire: `ClaimRejected`, `ClaimSuperseded`, `SupersedeClaim`, `VerificationCase`, version de claim, conservation, audit.
- Invariants critiques: un claim vérifié ne peut pas être supprimé; un claim rejeté conserve sa raison; une supersession pointe vers la nouvelle version sans changer le sens de l'ancienne.
- Garde-fous: pas de mise à jour destructive; pas de réutilisation d'identifiant pour changer une proposition; pas de purge ordinaire des versions négatives.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-007 attendue GREEN.
- Présence des milestones amont dans master: M-004 et M-005 requis et présents.
- Décisions manquantes: aucune pour la conservation métier; ADR requise si une durée de rétention ou purge administrative durable est décidée.
- Risques: perdre pourquoi un claim a été rejeté; modifier une version vérifiée; rendre RA incapable d'expliquer une supersession.

## Tâches
### T-008 - Conserver les claims rejetés et supersédés
- But métier: assurer que les décisions de preuve restent auditables même lorsqu'une affirmation est refusée ou remplacée.
- Portée DDD: transitions `REJECTED` et `SUPERSEDED`, versioning de `Claim`, lien `SupersededBy`, événements `ClaimRejected` et `ClaimSuperseded`.
- Scénario BDD:
  - Given un claim vérifié possède une preuve directe et une version publiée.
  - When une meilleure formulation le supersède.
  - Then l'ancien claim reste consultable avec sa décision et pointe explicitement vers la nouvelle version.
- Tests d'acceptation à écrire: `tests/m006/validate_claim_retention_acceptance.ps1`, couvrant rejet conservé, supersession conservée et refus de suppression ordinaire.
- Tests unitaires à écrire: tests de transition destructive interdite, raison de rejet obligatoire, lien de supersession absent, version inchangée modifiée et consultation de version supersédée.
- Implémentation attendue: implémenter la conservation dans l'agrégat et le repository EG, exposer les lectures nécessaires et préserver les événements de rejet/supersession.
- Invariants et garde-fous: aucune suppression logique cachée; aucune mutation d'une décision immuable; aucune création de nouvelle version sans lien explicite.
- Dépendances: T-007; ADR-006; DDD-ADR-005; DDD-ADR-010.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m006\validate_claim_retention_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m006\validate_claim_retention_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m006): couvrir conservation claims rejetes`
- Commit GREEN: `feat(m006): conserver claims rejetes supersedes`
