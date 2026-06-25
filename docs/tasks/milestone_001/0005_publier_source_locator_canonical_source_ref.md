# T-005 - Publier CanonicalSourceRef et SourceLocator

## Milestone
- Nom: M-001 - Frontières DDD et contrats publiés.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, livrables `CanonicalSourceRef` et `SourceLocator`, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 4, 20 et 21.
- Objectif métier: permettre aux contextes aval de référencer une version documentaire canonique sans lire le modèle interne de SP.

## Contexte DDD
- Domaine: traitement des sources et traçabilité documentaire publiée.
- Bounded context: SP producteur; KA, EG, RA et CV consommateurs directs ou indirects.
- Objectif métier: rendre une citation résolvable jusqu'à la version, la page et l'item documentaire avec détection d'incohérence.
- Langage ubiquitaire: version canonique, localisateur de source, page PDF, item source, hash de contenu, version en quarantaine, version retirée.
- Invariants critiques: `SourceLocator` pointe une page de la version canonique; `item_id` est résolvable; `content_hash` détecte l'incohérence; une version en quarantaine ou retirée est refusée sans avertissement explicite.
- Garde-fous: ne pas exposer les tables SP; ne pas utiliser Qdrant comme source de vérité; ne pas inventer de résolvabilité si le statut de version est inconnu.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 doit être GREEN; T-004 fournit les identifiants et versions communes.
- Présence des milestones amont dans master: M-000 est présent dans `master`.
- Décisions manquantes: aucune ADR nouvelle si DDD-ADR-003 est appliquée sans changement de sens.
- Risques: accepter un localisateur incomplet; pointer une version invalide; coupler KA ou EG aux détails internes de SP.

## Tâches
### T-005 - Publier CanonicalSourceRef et SourceLocator
- But métier: publier le contrat documentaire minimal qui autorise recherche, preuves et citations ouvrables dans les milestones aval.
- Portée DDD: contrats `CanonicalSourceRef` et `SourceLocator`, fixtures producteur SP, fixtures consommateur KA/EG, règles de refus des versions invalides.
- Scénario BDD:
  - Given SP publie une version canonique acceptée.
  - When KA ou EG reçoit un `SourceLocator`.
  - Then le consommateur peut vérifier la version, la page, l'item et le hash sans accéder au modèle interne de SP.
- Tests d'acceptation à écrire: un test de contrat producteur-consommateur qui sérialise `CanonicalSourceRef` et `SourceLocator`, puis refuse un `SourceLocator` vers une version absente, en quarantaine ou retirée.
- Tests unitaires à écrire: tests des invariants `page_pdf`, `item_id`, `content_hash`, `canonical_version_id` et compatibilité de lecture `schema_version`.
- Implémentation attendue: créer les modèles de contrat, validateurs stricts, fixtures JSON et tests de round-trip pour SP vers KA et SP vers EG.
- Invariants et garde-fous: aucun champ requis vide; aucun fallback vers `document_id` seul; aucun avertissement implicite pour version invalide; aucune dépendance à une classe interne SP.
- Dépendances: T-004; DDD-ADR-003; sections 4 et 21 de la spécification v4.1.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_source_contracts_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_source_locator_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`.
- Commit RED: `test(m001): couvrir source locator et canonical source ref`.
- Commit GREEN: `feat(m001): publier les contrats documentaires`.
