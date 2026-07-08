# Runbook ingestion PDF V1 M-013

## Statut

- Identifiant: `M013-Runbook-PdfIngestion-1.0`
- Contextes: SP, KA, EG, RA, CV et EV.
- Sources: `docs/specs/m003_source_enregistree_diagnostiquee_routee.md` et `docs/specs/m004_version_canonique_publiee.md`
- ADR applicables: ADR-001, ADR-002, ADR-003, ADR-004, DDD-ADR-003, ADR-010
- ADR: non requise; ce runbook rappelle les routes explicites déjà livrées.

## Scénario BDD

- Given un PDF source est ajouté à la V1 locale.
- When l'utilisateur déclenche ingestion PDF et publication canonique.
- Then `SourceDocumentId`, `SourceLocator`, diagnostic de pages, route explicite, version canonique et statut public restent visibles sans fallback.

## Procédure

- Précondition: le PDF est un fichier local identifié; aucune source externe courante n'est implicitement récupérée.
- Commande vérifiée:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m003_specification.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m004_specification.ps1
```

- Résultat attendu: les spécifications d'enregistrement source, diagnostic, route explicite, quarantaine, conversion et autorité textuelle restent conformes.
- Erreur explicite: une page sans route, une source en quarantaine, une autorité textuelle absente ou un SourceLocator non résoluble bloque la publication canonique.
- Preuve à conserver: sortie des validateurs, identifiant `SourceDocumentId`, `SourceLocator` et référence de version canonique.

## Statuts publics

| Statut public | Sens utilisateur |
|---|---|
| `SOURCE_REGISTERED` | Source enregistrée avec identité stable. |
| `SOURCE_QUARANTINED` | Source bloquée avant publication. |
| `ROUTE_EXPLICIT` | Route de traitement décidée sans défaut implicite. |
| `CANONICAL_PUBLISHED` | Version canonique publiée et immuable. |

## Garde-fous

- Aucune route par défaut implicite.
- Aucune correction silencieuse d'un PDF illisible.
- Aucune preuve complète publiée dans les logs.
- Fallback silencieux: interdit.
- Les limites V1 issues des écarts SP restent visibles dans `docs/governance/m013_v1_gap_decisions.md`.
