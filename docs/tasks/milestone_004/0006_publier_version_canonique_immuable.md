# T-006 - Publier une version canonique immuable

## Milestone
- Nom: M-004 - Version canonique publiée.
- Source: livrables M-004 du plan v4.1 et ADR-001.
- Objectif métier: accepter une version canonique structurée et immutable après conversion, adjudication et QA.

## Contexte DDD
- Domaine: publication documentaire canonique.
- Bounded context: `SP`.
- Objectif métier: créer une `CanonicalSource` versionnée qui fait autorité pour les contextes aval sans modifier les versions déjà publiées.
- Langage ubiquitaire: `CanonicalSource`, `CanonicalSourceRef`, version canonique, Docling JSON canonique, artefact canonique, export régénérable, correction, nouvelle version.
- Invariants critiques: une version acceptée est immutable; une correction crée une nouvelle version; le PDF original et le Docling JSON canonique sont les artefacts faisant autorité; les exports sont régénérables.
- Garde-fous: pas de mutation en place; pas de Markdown canonique; pas de publication sans QA GREEN; pas de version sans hash d'artefact.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 à T-005 doivent être GREEN.
- Présence des milestones amont dans master: M-000 à M-003 sont présents dans `master`.
- Décisions manquantes: aucune si la publication applique ADR-001; une ADR est requise si un autre artefact devient source de vérité.
- Risques: écraser une version publiée; générer un identifiant technique non conforme au langage M-001; confondre export et artefact canonique.

## Tâches
### T-006 - Publier une version canonique immuable
- But métier: fournir aux contextes aval une référence documentaire acceptée, stable et auditée.
- Portée DDD: agrégat `CanonicalSource`, cycle de vie de version, création de `CanonicalSourceRef`, stockage d'artefact canonique, exports régénérables et règles de correction par nouvelle version.
- Scénario BDD:
  - Given une source routée, convertie, adjugée et validée par QA.
  - When la publication canonique est demandée.
  - Then une version canonique immutable est créée avec `CanonicalSourceRef`, hash d'artefact, page count et statut accepté, sans modifier les versions antérieures.
- Tests d'acceptation à écrire: un test `tests/m004/validate_canonical_publication_acceptance.ps1` couvrant publication nominale, correction créant une nouvelle version, refus de mutation en place et refus de publication sans QA GREEN.
- Tests unitaires à écrire: tests de `CanonicalSource`, identifiants `CSRC` et `CVER`, hash d'artefact, statut de version, immutabilité, exports régénérables et interdiction des artefacts dérivés comme vérité.
- Implémentation attendue: créer `app/source_processing/domain/canonical_source.py`, les handlers applicatifs de publication, le port de stockage d'artefact et la production déterministe de `CanonicalSourceRef`.
- Invariants et garde-fous: version publiée immutable; correction par nouvelle version; Docling JSON canonique obligatoire; export Markdown ou HTML non canonique; source quarantinée refusée.
- Dépendances: T-005; M-001 `CanonicalSourceRef`; ADR-001; `app/contracts/source_references.py`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_canonical_publication_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_canonical_publication_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_source_contracts_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m004): couvrir la publication canonique immuable`.
- Commit GREEN: `feat(m004): publier une version canonique immuable`.
