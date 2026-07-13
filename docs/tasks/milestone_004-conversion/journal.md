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

## Exécution T-002

- GREEN initial : `uv run --locked gate` a validé 400 nœuds uniques en
  69,1 secondes avant le test RED.
- Scénario vérifié : Given une page possède une route M-003 explicite, When le
  worker de conversion la traite, Then il emploie l'adaptateur réel imposé ou
  publie son indisponibilité explicite, sans route de remplacement.
- RED : `d21b71718` ajoute le contrôle de gouvernance qui échoue en l'absence
  d'ADR-032.
- Décision : ADR-032 reste Proposée et impose Docling standard,
  Granite-Docling et OCRmyPDF conditionnel dans des runtimes isolés, avec
  actifs scellés par SHA-256, dépendance `uv` verrouillée et erreurs publiques
  stables. Aucun exécutable global, téléchargement silencieux ni fallback ne
  peut rendre `Convertir` disponible.
- GREEN : `ef05c09eb` crée ADR-032, met à jour son index et la spécification
  M-004. La réconciliation auditée de l'allowlist historique a conservé son
  catalogue fermé de 67 chemins et n'a mis à jour que l'empreinte de l'index
  ADR versionné.
- Preuves GREEN :
  `uv run --locked pytest gate_tests/ost_gate/test_historical_references_contract.py gate_tests/ported/tests/governance/validate_m004_conversion_runtime_governance_acceptance.py`
  (2 tests) puis `uv run --locked gate` (401 nœuds uniques, `Gate GREEN`,
  69,2 secondes). Cette dernière est la gate canonique complète, pas un scope
  partiel.

## Exécution T-003

- GREEN initial : `uv run --locked gate` a validé 401 nœuds uniques en
  69,7 secondes avant le test RED.
- Scénario vérifié : Given un PDF natif réel dont toutes les pages sont
  routées `NATIVE_STANDARD`, When `CONVERT_DOCUMENT` est exécuté, Then le
  processus Docling isolé et hors ligne produit le JSON canonique haché,
  immuable, puis la persistance transactionnelle publie la version et l'état
  `CANONICAL_ACCEPTED`.
- RED : `b789b3360` enrôle les invariants d'actifs scellés, de provenance,
  d'intégrité et d'immuabilité ainsi que le parcours d'acceptation Docling
  réel.
- Implémentation : `docling[vlm]==2.111.0` est verrouillé par `uv`; le worker
  lance seulement l'interpréteur de l'environnement courant, jamais un binaire
  global. Les actifs locaux sont préchargés explicitement par
  `uv run --locked preload-docling-native-assets --assets-root data/docling_assets/native --manifest-path config/docling-assets.native.json`, puis
  vérifiés par SHA-256 avant toute conversion avec `HF_HUB_OFFLINE=1`.
  L'absence ou l'altération de ces actifs reste RED avec un code stable : elle
  ne déclenche aucun téléchargement ni changement de route.
- Publication : le JSON Docling est créé une seule fois sous
  `paths.canonical_sources_root`; son hash, sa référence, la route native, la
  version de l'outil et `CANONICAL_ACCEPTED` sont persistés dans la même
  transaction PostgreSQL. La migration `011` introduit cette cohérence et la
  table des versions canoniques.
- GREEN : `fb5b398b9` livre l'adaptateur, le sous-processus, le worker, le
  stockage immuable, la persistance, le manifeste et les tests. Cette tranche
  ne rend pas encore le bouton UI disponible : T-004 doit encore publier le
  contrat de progression de bout en bout.
- Preuves GREEN :
  `uv run --locked pytest gate_tests/ported/tests/m004/validate_native_docling_conversion_unit.py gate_tests/ported/tests/m004/validate_native_document_conversion_worker_unit.py gate_tests/ported/tests/m004/validate_native_docling_conversion_acceptance.py -q`
  (3 tests, 6,43 s), puis `uv run --locked gate --scope m004` (33 nœuds
  uniques, `SCOPE GREEN: m004`, donc partiel), puis `uv lock --check`,
  `uv sync --locked`, `git diff --check` et `uv run --locked gate` (404 nœuds
  uniques, `Gate GREEN`, 94,5 s).

## Table des preuves

| Tâche | Commit RED | Commit GREEN | ADR | Validations | État |
|---|---|---|---|---|---|
| T-001 | `f66c85eac`, `e922b14c3` | `fb440e229` | ADR-029 | Gate de gouvernance, ancêtre `master`, checkout LF/CRLF, catalogue fermé de 67 preuves | GREEN ciblé |
| T-002 | `d21b71718` | `ef05c09eb` | ADR-032 (Proposée) | Test de gouvernance, contrat historique, gate canonique complète 401 nœuds | GREEN documentaire |
| T-003 | `b789b3360` | `fb5b398b9` | ADR-032; ADR-001 à ADR-004 | Tests ciblés, assets SHA-256 hors ligne, scope M-004, gate canonique complète 404 nœuds | GREEN réel natif |
| T-004 | À venir | À venir | ADR-018; ADR-019; ADR-024; ADR-031 | Tests ciblés, gate, UI réelle | À faire |
| T-005 | À venir | À venir | ADR-002; ADR-003; ADR-031 | Tests ciblés, gate, UI réelle | À faire |
