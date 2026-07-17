# ADR-041 - Pages vides ignorées et revue manuelle actionnable

**Statut :** Acceptée
**Date :** 2026-07-16
**Décideurs :** Équipe OSTrading
**Remplace :** Obligation de revue manuelle des pages `EMPTY` d'ADR-025
**Remplacée par :** Aucune
**Source :** Demande utilisateur du 2026-07-16 sur le parcours documentaire réel

## Contexte

L'inspection PDF isolée publie déjà l'état diagnostique `EMPTY` lorsqu'une page
ne contient ni texte natif, ni image, ni couche OCR. ADR-025 exige toutefois que
cette page reste en revue manuelle. Cette obligation bloque tout le document
alors qu'aucune conversion n'est nécessaire et que le signal métier est déjà
explicite.

À l'inverse, les véritables états `MANUAL_REVIEW` ne disposent pas encore d'une
commande publique et d'une interface permettant de prendre puis de persister la
décision humaine. Le statut est donc visible sans être actionnable, en
contradiction avec la règle « pas câblé, pas disponible ».

## Décision

- Une page diagnostiquée `EMPTY` **DOIT** recevoir la disposition routée
  `SKIP_EMPTY` et **NE DOIT PAS** déclencher `MANUAL_REVIEW`.
- `SKIP_EMPTY` **NE DOIT** appeler aucun préprocesseur, convertisseur, modèle ou
  fallback.
- Une page ignorée **DOIT** compter comme unité traitée dans la progression
  publique, sans être comptée comme page convertie.
- La numérotation PDF originale **DOIT** rester inchangée sur les pages
  converties et projetées après une page ignorée.
- Le manifeste d'autorité textuelle **DOIT** distinguer les pages converties des
  pages vides ignorées; une page ignorée **NE DOIT PAS** recevoir d'autorité
  textuelle synthétique.
- `MANUAL_REVIEW` **DOIT** être réservé à une page non vide ambiguë, corrompue ou
  sous le seuil de routage et sans décision humaine persistée.
- L'UI **DOIT** proposer l'action `Examiner` quand le document est en
  `MANUAL_REVIEW`.
- La revue **DOIT** exposer, via un contrat public authentifié, trois décisions
  explicites : `CONFIRM_EMPTY`, `ASSIGN_ROUTE` et `REJECT_DOCUMENT`.
- `CONFIRM_EMPTY` **DOIT** produire `SKIP_EMPTY` pour la page nommée.
- `ASSIGN_ROUTE` **DOIT** nommer une route de conversion réellement supportée;
  elle **NE DOIT PAS** autoriser `SKIP_EMPTY`.
- Chaque décision **DOIT** conserver le numéro de page, l'identité déclarée du
  réviseur, le motif, la décision et la route éventuelle.
- La résolution **DOIT** être persistée avec contrôle de version optimiste. Si
  d'autres pages restent ambiguës, le document reste `MANUAL_REVIEW`; sinon il
  passe à `ROUTE_PLANNED` et la conversion devient disponible.
- `REJECT_DOCUMENT` **DOIT** produire l'état terminal `REJECTED`.
- Aucun choix de route, aucune confirmation de vide et aucun rejet **NE DOIT**
  être déduit silencieusement par l'UI ou l'API.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Maintenir toute page `EMPTY` en revue | Rejetée | Blocage sans valeur et action humaine absente. |
| Créer un faux artefact de conversion vide | Rejetée | Introduit une autorité textuelle et un outil fictifs. |
| Omettre silencieusement la page | Rejetée | Perte d'audit et progression incohérente. |
| Disposition `SKIP_EMPTY` et revue publique persistée | Retenue | Explicite, auditable et compatible avec la numérotation PDF. |

## Conséquences

### Positives

- Les documents contenant des pages blanches poursuivent leur pipeline.
- Aucun temps Granite, Gemma, Docling ou OCRmyPDF n'est consommé pour une page
  déjà diagnostiquée vide.
- Les vraies revues manuelles deviennent résolubles et auditables.

### Négatives ou coûts

- Le manifeste d'autorité et la QA canonique doivent représenter explicitement
  les pages ignorées.
- Une migration PostgreSQL est nécessaire pour persister les décisions humaines.

### Risques et contrôles

- Risque de masquer du contenu : seule une page diagnostiquée `EMPTY` ou une
  confirmation humaine explicite peut produire `SKIP_EMPTY`.
- Risque de route forcée incohérente : l'API refuse toute route inconnue ou non
  exécutable et conserve l'auteur et le motif.
- Risque de progression trompeuse : les compteurs publics distinguent pages
  traitées, converties et vides ignorées.

## Impact d'implémentation

- Modules concernés: domaine et application SP, persistance PostgreSQL, API
  orchestratrice, client et rendu UI, conversion et QA canoniques.
- Configuration concernée: politique de routage documentaire `routing-v1`.
- Tests attendus: routage `EMPTY`, conversion sans appel d'outil, décisions de
  revue, contrat HTTP, persistance, rendu UI et parcours produit réel.
- Milestones concernées: M-003, M-004 et M-013-FastAPI.

## Liens de traçabilité

- Spécifications: `docs/specs/m003_source_enregistree_diagnostiquee_routee.md`,
  `docs/specs/m004_version_canonique_publiee.md`, `docs/specs/ui.md`.
- Plan d'implémentation: `docs/tasks/milestone_004-conversion/0012_ignorer_pages_vides_et_resoudre_revue.md`.
- Tests d'acceptation:
  `gate_tests/ported/tests/m003/validate_empty_page_and_manual_review_acceptance.py`,
  `gate_tests/ported/tests/m004/validate_empty_page_conversion_acceptance.py`,
  `gate_tests/ported/tests/m013_fastapi/validate_manual_review_ui_flow_acceptance.py`.
- Commits RED : `6333b859d`, `327f2f9aa`, `c75253074`.
- Commits GREEN : `12d1144d9`, `cffd38f5f`, `f102b35b4`.

## Notes

Acceptée après le parcours réel de `DOC-8C536DF8808F9E19` : conversion
`SUCCEEDED 265/265`, 264 pages converties, page PDF 2 ignorée sans outil ni
autorité synthétique, artefact canonique publié, projection `SUCCEEDED 155/155`
et `SEARCHABLE`. La gate `uv run --locked gate` est GREEN avec 436 nœuds
uniques.
