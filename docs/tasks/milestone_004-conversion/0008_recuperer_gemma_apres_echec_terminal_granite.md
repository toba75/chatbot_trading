# T-008 - Récupérer Gemma après un échec terminal Granite

## Milestone

- Nom : M04-conversion - Conversion canonique réellement exécutable.
- Source : parcours utilisateur réel du 2026-07-14 et ADR-036.
- Objectif métier : achever une conversion de page non native quand Granite a
  été réellement tenté mais retourne un échec terminal explicitement admis.

## Scénario BDD

- Given une source M-003 est enregistrée, diagnostiquée et routée, et Granite
  retourne `GRANITE_DOCLING_UNAVAILABLE` pour une page non native après son
  unique essai réel.
- When le worker M-004 traite la page selon ADR-036.
- Then Gemma 4 est appelée une seule fois via `llm-gateway`, la trace Granite
  est portée par la page canonique, la progression publique avance seulement
  après cette page et le parcours peut atteindre `CANONICAL_ACCEPTED`.

## Garde-fous

- `DOCLING_PROVENANCE_MISSING` et `GRANITE_DOCLING_UNAVAILABLE` sont les deux
  seuls déclencheurs Gemma.
- Aucun retry Granite, OCR, modèle ou appel direct Spark/vLLM n'est autorisé.
- Une erreur Gemma, d'actif, de source, de stockage ou de contrat reste
  terminale et publique.

## Validation

- Test RED :
  `gate_tests/ported/tests/m004/validate_granite_gemma_recovery_unit.py`.
- Preuve d'intégration : ajout réel du PDF, diagnostic, conversion,
  `CANONICAL_ACCEPTED` et lecture publique de la version canonique.
- Commandes : `uv run --locked gate --scope m004`,
  `uv run --locked gate`, `git diff --check`.
