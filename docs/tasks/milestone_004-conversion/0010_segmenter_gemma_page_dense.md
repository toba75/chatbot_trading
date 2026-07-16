# T-010 - Segmenter explicitement une page Gemma dense

## Milestone

- Nom : M04-conversion - Conversion canonique réellement exécutable.
- Source : parcours réel de `DOC-7A3001E2DE57C3E0`, ADR-039.
- Objectif métier : convertir une page dense dont la transcription Gemma
  complète est tronquée, sans rejouer les pages déjà réussies ni masquer
  l’erreur du modèle.

## Scénario BDD

- Given Granite a réellement échoué sur une page et Gemma retourne une sortie
  invalide à 0 degré puis tronquée sur le rendu complet à 90 degrés.
- When le worker applique la récupération bornée d’ADR-039.
- Then il soumet exactement les seize bandes horizontales non chevauchantes de
  la page source, découpées de droite à gauche dans le rendu tourné, remappe
  leurs coordonnées dans la page PDF source, fusionne leurs items dans l’ordre
  haut-bas et ne termine l’unité publique qu’après les seize succès.

## Garde-fous

- `LLM_PARTIAL_OUTPUT` devient explicitement
  `GEMMA_VISION_OUTPUT_TRUNCATED`, jamais `GEMMA_VISION_UNAVAILABLE`.
- La segmentation n’est autorisée qu’après la troncature du second rendu
  complet à 90 degrés.
- Deux moitiés, quatre quarts et huit huitièmes sont interdits : les zones les
  plus denses restent tronquées. Les deux seizièmes de la zone la plus dense
  ont réussi réellement ; le nombre contractuel est fixé à seize segments.
- Découper la hauteur du rendu déjà tourné est interdit : cela conserve toutes
  les lignes d’un tableau dense dans chaque segment et ne borne pas sa sortie.
- Les appels portent des identifiants distincts ; aucun segment, modèle, angle
  ou retry supplémentaire n’est autorisé.
- Une erreur de segment reste terminale et aucun contenu partiel n’est publié.

## Validation

- Test RED :
  `gate_tests/ported/tests/m004/validate_granite_gemma_recovery_unit.py`.
- Preuve réelle : conversion publique de `DOC-7A3001E2DE57C3E0` jusqu’à
  `CANONICAL_ACCEPTED`, puis projection publique réussie.
- Commandes : `uv run --locked gate --scope m004`,
  `uv run --locked gate --scope m013_config`, `uv run --locked gate`,
  `git diff --check`.
