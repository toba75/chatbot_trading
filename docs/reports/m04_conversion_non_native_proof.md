# Preuve réelle M04 — routes non natives

**Date :** 2026-07-14  
**Branche :** `codex/m04-conversion`  
**Commits :** RED `ada4b6a0e`, `e62c60a2d`, `bfd5438e7`; GREEN `96be704d8`

## Contrat vérifié

Chaque action passe par le formulaire de l'UI locale, puis le contrat public,
l'outbox, le relais, le worker, l'outil isolé, la persistance et la lecture
publique. Il n'existe aucun changement implicite de route ni fallback après une
erreur d'outil.

Les actifs sont provisionnés séparément : Granite-Docling utilise
`ibm-granite/granite-docling-258M` à la révision
`982fe3b40f2fa73c365bdb1bcacf6c81b7184bfe`, contrôlée par manifeste SHA-256;
OCRmyPDF utilise l'image immuable
`jbarlow83/ocrmypdf@sha256:88d50f2ce7c054e5aacfc48794eca50dbb8af9a6ef1d2a540456dcd9a4687e42`.

## Résultats publics réels

| Source réelle | Route publique | Progression publique | Issue |
|---|---|---|---|
| `the-original-turtle-trading-rules.pdf`, page 3 | `NATIVE_STANDARD` | `QUEUED 0/1` → `SUCCEEDED 1/1` | `CANONICAL_ACCEPTED`, `CVER-M004-ROUTED-F91FE126FBFFA37438719227` |
| `the-original-turtle-trading-rules.pdf`, page 1 | `MIXED_PAGEWISE` | `QUEUED 0/1` → `RUNNING 0/1` → `SUCCEEDED 1/1` | Granite-Docling réel, `CVER-M004-ROUTED-36C1D89AA482316FB00F7B3F` |
| `trading-on-momentum.pdf`, page 123 | `PREPROCESS_GRANITE` avec `OCR_PHYSICAL_PREPROCESSING` | `QUEUED 0/1` → `RUNNING 0/1` → `FAILED 0/1` | `GRANITE_DOCLING_UNAVAILABLE`, aucun artefact canonique |

Pour la troisième ligne, OCRmyPDF a réellement écrit le PDF prétraité auditable
`data/docling_audit/RUN-DIAGNOSE-DOC-57B6154F051878A6/page-001-preprocessed.pdf`
(SHA-256 `f292da7d3ebde804195e00ea6b2b5edbc334586bcce2a2794d6bc5c8517eaff0`).
Granite n'a produit aucun item textuel exploitable : l'échec est donc
persistant et public, sans artefact canonique partiel ni bascule vers un autre
outil.

## Correction de politique

ADR-033 rend la précondition OCR atteignable : une dégradation physique prime
sur le caractère mixte technique, mais une page mixte saine conserve
`MIXED_PAGEWISE`. Une page à OCR mauvais sans dégradation physique conserve
`BAD_OCR_TO_GRANITE`. Une page complexe ou corrompue garde sa décision
spécialisée ou bloquante.

La preuve a exercé les formulaires HTML de l'UI réelle et les endpoints publics
uniquement. Le navigateur visuel intégré n'était pas disponible dans
l'environnement, donc aucune capture ni lecture directe de stockage n'est
présentée comme une preuve UI.

## Validation reproductible

Les neuf modules ciblés M-004 ont passé (`17 passed in 8.96s`), de même que
`uv lock --check` et `uv sync --locked`. La gate canonique complète a ensuite
validé 406 nœuds uniques en 94 secondes (`Gate GREEN`).
