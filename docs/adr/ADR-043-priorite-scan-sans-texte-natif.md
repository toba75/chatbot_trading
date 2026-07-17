# ADR-043 - Priorité au scan sans texte natif

**Statut :** Acceptée
**Date :** 2026-07-16
**Décideurs :** Équipe OSTrading
**Remplace :** Pour `COMPLEX_VISUAL` sans texte natif, la priorité de classification d’ADR-033
**Remplacée par :** Aucune
**Source :** Page 166 du document réel `DOC-8C536DF8808F9E19`

## Contexte

La page 166 est diagnostiquée avec texte natif absent, scan propre et mise en
page complexe. La priorité actuelle retient `COMPLEX_VISUAL`, puis
`TARGETED_ENRICHMENT`. Cette route exige un candidat Docling standard alors que
Docling confirme `provenance absente`; la conversion devient terminale avec
`DOCLING_STANDARD_UNAVAILABLE`.

## Décision

- Une page avec texte natif `ABSENT` et image `SCAN_CLEAN` **DOIT** être classée
  `SCAN_CLEAN`, même si sa mise en page est complexe.
- Elle **DOIT** suivre `SCAN_GRANITE`, avec la récupération Gemma explicite déjà
  décidée pour cette route.
- `COMPLEX_VISUAL` et `TARGETED_ENRICHMENT` **DOIVENT** rester réservés aux pages
  possédant un candidat textuel natif.
- Les diagnostics et routes persistés selon l’ancienne priorité **DOIVENT** être
  migrés sans modifier leur numéro de page ni leur justification d’origine.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Accepter l’échec Docling standard | Rejetée | Exige une autorité dont le diagnostic annonce déjà l’absence. |
| Envoyer tout `COMPLEX_VISUAL` à Granite | Rejetée | Supprime l’enrichissement ciblé des pages natives complexes. |
| Prioriser le scan lorsque le texte natif est absent | Retenue | Aligne diagnostic, route et outils réellement admissibles. |

## Conséquences

### Positives

- Les scans complexes n’exigent plus de faux candidat natif.
- Les pages natives complexes conservent l’adjudication Docling/Granite.

### Négatives ou coûts

- Une migration recalcule la route dominante et les exceptions des runs touchés.

### Risques et contrôles

- Risque de déroutage trop large : les trois signaux `ABSENT`, `SCAN_CLEAN` et
  `COMPLEX` sont requis ensemble.

## Impact d'implémentation

- Modules concernés : politique diagnostique M-003 et persistance PostgreSQL.
- Configuration concernée : aucune.
- Tests attendus : classification et route de la combinaison exacte.
- Milestones concernées : M-003, M-004 et M-013 réalité produit.

## Liens de traçabilité

- Spécification : `docs/specs/m003_source_enregistree_diagnostiquee_routee.md`.
- Plan d’implémentation : `docs/tasks/milestone_004-conversion/0014_router_scan_complexe_sans_texte.md`.
- Tests d’acceptation : `gate_tests/ported/tests/m003/validate_complex_scan_routing_unit.py`.
- Commit RED : `8b9fe93e5`.
- Commit GREEN : `20daa39a2`.

## Notes

Acceptée après le franchissement réel de la page PDF 166 de
`DOC-8C536DF8808F9E19` par `SCAN_GRANITE`, puis la conversion
`SUCCEEDED 265/265`, la projection `SEARCHABLE` et la gate verrouillée GREEN de
436 nœuds uniques.
