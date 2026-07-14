# T-009 - Récupérer l'orientation Gemma après bbox invalide

## Milestone

- Nom : M04-conversion - Conversion canonique réellement exécutable.
- Source : parcours réel de `trading-on-momentum - Copie.pdf`, ADR-036.
- Objectif métier : ne pas rejeter un document complet lorsque Gemma a lu une
  page mais retourne des coordonnées incompatibles avec le contrat public.

## Scénario BDD

- Given Granite a réellement échoué sur une page non native autorisant Gemma,
  puis le premier rendu Gemma non tourné retourne des bbox invalides.
- When le worker applique la récupération d'orientation d'ADR-036.
- Then il appelle Gemma une seconde et dernière fois avec un rendu à 90 degrés,
  réexprime les bbox dans le repère PDF source, trace
  `render-rotation-090` dans la version d'outil et poursuit la conversion.

## Garde-fous

- La seconde tentative est réservée au seul code
  `GEMMA_VISION_OUTPUT_INVALID` du premier rendu Gemma.
- Aucun autre angle, retry Granite, OCR, modèle ou appel direct Spark/vLLM
  n'est autorisé.
- Toute autre erreur Gemma reste terminale, persistée et publique.

## Validation

- Test RED :
  `gate_tests/ported/tests/m004/validate_granite_gemma_recovery_unit.py`.
- Preuve d'intégration : parcours UI réel du PDF complet, de l'ajout jusqu'à
  `CANONICAL_ACCEPTED` et la lecture publique de sa version.
- Commandes : `uv run --locked gate --scope m004`,
  `uv run --locked gate`, `git diff --check`.
