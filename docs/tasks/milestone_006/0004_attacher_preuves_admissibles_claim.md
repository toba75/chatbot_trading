# T-004 - Attacher des preuves admissibles à un claim

## Milestone
- Nom: M-006 - Claims vérifiables.
- Source: spécification M-006 à publier et spécification v4.1, contrats `EvidenceRef` et invariants EG.
- Objectif métier: associer uniquement des preuves directes, résolvables et admissibles aux claims candidats.

## Contexte DDD
- Domaine: gouvernance des preuves.
- Bounded context: EG.
- Objectif métier: établir un lien contrôlé entre un claim et un span documentaire canonique.
- Langage ubiquitaire: `EvidenceRef`, `EvidenceAssociation`, `EvidenceSpan`, `EvidenceRelation`, `EvidenceAdmissibilityPolicy`, `CanonicalEvidenceReader`.
- Invariants critiques: une preuve pointe vers une version canonique publiée; `SUPPORTS_DIRECTLY` est requis pour vérifier; le `quoted_span_hash` doit rester cohérent.
- Garde-fous: aucune preuve issue d'une version en quarantaine; aucune relation inventée; aucun élargissement de portée lors de l'attachement.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-003 attendue GREEN.
- Présence des milestones amont dans master: M-004 et M-005 requis et présents.
- Décisions manquantes: aucune si EG consomme le contrat `EvidenceRef` M-001 et la recherche KA M-005.
- Risques: accepter un localisateur non résolvable; confondre preuve candidate KA et preuve admissible EG; perdre le hash du span cité.

## Tâches
### T-004 - Attacher des preuves admissibles à un claim
- But métier: permettre à EG de rattacher un claim à des preuves documentaires vérifiables sans déclarer encore le claim vrai.
- Portée DDD: `Claim.proposeEvidence`, `EvidenceAssociation`, `EvidenceAdmissibilityPolicy`, `CanonicalEvidenceReader`, événement `EvidenceAttachedToClaim`.
- Scénario BDD:
  - Given un claim `DRAFT` et une preuve candidate dont le `SourceLocator` pointe vers une version canonique publiée.
  - When la preuve est attachée avec la relation `SUPPORTS_DIRECTLY`.
  - Then le claim passe à `EVIDENCE_ATTACHED` et conserve le `EvidenceRef` complet avec son hash de span.
- Tests d'acceptation à écrire: `tests/m006/validate_claim_evidence_attachment_acceptance.ps1`, couvrant attachement admissible et refus de localisateur non publié.
- Tests unitaires à écrire: tests de relation non autorisée, hash absent, `SourceLocator` non résolvable, preuve de version retirée, doublon d'évidence et transition d'état interdite.
- Implémentation attendue: implémenter l'attachement dans l'agrégat `Claim`, le port de lecture des preuves canoniques et un repository mémoire EG utilisé par les tests.
- Invariants et garde-fous: pas de création de preuve sans `SourceLocator`; pas de relation par défaut; pas de fallback vers une page voisine si le span n'est pas résolvable.
- Dépendances: T-003; `app/contracts/evidence_claims.py`; `app/contracts/source_references.py`; DDD-ADR-003; DDD-ADR-005.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m006\validate_claim_evidence_attachment_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m006\validate_claim_evidence_attachment_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m006): couvrir attachement preuve claim`
- Commit GREEN: `feat(m006): attacher preuves admissibles aux claims`
