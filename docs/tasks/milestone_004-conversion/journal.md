# Journal M04-conversion - Conversion canonique réellement exécutable

## Portée

Cette tranche complète le runtime manquant de M-004 sur le socle M13-FastAPI.
Elle ne redéfinit ni les politiques de domaine M-004 déjà acceptées, ni les
frontières UI/API d'ADR-018 et ADR-031.

## Ordre d'exécution

1. T-001 - Vérifier la précondition GREEN de la conversion réelle.
2. T-002 - Décider l'exécution réelle de la conversion canonique.
3. T-003 - Convertir un document natif et publier son artefact canonique.
4. T-004 - Exposer la conversion et sa progression publique dans l'UI.
5. T-005 - Traiter explicitement les routes non natives et prouver le pipeline.

## État initial

- Base officielle : `master` et `codex/m13-fastapi` ont été intégrés par
  fast-forward sur `9edeab957` le 2026-07-13.
- Branche de travail : `codex/m04-conversion`.
- Gate antérieure : `uv run --locked gate --workers 8` GREEN sur `9edeab957`,
  avec 400 nœuds uniques et une durée d'environ 67,6 secondes.
- Précondition actuellement RED : `uv run --locked gate --scope governance`
  échoue sur `gate.historical-references` avec
  `GATE_HISTORICAL_ALLOWLIST_HASH_MISMATCH:docs/adr/ADR-010-gates-gouvernance-powershell.md`.
  La cause établie est un hachage de l'arbre de travail dépendant des fins de
  lignes Windows, alors que l'allowlist doit vérifier le contenu versionné de
  façon stable. T-001 corrige ce défaut avant toute autre tranche.
- Aucun bouton `Convertir` n'est rendu tant que T-004 n'est pas GREEN.

## Table des preuves

| Tâche | Commit RED | Commit GREEN | ADR | Validations | État |
|---|---|---|---|---|---|
| T-001 | À venir | À venir | ADR-029 | Gate canonique, ancêtre `master`, test de fins de lignes | RED connu |
| T-002 | À venir | À venir | ADR-032 | Tests ciblés, gate | À faire |
| T-003 | À venir | À venir | ADR-032; ADR-001 à ADR-004 | Tests ciblés, gate | À faire |
| T-004 | À venir | À venir | ADR-018; ADR-019; ADR-024; ADR-031 | Tests ciblés, gate, UI réelle | À faire |
| T-005 | À venir | À venir | ADR-002; ADR-003; ADR-031 | Tests ciblés, gate, UI réelle | À faire |
