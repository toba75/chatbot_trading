# T-008 - Publier l'événement CanonicalSourcePublished

## Milestone
- Nom: M-004 - Version canonique publiée.
- Source: livrables M-004 du plan v4.1, contrats M-001 et outbox M-002.
- Objectif métier: annoncer aux contextes aval qu'une version canonique est disponible sans leur donner accès au modèle interne SP.

## Contexte DDD
- Domaine: intégration intercontextes après publication documentaire.
- Bounded context: `SP`, consommateurs `KA` et `EG`.
- Objectif métier: publier un événement de domaine versionné et idempotent après acceptation d'une `CanonicalSource`.
- Langage ubiquitaire: `CanonicalSourcePublished`, enveloppe d'événement, outbox, consommateur aval, idempotence, contrat publié.
- Invariants critiques: l'événement n'est produit qu'après publication acceptée; son payload est un `CanonicalSourceRef`; l'outbox évite les doublons de transition métier; aucun modèle interne SP n'est exposé.
- Garde-fous: pas d'événement avant QA GREEN; pas d'appel direct KA/EG; pas de payload contenant chemins internes ou résultats de conversion complets.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 à T-007 doivent être GREEN.
- Présence des milestones amont dans master: M-000 à M-003 sont présents dans `master`.
- Décisions manquantes: aucune si l'événement applique l'enveloppe M-001 et l'outbox M-002; une ADR est requise si la coordination intercontextes change.
- Risques: double publication; événement incomplet; couplage direct de SP vers KA ou EG; payload non compatible avec les fixtures M-001.

## Tâches
### T-008 - Publier l'événement CanonicalSourcePublished
- But métier: rendre la version canonique consommable par les projections et la gouvernance des preuves sans briser les frontières DDD.
- Portée DDD: événement `CanonicalSourcePublished`, enveloppe M-001, outbox M-002, idempotence de publication et fixtures de contrat SP vers KA/EG.
- Scénario BDD:
  - Given une version canonique vient d'être publiée par SP.
  - When l'intégration intercontextes est traitée.
  - Then un événement `CanonicalSourcePublished` versionné est inscrit dans l'outbox avec un payload `CanonicalSourceRef` et aucune donnée interne SP.
- Tests d'acceptation à écrire: un test `tests/m004/validate_canonical_publication_event_acceptance.ps1` couvrant émission nominale, idempotence sur retry, refus avant publication et compatibilité de l'enveloppe.
- Tests unitaires à écrire: tests de payload `CanonicalSourceRef`, cohérence `aggregate_id`, `occurred_at`, version d'événement, déduplication outbox et absence de clés internes.
- Implémentation attendue: connecter la publication T-006 à l'outbox M-002, produire l'enveloppe existante et ajouter les fixtures M-004 ou réutiliser les fixtures M-001 quand elles suffisent.
- Invariants et garde-fous: un seul événement par version; payload contractuel uniquement; idempotence vérifiée; aucune transaction aval synchrone; aucun accès direct aux stockages KA ou EG.
- Dépendances: T-006; T-007; M-001 `EventEnvelope`; M-002 outbox; `tests/fixtures/m001/contracts/sp_to_ka_canonical_source_published_event_v1.json`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_canonical_publication_event_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_canonical_publication_event_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_event_envelope_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m002\validate_outbox_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m004): couvrir l evenement canonical source published`.
- Commit GREEN: `feat(m004): publier l evenement canonical source published`.
