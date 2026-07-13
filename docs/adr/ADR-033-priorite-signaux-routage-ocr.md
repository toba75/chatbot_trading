# ADR-033 - Priorité des signaux pour les routes OCR atteignables

**Statut :** Acceptée
**Date :** 2026-07-14
**Décideurs :** Équipe OSTrading
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** ADR-002, ADR-003, ADR-032 et T-005 de `docs/tasks/milestone_004-conversion/0005_traiter_routes_non_natives_et_prouver_pipeline.md`

## Contexte

L'inspecteur PDF isolé publie simultanément `mixed_content_detected=true`,
`existing_ocr_state=BAD` et `image_state=SCAN_DEGRADED` lorsqu'une page porte
une image et une couche OCR insuffisante. La politique M-003 classait alors
`MIXED_CONTENT` avant les signaux OCR et physiques. Les routes
`PREPROCESS_GRANITE` et `BAD_OCR_TO_GRANITE` existaient dans le domaine mais
étaient inatteignables depuis ce diagnostic réel.

Ce résultat contredit ADR-002, qui impose le routage explicite, et ADR-003,
qui autorise OCRmyPDF seulement lorsqu'un diagnostic le justifie. La correction
ne doit pas dérouter une page mixte légitime dont l'OCR est valide et le scan
propre.

## Décision

- `PageDiagnosticPolicy` **DOIT** appliquer les signaux dans l'ordre suivant :
  corruption, complexité visuelle, dégradation physique du scan, OCR existant
  mauvais, contenu mixte légitime, scan propre, texte natif.
- Une page `SCAN_DEGRADED`, même si elle contient une couche OCR mauvaise et
  est techniquement mixte, **DOIT** être routée `PREPROCESS_GRANITE`; elle est
  la seule route qui autorise OCRmyPDF puis Granite-Docling.
- Une page dont l'OCR est mauvais mais dont le scan n'est pas physiquement
  dégradé **DOIT** être routée `BAD_OCR_TO_GRANITE`, sans OCRmyPDF implicite.
- Une page mixte avec OCR valide et scan propre **DOIT** rester
  `MIXED_PAGEWISE`; elle ne doit pas être assimilée à une page dégradée.
- Une page complexe **DOIT** garder `TARGETED_ENRICHMENT` avant les règles OCR
  et mixtes; une page corrompue **DOIT** rester bloquée.
- Aucun ordre de signal **NE DOIT** sélectionner une autre route après l'échec
  d'un outil. L'issue reste terminale et publique conformément à ADR-031 et
  ADR-032.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Priorité explicite dégradation/OCR avant mélange légitime | Retenue | Rend les routes OCR accessibles tout en conservant `MIXED_PAGEWISE` pour les pages saines. |
| Conserver `MIXED_CONTENT` en première position | Rejetée | Rend OCRmyPDF conditionnel inatteignable avec le diagnostic réel actuel. |
| Appliquer OCRmyPDF à toute page mixte | Rejetée | Viole ADR-003 et introduit un prétraitement non justifié. |
| Basculer vers Granite après un échec OCR | Rejetée | Viole ADR-002, ADR-031 et l'interdiction de fallback. |

## Conséquences

### Positives

- Les routes `PREPROCESS_GRANITE` et `BAD_OCR_TO_GRANITE` ont des préconditions
  observables et testables.
- Une page mixte saine conserve la route spécialisée existante.
- Le diagnostic public peut justifier l'action UI avant le lancement du worker.

### Négatives ou coûts

- L'ordre de classification M-003 devient une décision versionnée à tester.
- Le corpus réel peut révéler une erreur terminale Granite après OCRmyPDF; ce
  résultat doit rester public et ne constitue pas une réussite synthétique.

### Risques et contrôles

- Les tests couvrent une page physiquement dégradée, un OCR mauvais sans
  dégradation, une page mixte légitime, une page complexe et une page corrompue.
- La preuve UI réelle doit observer `ROUTE_PLANNED/PREPROCESS_GRANITE`,
  `QUEUED`, `RUNNING` et l'état terminal persistant.

## Impact d'implémentation

- Modules concernés : `app/source_processing/domain/document_processing_run.py`,
  le worker de diagnostic et les read-models publics existants.
- Configuration concernée : aucune nouvelle valeur implicite; la version de
  politique de routage existante reste persistée dans le `RoutePlan`.
- Tests attendus : priorité de classification, plan de route, UI réelle et
  persistance de l'erreur terminale.
- Milestones concernées : M-003, M-004 et M13-reality.

## Liens de traçabilité

- Spécification : `docs/specs/m003_source_enregistree_diagnostiquee_routee.md`.
- Plan d'implémentation : `docs/tasks/milestone_004-conversion/0005_traiter_routes_non_natives_et_prouver_pipeline.md`.
- Tests d'acceptation : `gate_tests/ported/tests/m004/validate_diagnostic_route_planning_unit.py`.
- Commits : RED `bfd5438e7`; GREEN `96be704d8`.

## Notes

Cette ADR complète ADR-002 et ADR-003 sans les remplacer : elle fixe leur ordre
d'application quand les signaux d'une même page se recouvrent.
