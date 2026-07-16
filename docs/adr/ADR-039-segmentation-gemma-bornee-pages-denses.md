# ADR-039 - Segmentation Gemma bornée des pages denses

**Statut :** Proposée
**Date :** 2026-07-16
**Décideurs :** Équipe OSTrading
**Remplace :** ADR-036 à l’acceptation
**Remplacée par :** Aucune
**Source :** Parcours réel M-004 du document `DOC-7A3001E2DE57C3E0`

## Contexte

La conversion réelle du PDF de 36 pages associé à
`DOC-7A3001E2DE57C3E0` a échoué sur une page dense après cinq pages publiées
dans la progression. Granite a réellement traité la page, puis la récupération
Gemma d’ADR-036 a produit successivement une sortie non JSON sur le rendu
initial et une sortie tronquée après rotation à 90 degrés.

La page fautive contient un tableau de 1 428 mots, 6 314 caractères et 104
lignes. Elle ne peut pas être transcrite intégralement dans les 2 048 jetons de
sortie du contrat courant. Porter ce budget à 4 096 jetons ne résout pas le
problème sur le Spark : les essais réels n’ont produit aucun premier jeton dans
le délai borné. Un premier essai avec deux moitiés a également produit
`LLM_PARTIAL_OUTPUT` sur la première moitié après 80 secondes et 3 463 octets
de réponse. Un essai en quatre quarts découpés après rotation a encore tronqué
le premier quart après 80 secondes et 3 304 octets : ce découpage isolait une
colonne du tableau mais conservait ses 104 lignes. L’erreur était en outre traduite à tort en
`GEMMA_VISION_UNAVAILABLE`, ce qui masquait que Gemma était disponible.

Il faut reprendre cette page sans appliquer Gemma aux autres pages, sans
relancer tout le document, sans récursion non bornée et sans fusion silencieuse
de transcriptions concurrentes.

## Décision

- La récupération reste strictement **page par page** et n’est autorisée
  qu’après l’un des échecs Granite prévus par la politique de récupération.
- Le worker **DOIT** d’abord soumettre le rendu complet à 0 degré.
- Seulement si ce rendu produit `GEMMA_VISION_OUTPUT_INVALID`, le worker
  **DOIT** soumettre un second rendu complet à 90 degrés.
- Seulement si ce second rendu produit `GEMMA_VISION_OUTPUT_TRUNCATED`, après
  traduction exacte de `LLM_PARTIAL_OUTPUT`, le worker **DOIT** découper le
  page source en exactement quatre bandes horizontales, ordonnées du haut vers
  le bas, non chevauchantes et couvrant ensemble toute la page. Sur le rendu à
  90 degrés, ces bandes correspondent à quatre découpes verticales parcourues
  de droite à gauche.
- Le contrat de requête isolé **DOIT** publier explicitement
  `render_segment_index` et `render_segment_count`. Les deux valeurs sont soit
  nulles ensemble pour un rendu complet, soit un index de `1` à `4` et le
  compte `4` pour un rendu segmenté à 90 degrés.
- Chaque rendu et chaque segment **DOIT** posséder des identifiants de requête,
  de trace et d’idempotence distincts, dérivés de la rotation et du segment.
- Chaque segment conserve le budget de 2 048 jetons. Le client du worker
  **DOIT** couvrir toutes les tentatives avant premier jeton configurées par le
  gateway, plus 30 secondes de marge ; avec la configuration courante, son
  délai de supervision vaut 270 secondes.
- Les coordonnées produites pour un segment **DOIVENT** être réexprimées
  d’abord dans la position horizontale du rendu complet tourné, puis dans le
  repère de la page PDF source. Les items sont fusionnés uniquement dans
  l’ordre haut-bas de la page source.
- La version d’outil **DOIT** tracer `render-rotation-090` puis
  `render-segments-04`. Aucun item du rendu complet tronqué n’est publiable.
- La page n’est comptée comme terminée qu’après la réussite des quatre segments.
  Une erreur sur un segment rend la page et la conversion terminalement RED
  avec son code exact.
- Le worker **NE DOIT PAS** créer un cinquième segment, une récursion, un
  chevauchement, un autre angle, un autre modèle, un OCR alternatif ou une
  nouvelle tentative Granite.
- Le document **NE DOIT PAS** basculer toutes ses pages vers Gemma lorsqu’une
  page requiert cette récupération.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Augmenter globalement la sortie à 4 096 jetons | Rejetée | Les essais réels de la page dense n’ont produit aucun premier jeton dans le délai du Spark. |
| Rejouer toute la page ou tout le document sans borne | Rejetée | Amplification, absence de progression fiable et risque de boucles. |
| Deux segments explicites après troncature du rendu tourné | Rejetée | La première moitié réelle est encore tronquée après 80 secondes. |
| Quatre quarts de la hauteur du rendu déjà tourné | Rejetée | Chaque quart conserve les 104 lignes du tableau et reste tronqué. |
| Quatre bandes horizontales de la page source | Retenue | Chaque segment borne le nombre de lignes, conserve le budget et maintient un nombre d’appels déterministe. |
| Appliquer Gemma à toutes les pages du document | Rejetée | Contredit le routage pagewise et masque le taux de fonctionnement réel de Granite. |

## Conséquences

### Positives

- Une page dense devient traitable sans augmenter le budget global du modèle.
- L’indisponibilité et la troncature restent deux erreurs publiques distinctes.
- Le nombre maximal d’appels Gemma pour une page est fixé à six.
- Granite reste tenté et mesurable séparément pour chaque page.

### Négatives ou coûts

- Une page dense en récupération consomme jusqu’à six inférences Gemma.
- Le remappage des coordonnées segmentées ajoute un contrat géométrique à
  maintenir.

### Risques et contrôles

- Risque de trou, doublon ou ordre inversé entre segments : découpage source
  haut-bas non chevauchant couvrant exactement la page et tests du crop
  droite-gauche après rotation ainsi que du remappage des quatre bandes.
- Risque de rejouer le même appel : suffixes de rotation et de segment dans les
  trois identifiants du gateway.
- Risque de publication partielle : fusion seulement après les quatre réponses
  valides ; toute erreur reste terminale.

## Impact d'implémentation

- Modules concernés : adaptateur Gemma Vision, worker de conversion routée,
  codes d’erreur publics et tests M-004.
- Configuration concernée : `models.llm.max_output_tokens` revient à `2048` ;
  la supervision dérivée reste à `270` secondes avec un retry configuré.
- Tests attendus : séquence d’appels bornée, mapping de
  `LLM_PARTIAL_OUTPUT`, identifiants distincts, remappage géométrique, fusion
  déterministe et parcours réel du PDF complet.
- Milestones concernées : M-004 et M-013 réalité produit.

## Liens de traçabilité

- Spécification : `docs/specs/m004_version_canonique_publiee.md`.
- Plan d'implémentation :
  `docs/tasks/milestone_004-conversion/0010_segmenter_gemma_page_dense.md`.
- Tests d'acceptation :
  `gate_tests/ported/tests/m004/validate_granite_gemma_recovery_unit.py`.
- Commits : à compléter après les commits RED et GREEN.

## Notes

ADR-039 reste proposée tant que les tests et le parcours réel du PDF de 36
pages ne sont pas GREEN. Son acceptation remplacera atomiquement ADR-036.
