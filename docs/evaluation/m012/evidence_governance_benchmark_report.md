# Rapport de benchmark gouvernance des preuves EG M-012

## Scénario BDD

- Given les états publiés de claims associés aux réponses du corpus pilote.
- When EG est mesuré par `EvidenceGovernanceBenchmark`.
- Then les claims vérifiés, rejetés, en revue, sans preuve directe, verdicts, groupes de dépendance, supersessions et délais de vérification sont publiés sans lire de stockage EG interne.

## Contrat publié

- `EvidenceClaimMeasurement` porte le statut publié du claim, son verdict, son sujet, ses groupes de dépendance, son état de supersession et ses horodatages de vérification.
- Un claim `VERIFIED` sans preuve directe est refusé par le benchmark.
- Les distributions de statuts et de verdicts restent séparées des taux agrégés.
- Les groupes de dépendance sont comptés par sujet.
- Le délai de vérification est calculé uniquement sur les claims décidés; les claims `IN_REVIEW` restent dans le dénominateur de statut.

## Métriques normatives EG

- `evidence_claim_verified_rate`
- `evidence_claim_rejected_rate`
- `evidence_claim_review_rate`
- `evidence_unsupported_assertion_ratio`
- `evidence_verdict_distribution`
- `evidence_dependency_group_count`
- `evidence_supersession_rate`
- `evidence_verification_delay_seconds`

ADR: non requise; T-008 applique ADR-010 et DDD-ADR-007 sans modifier leur sens.
