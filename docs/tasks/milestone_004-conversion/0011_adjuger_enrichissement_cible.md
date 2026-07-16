# T-011 - Adjuger explicitement l’enrichissement ciblé

## Milestone

- Nom : M04-conversion - Conversion canonique réellement exécutable.
- Source : spécification unifiée 4.1, ADR-040 et parcours réel de
  `DOC-7A3001E2DE57C3E0`.
- Objectif métier : publier une page complexe native après comparaison Docling
  et Granite, sans détourner la route vers Gemma ni masquer l’issue Granite.

## Scénario BDD

- Given une page `TARGETED_ENRICHMENT` possède un candidat Docling standard
  valide et Granite termine avec une indisponibilité explicitement autorisée.
- When le worker exécute l’enrichissement ciblé et son adjudication.
- Then il conserve les preuves des deux tentatives, sélectionne explicitement
  Docling comme autorité de la page, n’appelle jamais Gemma, termine une seule
  unité publique et poursuit la conversion du document.

## Garde-fous

- Les deux candidats emploient des références d’audit distinctes.
- Granite est retenu lorsqu’il réussit ; Docling n’est retenu qu’après
  `DOCLING_PROVENANCE_MISSING` ou `GRANITE_DOCLING_UNAVAILABLE`.
- Tout autre échec reste terminal.
- Une seule autorité alimente la page canonique et sa trace d’adjudication est
  publiée dans l’artefact immuable.
- Gemma reste réservée aux routes Granite sans candidat Docling standard.
- Huit pages peuvent rester orchestrées en parallèle, mais toutes leurs
  tentatives Granite partagent une limite explicite de deux processus, calibrée
  sur deux pages précédemment échouées qui réussissent simultanément.

## Validation

- Test RED :
  `gate_tests/ported/tests/m004/validate_non_native_document_conversion_unit.py`.
- Preuve réelle : conversion publique de `DOC-7A3001E2DE57C3E0` jusqu’à
  `CANONICAL_ACCEPTED`, projection publique réussie et vérification UI.
- Commandes : `uv run --locked gate --scope m004`,
  `uv run --locked gate`, `git diff --check`.
