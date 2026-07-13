# T-004 - Publier le jeu annoté page par page

## Milestone
- Nom: M-012 - Évaluation pilote et calibration.
- Source: M-012, section `Jeu annoté page par page` de la spécification v4.1.
- Objectif métier: publier la référence humaine qui permet de mesurer les routes, conversions, citations et lectures de tableaux.

## Contexte DDD
- Domaine: évaluation scientifique et calibration des seuils.
- Bounded context: transverse d'évaluation, avec SP et KA comme consommateurs des annotations de référence.
- Objectif métier: associer aux pages échantillonnées les attentes de route, transcription, chiffres, tableaux, ordre de lecture et provenance.
- Langage ubiquitaire: jeu annoté, annotation de page, route attendue, transcription de référence, valeur numérique critique, cellule de tableau, ordre de lecture, zone de provenance.
- Invariants critiques: chaque annotation référence une page du corpus pilote; les zones de provenance sont résolvables; les valeurs numériques critiques conservent signe, unité et contexte; une annotation incomplète ne peut pas être utilisée pour calibrer un seuil.
- Garde-fous: aucune annotation générée par le système évalué; aucune valeur critique sans source visuelle; aucune page omise silencieusement; aucun conflit entre route attendue et état attendu.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-003.
- Présence des milestones amont dans master: M-011 présent dans `master`.
- Décisions manquantes: aucune si l'annotation reste un artefact d'évaluation versionné.
- Risques: jeu annoté trop faible pour les tableaux; confusion entre transcription de référence et sortie Docling; absence d'annotation des pages rejetées ou vides.

## Tâches
### T-004 - Publier le jeu annoté page par page
- But métier: fournir l'oracle d'évaluation nécessaire aux métriques documentaires et citations.
- Portée DDD: `PageAnnotation`, `AnnotationSet`, `AnnotationCompletenessPolicy`, référence de page, état attendu, route attendue, transcription, chiffres, tableaux, ordre de lecture, zones de provenance et version d'annotation.
- Scénario BDD:
  - Given un corpus pilote figé.
  - When les pages échantillonnées sont annotées.
  - Then chaque page évaluée porte des attentes complètes et résolvables avant d'être utilisée par un benchmark.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue si une page évaluée n'a pas d'annotation, si une zone de provenance est non résolvable, si une valeur numérique critique perd signe ou unité, ou si une annotation générée par le système évalué est acceptée.
- Tests unitaires à écrire: tests de `AnnotationCompletenessPolicy` pour annotation manquante, route attendue absente, transcription absente, tableau incomplet, ordre de lecture absent, zone de provenance invalide, page vide non déclarée et conflit d'état attendu.
- Implémentation attendue: créer le format du jeu annoté, le validateur d'annotations, les fixtures d'annotation minimales et le lien entre annotations, documents pilotes et pages SP.
- Invariants et garde-fous: aucune page utilisée par benchmark sans annotation suffisante; aucune correction silencieuse d'une annotation incohérente; aucune sortie de conversion traitée comme référence; aucune suppression d'annotation historique sans nouvelle version.
- Dépendances: T-003; `SourceLocator`; `CanonicalSourceRef`; `docs/specs/m004_version_canonique_publiee.md`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m012): couvrir le jeu annote page par page`
- Commit GREEN: `feat(m012): publier le jeu annote page par page`
