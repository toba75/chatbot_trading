# T-007 - Récupérer une page Gemma après provenance Granite absente

## Milestone

- Nom : M04-conversion - Conversion canonique réellement exécutable.
- Source : demande utilisateur du 2026-07-14, ADR-034 et ADR-035.
- Objectif métier : convertir une page réellement traitée par Granite mais
  dépourvue de provenance textuelle, sans masquer l'essai initial ni élargir
  la récupération à un autre échec.

## Scénario BDD

- Given une page M-003 suit une route Granite et Granite retourne
  `DOCLING_PROVENANCE_MISSING` après son essai réel.
- When le worker exécute la récupération ADR-035.
- Then Gemma 4 reçoit l'image par `llm-gateway`, rend du texte géométré, la
  trace Granite est incluse au canonique et la progression publique avance
  seulement après chaque page terminée.

## Garde-fous

- Aucun autre code Granite ne déclenche Gemma.
- Gemma indisponible, de mauvais modèle ou sans coordonnées reste terminale.
- Aucun appel direct Spark/vLLM, aucune fusion de texte Granite et Gemma.
- La page Gemma est l'unique autorité textuelle de sa page.

## Validation

- Test RED : `488ec2b82` —
  `gate_tests/ported/tests/m004/validate_granite_gemma_recovery_unit.py`.
- Commandes : `uv sync --locked`, `uv run --locked gate`, `git diff --check`.
- Commit GREEN : à renseigner après validation complète.
