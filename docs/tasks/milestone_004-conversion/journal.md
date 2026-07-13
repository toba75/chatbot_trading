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
6. T-006 - Accepter les décisions de conversion effectivement livrées.

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

## Exécution T-004

- Scénario livré : Given un document dont toutes les pages sont routées
  `NATIVE_STANDARD`, When l'utilisateur clique `Convertir` dans l'UI, Then
  l'UI transmet `POST /v1/documents/{id}/convert`, ne consomme ensuite que les
  contrats publics de conversion et de progression, affiche phase et unités
  persistées, et le bouton disparaît dès que la demande existe.
- Contrat livré : `POST /v1/documents/{id}/convert` retourne seulement
  `document_id`, `conversion_status` et, après succès canonique, la version
  publique. La commande persiste `QUEUED`, son job `CONVERT_DOCUMENT` est
  relayé par l'outbox existante, le worker persiste `RUNNING` avant Docling,
  puis `SUCCEEDED` ou `FAILED` avec les unités et l'erreur publique stable.
  `GET /v1/documents/{id}/conversion/progress` expose ce seul état public.
- Disponibilité : le read-model marque l'action disponible uniquement avant
  toute demande, pour une route complète `NATIVE_STANDARD`. Le runtime de
  l'UI supervise le worker documentaire réel ; ce worker construit le
  convertisseur Docling et vérifie le manifeste SHA-256 des actifs avant de
  pouvoir démarrer. Il initialise aussi la racine du stockage canonique avant
  sa boucle ; un actif absent ou altéré, ou un stockage indisponible, bloque
  donc le démarrage UI au lieu de rendre le bouton disponible avec un fallback.
- Preuves automatisées GREEN :
  `uv run --locked pytest gate_tests/ported/tests/m004/validate_conversion_public_progress_acceptance.py gate_tests/ported/tests/m004/validate_ui_conversion_progress_unit.py gate_tests/ported/tests/m004/validate_document_conversion_command_acceptance.py gate_tests/ported/tests/m004/validate_document_conversion_command_unit.py gate_tests/ported/tests/m004/validate_native_docling_conversion_acceptance.py gate_tests/ported/tests/m004/validate_native_document_conversion_worker_unit.py -q`
  complété par `validate_native_docling_conversion_unit.py` (7 tests, 7,01 s) ;
  `uv sync --locked` ; `uv run --locked gate` (406 nœuds, `Gate GREEN`,
  97,7 s) ; `git diff --check` GREEN.
- Preuve locale réelle : `uv run ui` a démarré PostgreSQL, l'API, le gateway
  local et le worker SP, avec les actifs Docling natifs provisionnés. Le PDF
  réel « The Original Turtle Trading Rules », page 3 native extraite à
  l'identique pour former une source d'une page, a obtenu `ROUTE_PLANNED` et
  le bouton `Convertir` dans `/ui/corpus-pdf`. Son action UI a redirigé vers
  l'inspection de conversion ; celle-ci a rendu publiquement `QUEUED`, `0 / 1`,
  puis `SUCCEEDED`, `1 / 1`, `CANONICAL_ACCEPTED` et
  `CVER-M004-NATIVE-35B0B2F10D5D541993F217CC`. Après succès, le bouton était
  absent. L'UI n'a lu ni table ni log ; la lecture s'est faite exclusivement
  via `GET /v1/documents/{id}/conversion` et
  `GET /v1/documents/{id}/conversion/progress`.
- Commit GREEN : `bd27e2433` (`feat(ui): exécuter conversion et progression
  publique`). Le runtime temporaire a été arrêté après la preuve ; le port
  `8081` est libre.

### Correctif de preuve T-004 constaté pendant T-005

La preuve T-004 historique affirmait `ROUTE_PLANNED` après l'action UI
`Diagnostiquer`, mais le worker réel s'arrêtait en fait à `DIAGNOSED` : il
n'appelait pas `ApproveRoutePlan` et le bouton n'était donc pas atteignable
pour une source nouvellement diagnostiquée. T-005 a rétabli la chaîne dans le
worker, avec persistance optimiste de transition. La preuve native a été
rejouée depuis le formulaire UI sur `DOC-F91FE126FBFFA374` :
`ROUTE_PLANNED/NATIVE_STANDARD`, `QUEUED 0/1`, puis `SUCCEEDED 1/1` et
`CVER-M004-ROUTED-F91FE126FBFFA37438719227`.

## Exécution T-005

- BDD : Given une page M-003 routée hors native, When l'action UI Convertir
  est acceptée, Then seul l'outil de sa route est exécuté et la progression
  publique atteint soit une version canonique, soit une erreur terminale sans
  artefact canonique partiel.
- Baseline GREEN : les six tests T-004 de conversion publique, UI, commande et
  Docling natif ont passé (`6 passed in 8.02s`).
- RED principal : `ada4b6a0e` (`test(m04): couvrir routes non natives et preuve
  réelle`) a ajouté les contrats Granite-Docling, OCRmyPDF et les erreurs
  terminales. RED d'intégration UI : `e62c60a2d` (`test(m04): exiger le
  routage après diagnostic`) a exposé l'arrêt incorrect en `DIAGNOSED`.
- Décision et RED de politique : les signaux réels d'une page dégradée étaient
  simultanément mixtes, donc les routes OCR étaient inatteignables. ADR-033
  est proposée pour fixer l'ordre corruption, complexité, dégradation physique,
  OCR mauvais, mélange sain, scan propre, texte natif. `bfd5438e7`
  (`test(m003): rendre routes OCR atteignables ADR-033`) a vérifié
  `PREPROCESS_GRANITE`, `BAD_OCR_TO_GRANITE` et `MIXED_PAGEWISE` sans
  fallback.
- GREEN : `96be704d8` (`feat(m04): exécuter routes documentaires réelles`)
  livre les convertisseurs isolés, les manifestes scellés, OCRmyPDF Docker,
  le worker routé, le plan de route automatique après diagnostic, la migration
  `013` pour les routes non natives et les erreurs publiques persistables.
- Provisionnement explicite :
  `uv run --locked preload-docling-granite-assets --assets-root data/docling_assets/granite --manifest-path config/docling-assets.granite.json`
  a scellé `ibm-granite/granite-docling-258M` à
  `982fe3b40f2fa73c365bdb1bcacf6c81b7184bfe`; `uv run --locked
  preload-ocrmypdf-image` a obtenu l'image
  `jbarlow83/ocrmypdf@sha256:88d50f2ce7c054e5aacfc48794eca50dbb8af9a6ef1d2a540456dcd9a4687e42`.
  Aucun actif n'est téléchargé pendant une conversion.
- Preuve UI Granite réelle : le formulaire UI a enregistré la page 1 de
  `the-original-turtle-trading-rules.pdf` sous `DOC-36C1D89AA482316F`. Le
  diagnostic public a produit `ROUTE_PLANNED/MIXED_PAGEWISE`; l'action UI a
  publié `QUEUED 0/1`, `RUNNING 0/1`, puis `SUCCEEDED 1/1`,
  `CANONICAL_ACCEPTED` et
  `CVER-M004-ROUTED-36C1D89AA482316FB00F7B3F`.
- Preuve UI OCR réelle : la page 123 de `trading-on-momentum.pdf` a été
  enregistrée sous `DOC-57B6154F051878A6`. Après ADR-033, le diagnostic public
  a produit `ROUTE_PLANNED/PREPROCESS_GRANITE` et
  `OCR_PHYSICAL_PREPROCESSING`. L'action UI a publié `QUEUED 0/1`, `RUNNING
  0/1`, puis `FAILED 0/1` avec `GRANITE_DOCLING_UNAVAILABLE`. OCRmyPDF a bien
  produit l'artefact d'audit
  `data/docling_audit/RUN-DIAGNOSE-DOC-57B6154F051878A6/page-001-preprocessed.pdf`
  (22 024 octets, SHA-256
  `f292da7d3ebde804195e00ea6b2b5edbc334586bcce2a2794d6bc5c8517eaff0`), mais
  Granite n'a fourni aucun item textuel : aucun artefact canonique n'a été
  publié. Cette limite est une issue terminale vérifiée, non une conversion
  présentée comme réussie.
- Une première tentative Granite a révélé la contrainte PostgreSQL historique
  réservée à `NATIVE_STANDARD`. La migration `013` accepte les six routes
  M-003 et l'état persistant `POSTGRES_INTEGRITY_FAILURE` est maintenant lu
  publiquement comme `FAILED`, sans masquer l'incident.
- La connexion de navigateur visuel n'était pas disponible dans
  l'environnement. Les preuves ont donc soumis les formulaires réels de l'UI
  locale (`Origin` même origine, `multipart/form-data`, redirections `303`)
  et lu exclusivement les endpoints publics; aucune table, log ou état local
  n'a servi à déterminer les phases affichées.
- Validations finales ciblées : les neuf modules de tests M-004 (contrat
  public, UI, commande, conversion native, routes non natives et routage après
  diagnostic) ont passé, soit `17 passed in 8.96s`; `uv lock --check` et
  `uv sync --locked` sont également GREEN. La gate canonique a validé
  406 nœuds uniques en 94 secondes (`Gate GREEN`). La vérification historique
  ignore désormais les actifs locaux sous `data/`, non versionnés et fournis
  explicitement, sans élargir son catalogue fermé de preuves historiques.

## Table des preuves

| Tâche | Commit RED | Commit GREEN | ADR | Validations | État |
|---|---|---|---|---|---|
| T-001 | `f66c85eac`, `e922b14c3` | `fb440e229` | ADR-029 | Gate de gouvernance, ancêtre `master`, checkout LF/CRLF, catalogue fermé de 67 preuves | GREEN ciblé |
| T-002 | `d21b71718` | `ef05c09eb` | ADR-032 (Proposée) | Test de gouvernance, contrat historique, gate canonique complète 401 nœuds | GREEN documentaire |
| T-003 | `b789b3360` | `fb5b398b9` | ADR-032; ADR-001 à ADR-004 | Tests ciblés, assets SHA-256 hors ligne, scope M-004, gate canonique complète 404 nœuds | GREEN réel natif |
| T-004 | `e8b82bf47` | `bd27e2433` | ADR-018; ADR-019; ADR-024; ADR-031; ADR-032 | 7 tests ciblés, `uv sync --locked`, gate complète 406 nœuds, `git diff --check`, UI réelle `QUEUED` puis `SUCCEEDED` | GREEN réel UI |
| T-005 | `ada4b6a0e`, `e62c60a2d`, `bfd5438e7` | `96be704d8` | ADR-002; ADR-003; ADR-031; ADR-032; ADR-033 | 17 tests ciblés, migration 013, UI native/Granite/OCR réelle, absence de publication partielle, gate complète 406 nœuds | GREEN |
| T-006 | À venir | À venir | ADR-032; ADR-033 | Gouvernance ADR, allowlist historique, gate canonique complète | À faire |
