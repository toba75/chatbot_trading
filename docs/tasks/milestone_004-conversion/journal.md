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
  une empreinte historique d'ADR-010 incohérente avec le contenu versionné.
  La cause établie est un hachage de l'arbre de travail dépendant des fins de
  lignes Windows, alors que l'allowlist doit vérifier le contenu versionné de
  façon stable. T-001 corrige ce défaut avant toute autre tranche.
- Aucun bouton `Convertir` n'est rendu tant que T-004 n'est pas GREEN.

## Exécution T-001

- Scénario vérifié : Given une preuve historique indexée avec un checkout
  CRLF, When la gate charge l'allowlist, Then elle accepte la seule variation
  de fin de ligne, lit le blob Git et refuse toute modification sémantique.
- RED : `f66c85eac` reproduit la divergence LF/CRLF ; `e922b14c3` impose la
  réconciliation auditée du catalogue fermé.
- Réconciliation : 67 empreintes ont été recalculées depuis les blobs Git
  indexés ; 30 valeurs ont changé. Il n'y a eu aucun ajout, retrait,
  réordonnancement de chemin ni changement de
  justification. Le catalogue `chemin + justification` est verrouillé par le
  test de contrat.
- Commande reproductible :
  `uv run --locked python -c "from pathlib import Path; from ost_gate.historical_references import reconcile_historical_allowlist; print(reconcile_historical_allowlist(Path.cwd()))"`.
- Preuves GREEN : `uv run --locked pytest gate_tests/ost_gate/test_historical_references_contract.py`
  (1 test atomique) et `uv run --locked gate --scope governance` (22 nœuds
  uniques, `SCOPE GREEN: governance`).

## Table des preuves

| Tâche | Commit RED | Commit GREEN | ADR | Validations | État |
|---|---|---|---|---|---|
| T-001 | `f66c85eac`, `e922b14c3` | `fb440e229` | ADR-029 | Gate de gouvernance, ancêtre `master`, checkout LF/CRLF, catalogue fermé de 67 preuves | GREEN ciblé |
| T-002 | À venir | À venir | ADR-032 | Tests ciblés, gate | À faire |
| T-003 | À venir | À venir | ADR-032; ADR-001 à ADR-004 | Tests ciblés, gate | À faire |
| T-004 | À venir | À venir | ADR-018; ADR-019; ADR-024; ADR-031 | Tests ciblés, gate, UI réelle | À faire |
| T-005 | À venir | À venir | ADR-002; ADR-003; ADR-031 | Tests ciblés, gate, UI réelle | À faire |
