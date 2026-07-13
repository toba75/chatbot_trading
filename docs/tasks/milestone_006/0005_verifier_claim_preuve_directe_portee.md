# T-005 - Vérifier un claim par preuve directe et portée conservée

## Milestone
- Nom: M-006 - Claims vérifiables.
- Source: scénario directeur M-006 et spécification v4.1, invariants EG sur `VERIFIED`, `VerificationCase` et portée.
- Objectif métier: empêcher qu'une affirmation plausible devienne vérifiée sans preuve directe admissible et portée compatible.

## Contexte DDD
- Domaine: gouvernance des preuves.
- Bounded context: EG.
- Objectif métier: enregistrer une décision de vérification indépendante, explicite et immuable.
- Langage ubiquitaire: `SubmitClaimForVerification`, `ClaimSubmittedForVerification`, `VerificationCase`, `ClaimVerificationPolicy`, `ScopePreservationPolicy`, `IndependentClaimVerifier`, `VerificationVerdict`, `ReasonCode`.
- Invariants critiques: `VERIFIED` exige `ENTAILED` ou combinaison explicitement autorisée; `PARTIALLY_ENTAILED` ne vérifie pas un claim plus large; toute décision enregistre modèle, prompt et version de politique.
- Garde-fous: aucun score comme vérité; aucune preuve indirecte acceptée silencieusement; aucun effacement d'un rejet.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-004 attendue GREEN.
- Présence des milestones amont dans master: M-004 et M-005 requis et présents.
- Décisions manquantes: la politique autorisant plusieurs preuves doit être documentée dans la spécification M-006 avant implémentation; ADR requise si elle change le sens de DDD-ADR-005.
- Risques: validation trop large; mélange entre origine automatisée et état de domaine; absence de raisons de refus.

## Tâches
### T-005 - Vérifier un claim par preuve directe et portée conservée
- But métier: protéger la transition vers `VERIFIED` par une décision vérifiable et refusante par défaut explicite.
- Portée DDD: commande `SubmitClaimForVerification`, transition `EVIDENCE_ATTACHED` vers `UNDER_VERIFICATION`, agrégat `VerificationCase`, transitions `VERIFIED` et `REJECTED`, politiques de vérification et de portée, événements `ClaimSubmittedForVerification` et `VerificationDecisionRecorded`.
- Scénario BDD:
  - Given une affirmation à l'état `EVIDENCE_ATTACHED`.
  - When elle est soumise à vérification puis qu'aucune preuve admissible `SUPPORTS_DIRECTLY` n'existe.
  - Then l'événement `ClaimSubmittedForVerification` est enregistré, l'affirmation atteint `UNDER_VERIFICATION`, ne passe pas à `VERIFIED` et la raison `INSUFFICIENT_DIRECT_EVIDENCE` est enregistrée.
- Tests d'acceptation à écrire: `uv run --locked gate`, couvrant soumission à vérification, acceptation `ENTAILED`, refus sans preuve directe, refus de portée élargie et rejet explicite.
- Tests unitaires à écrire: tests de `SubmitClaimForVerification`, `ClaimSubmittedForVerification`, `ClaimVerificationPolicy`, `ScopePreservationPolicy`, immutabilité de `VerificationCase`, transitions interdites, métadonnées de décision absentes et verdict partiel.
- Implémentation attendue: implémenter la soumission en vérification, le cycle de vérification, le port `IndependentClaimVerifier`, le handler `VerifyClaimHandler` et la publication contrôlée de `VerifiedClaimRef`.
- Invariants et garde-fous: pas de valeur par défaut pour le verdict; pas de passage `DRAFT` vers `UNDER_VERIFICATION` ou `VERIFIED`; pas de fallback vers revue humaine silencieuse; pas de publication de `VerifiedClaimRef` sans preuve.
- Dépendances: T-004; `app/contracts/evidence_claims.py`; ADR-006; DDD-ADR-005; DDD-ADR-007.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m006): couvrir verification claim preuve directe`
- Commit GREEN: `feat(m006): verifier claims par preuve directe`
