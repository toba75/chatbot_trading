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
- Then il soumet exactement les deux moitiés non chevauchantes du rendu tourné,
  remappe leurs coordonnées dans la page PDF source, fusionne leurs items dans
  l’ordre et ne termine l’unité publique qu’après les deux succès.

## Garde-fous

- `LLM_PARTIAL_OUTPUT` devient explicitement
  `GEMMA_VISION_OUTPUT_TRUNCATED`, jamais `GEMMA_VISION_UNAVAILABLE`.
- La segmentation n’est autorisée qu’après la troncature du second rendu
  complet à 90 degrés.
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
