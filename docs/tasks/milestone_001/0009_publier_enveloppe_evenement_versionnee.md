# T-009 - Publier l'enveloppe d'événement versionnée

## Milestone
- Nom: M-001 - Frontières DDD et contrats publiés.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, livrable `enveloppe d'événement versionnée`, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 4, 14, 15, 20 et 21.
- Objectif métier: donner aux événements intercontextes une forme publiée stable avant l'outbox opérationnelle M-002.

## Contexte DDD
- Domaine: synchronisation intercontextes et cohérence éventuelle.
- Bounded context: transverse; tous les contextes producteurs ou consommateurs d'événements.
- Objectif métier: distinguer un fait métier passé d'une commande ou d'un job technique.
- Langage ubiquitaire: événement de domaine, enveloppe d'événement, version d'événement, agrégat producteur, corrélation, causalité, producteur, idempotence.
- Invariants critiques: un événement est nommé au passé; un job demandé n'est pas un événement; l'enveloppe contient producteur, agrégat, version, corrélation et causalité; les doublons sont identifiables.
- Garde-fous: ne pas implémenter un bus distribué avant M-002; ne pas supposer une livraison exactement une fois; ne pas confondre commande refusible et événement consommable.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 doit être GREEN; T-003 fournit les contextes producteurs possibles.
- Présence des milestones amont dans master: M-000 est présent dans `master`.
- Décisions manquantes: aucune ADR nouvelle si la tâche matérialise DDD-ADR-006 et DDD-ADR-008 sans changer leur sens.
- Risques: faire de l'event sourcing généralisé; créer une file de jobs avant le contrat; accepter un événement sans producteur clair.

## Tâches
### T-009 - Publier l'enveloppe d'événement versionnée
- But métier: publier le contrat minimal qui permettra aux milestones aval de synchroniser les contextes par outbox et consommateurs idempotents.
- Portée DDD: enveloppe `event_id`, `event_type`, `event_version`, `occurred_at`, `aggregate_type`, `aggregate_id`, `aggregate_version`, `correlation_id`, `causation_id`, `producer_context` et `payload`.
- Scénario BDD:
  - Given un contexte publie un fait métier passé pour un autre contexte.
  - When l'événement est validé.
  - Then l'enveloppe versionnée identifie le producteur, l'agrégat, la causalité et permet au consommateur de détecter un doublon.
- Tests d'acceptation à écrire: un test de contrat qui accepte `CanonicalSourcePublished` dans une enveloppe complète et refuse un événement nommé comme commande, sans producteur ou sans version.
- Tests unitaires à écrire: tests de nommage au passé, champs obligatoires, version d'événement, contexte producteur autorisé, corrélation et détection de doublon par `event_id`.
- Implémentation attendue: créer l'enveloppe de contrat, les validateurs, les fixtures et une abstraction de test d'idempotence sans outbox persistante.
- Invariants et garde-fous: aucun producteur implicite; aucun event type vide; aucun fallback de version; aucun bus distribué ou stockage outbox opérationnel dans cette tâche.
- Dépendances: T-003; T-004; DDD-ADR-006; DDD-ADR-008; section 15 de la spécification v4.1.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_event_envelope_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_event_envelope_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`.
- Commit RED: `test(m001): couvrir l'enveloppe evenement versionnee`.
- Commit GREEN: `feat(m001): publier l'enveloppe evenement versionnee`.
