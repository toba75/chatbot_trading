# T-007 - Rendre les SourceLocator résolvables

## Milestone
- Nom: M-004 - Version canonique publiée.
- Source: livrables M-004 du plan v4.1, contrats M-001 et critères V1 de citation ouvrable.
- Objectif métier: permettre à une citation aval de retrouver la version canonique, la page PDF et l'item documentaire exact.

## Contexte DDD
- Domaine: traçabilité documentaire publiée.
- Bounded context: `SP`.
- Objectif métier: produire le mapping canonique nécessaire à la validation des `SourceLocator` sans exposer les structures internes SP.
- Langage ubiquitaire: `SourceLocator`, page PDF, item documentaire, `content_hash`, item_id, version canonique, politique de validation, citation ouvrable.
- Invariants critiques: tout item cité appartient à la version canonique publiée; le `content_hash` correspond au contenu de l'item; une version indisponible ou quarantinée rend le locator invalide.
- Garde-fous: pas de locator seulement au niveau document; pas d'item sans hash; pas d'accès direct de KA, EG ou RA aux tables internes SP.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 à T-006 doivent être GREEN.
- Présence des milestones amont dans master: M-000 à M-003 sont présents dans `master`.
- Décisions manquantes: aucune si le contrat `SourceLocator` M-001 reste inchangé; une ADR est requise si le langage publié de citation change.
- Risques: produire des citations non ouvrables; exposer des identifiants de stockage internes; permettre une version retirée comme preuve.

## Tâches
### T-007 - Rendre les SourceLocator résolvables
- But métier: garantir que toute preuve future peut ouvrir la page et l'item exacts de la version canonique.
- Portée DDD: index de résolvabilité SP, production d'item_id, hash de contenu, politique `SourceLocatorValidationPolicy`, endpoint ou port de résolution interne publié.
- Scénario BDD:
  - Given une version canonique publiée contenant une page avec plusieurs items.
  - When un contexte aval valide un `SourceLocator` vers un item précis.
  - Then SP confirme la version, la page, l'item et le `content_hash`, ou refuse explicitement le locator.
- Tests d'acceptation à écrire: un test `tests/m004/validate_source_locator_resolution_acceptance.ps1` couvrant locator valide, item absent, page hors version, hash incohérent et version non disponible.
- Tests unitaires à écrire: tests de construction item_id, stabilité du hash de contenu, mapping page-item, statut de version, refus des clés internes et intégration avec `SourceLocatorValidationPolicy`.
- Implémentation attendue: générer le registre de résolvabilité par version canonique, fournir la politique de validation aux consommateurs et conserver la frontière Published Language M-001.
- Invariants et garde-fous: item_id stable; `content_hash` obligatoire; aucune version non acceptée résolvable; aucun accès croisé au stockage SP; aucune correction silencieuse de locator.
- Dépendances: T-006; `app/contracts/source_references.py`; DDD-ADR-003; tests M-001 SourceLocator.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_source_locator_resolution_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_source_locator_resolution_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_source_locator_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_architecture_boundaries.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m004): couvrir la resolution des source locator`.
- Commit GREEN: `feat(m004): rendre les source locator resolvables`.
