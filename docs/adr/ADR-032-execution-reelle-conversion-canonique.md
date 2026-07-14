# ADR-032 - Exécution réelle et reproductible de la conversion canonique

**Statut :** Remplacée
**Date :** 2026-07-13
**Décideurs :** Équipe OSTrading
**Remplace :** Aucun
**Remplacée par :** ADR-035
**Source :** `docs/tasks/milestone_004-conversion/0002_decider_execution_reelle_conversion.md`, ADR-001 à ADR-004, ADR-031 et T-004 de `docs/specs/plan_remediation_m13.md`

## Contexte

M-004 possède les ports `PageConverter`, `PagePreprocessor` et
`CanonicalArtifactStore`, ainsi que les invariants du `DoclingDocument` unique.
Ils ne constituent pas un runtime : aucun adaptateur réel n'est aujourd'hui
installé, supervisé, configuré ni relié au worker de conversion.

ADR-002 impose la route M-003, ADR-003 réserve OCRmyPDF aux pages qui le
justifient, ADR-004 impose une autorité textuelle unique et ADR-001 impose le
PDF original ainsi que le Docling JSON canonique. ADR-031 interdit d'exposer
une action UI asynchrone tant que sa chaîne réelle et sa progression publique
ne sont pas disponibles.

Le `docling` installé globalement sur un poste et les modèles téléchargés à la
première exécution ne sont pas des dépendances reproductibles. En outre,
OCRmyPDF ne peut pas être retenu comme exécutable global sous Windows : sa
chaîne native doit être livrée et vérifiée comme un runtime isolé.

## Décision

- Une page est convertie exclusivement par l'adaptateur déterminé par sa route
  M-003 déjà publiée :

  | Route M-003 | Adaptateur réel obligatoire | Entrée et sortie |
  |---|---|---|
  | `NATIVE_STANDARD` | Docling standard | PDF original immuable -> sortie page Docling |
  | `SCAN_GRANITE`, `BAD_OCR_TO_GRANITE`, `MIXED_PAGEWISE`, `TARGETED_ENRICHMENT` | Granite-Docling (`GRANITE_DOCLING`) | PDF original immuable -> sortie page Docling |
  | `PREPROCESS_GRANITE` | OCRmyPDF puis Granite-Docling (`GRANITE_DOCLING`) | PDF original -> PDF prétraité auditable -> sortie page Docling |

- La dépendance Python de ces deux adaptateurs Docling **DOIT** être déclarée
  exactement sous la forme `docling[vlm]==2.111.0` dans `pyproject.toml` et
  verrouillée dans `uv.lock` avant que l'adaptateur soit câblé. Le domaine SP
  continue de dépendre uniquement de ses ports ; le SDK Docling reste dans les
  adaptateurs d'infrastructure.
- Chaque conversion Docling **DOIT** être exécutée dans un processus isolé,
  démarré par le worker depuis l'interpréteur de l'environnement `uv` courant.
  Son protocole d'entrée et de sortie est versionné, borné et ne transmet que
  l'artefact explicitement demandé, la route, l'identifiant de run et le chemin
  d'artefacts. Il **NE DOIT PAS** appeler un exécutable global `docling`.
- Les modèles Docling standard et Granite-Docling **DOIVENT** être décrits dans
  un manifeste d'actifs versionné : dépôt, révision immuable, fichiers et
  SHA-256. Le runner reçoit seulement ce répertoire validé, avec
  `HF_HUB_OFFLINE=1`. Un préchargement est une commande explicite, distincte de
  la conversion et de `uv run ui`; aucun téléchargement silencieux ne peut
  survenir pendant une action utilisateur.
- Granite-Docling **DOIT** utiliser le modèle local
  `ibm-granite/granite-docling-258M` dont la révision et les SHA-256 sont dans
  ce manifeste. Le service historique `granite-docling` qui ne prouve pas ce
  modèle, son manifeste et son protocole ne satisfait pas cette décision.
- OCRmyPDF **DOIT** être exécuté dans un conteneur local isolé, référencé par
  digest immuable dans le même manifeste d'actifs. Il reçoit un montage d'entrée
  en lecture seule, un répertoire de sortie dédié et aucun réseau. Son image
  est provisionnée par une commande explicite, jamais tirée silencieusement par
  `uv run ui`; l'UI ne dépend d'aucun exécutable global `ocrmypdf`.
- Le `CanonicalArtifactStore` **DOIT** écrire le Docling JSON canonique dans un
  emplacement déterministe par document et version, calculer son SHA-256 puis
  persister référence, hash, version de l'outil et route avant publication.
  Cet artefact canonique immuable ne peut jamais être remplacé à version égale.
  Les PDF prétraités et les sorties de page restent des preuves d'audit et ne
  deviennent jamais l'autorité canonique.
- Une indisponibilité est publique, stable et sans détail d'hôte, de chemin ou
  de secret : `DOCLING_STANDARD_UNAVAILABLE`,
  `GRANITE_DOCLING_UNAVAILABLE`, `OCRMYPDF_UNAVAILABLE`,
  `CONVERSION_ASSET_MANIFEST_INVALID` et
  `CANONICAL_ARTIFACT_STORE_UNAVAILABLE`. Le worker persiste cette issue
  terminale; il n'essaie pas une autre route et il n'y a pas de fallback.
- Conformément à ADR-031, `uv run ui` ne rendra `Convertir` disponible que si
  le contrat public, l'écriture, l'outbox, le relais, le worker, les runtimes
  requis par les routes du document, le stockage et la lecture publique sont
  prêts et supervisés. Si l'un d'eux est absent avant l'action, la lecture
  publique expose l'indisponibilité nommée et le bouton n'est pas disponible.
  S'il disparaît après acceptation, la progression publique devient `FAILED`
  avec le code stable, après une phase réellement persistée.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Adaptateurs Docling verrouillés, modèles scellés et OCRmyPDF conteneurisé | Retenue | Rend chaque outil identifiable, isolé et utilisable depuis `uv run ui` sans état machine caché. |
| Exécutable Docling ou OCRmyPDF trouvé dans le `PATH` | Rejetée | Rend le résultat dépendant du poste et ne permet pas de prouver la version réellement utilisée. |
| Télécharger les modèles à la première conversion | Rejetée | Masque une dépendance externe et rend l'action imprévisible ou non reproductible. |
| Utiliser une sortie synthétique ou basculer de Docling vers Granite | Rejetée | Viole la route M-003, ADR-002 et l'interdiction de fallback. |
| Conserver le service Granite historique sans preuve de modèle | Rejetée | Un endpoint qui ne matérialise pas le modèle et les actifs verrouillés n'est pas Granite-Docling réel. |

## Conséquences

### Positives

- L'outil qui a produit chaque page et ses actifs sont auditables.
- L'artefact canonique reste relié au PDF original, à la route et à son hash.
- Une action de conversion indisponible est explicitement visible au lieu de
  produire une conversion partielle ou simulée.

### Négatives ou coûts

- `docling[vlm]`, les modèles scellés et l'image OCRmyPDF alourdissent le
  provisioning local.
- Les runners isolés et le stockage d'audit exigent une supervision et des
  contrats supplémentaires.

### Risques et contrôles

- Un actif absent ou altéré est refusé avant conversion par
  `CONVERSION_ASSET_MANIFEST_INVALID`.
- Un outil indisponible est persistant et public, sans bascule vers un autre
  outil.
- Une image OCRmyPDF ou un modèle non scellé n'autorise pas l'action UI.
- Les validations d'acceptation devront traverser le parcours
  `UI -> API -> outbox -> relais -> worker -> processus isolé -> stockage -> état public`.

## Impact d'implémentation

- Modules concernés : adaptateurs SP de conversion et de stockage, worker de
  documents, configuration d'actifs, composition de `uv run ui`, contrats et
  read-models de progression.
- Configuration concernée : `pyproject.toml`, `uv.lock`, manifeste versionné
  des actifs Docling/Granite/OCRmyPDF et répertoires d'artefacts locaux.
- Le parcours `NATIVE_STANDARD` livré par T-003 utilise
  `config/docling-assets.native.json`. Le provisionnement reste explicite :
  `uv run --locked preload-docling-native-assets --assets-root data/docling_assets/native --manifest-path config/docling-assets.native.json`.
  Le manifeste est refusé si le répertoire n'est pas déjà présent et scellé ;
  la conversion ne le crée ni ne le modifie.
- Tests attendus : gouvernance ADR-032, route native, route Granite, route
  OCRmyPDF conditionnel, actif absent ou altéré, outil absent, stockage
  immuable, progression publique et parcours UI réel.
- Milestones concernées : M04-conversion, M13-reality.

## Liens de traçabilité

- Spécification : `docs/specs/m004_version_canonique_publiee.md`, section
  « Exécution réelle et disponibilité des convertisseurs » ; T-004 de
  `docs/specs/plan_remediation_m13.md`.
- Plan d'implémentation :
  `docs/tasks/milestone_004-conversion/0002_decider_execution_reelle_conversion.md`
  et `docs/tasks/milestone_004-conversion/0003_convertir_document_natif_et_publier_artefact.md`.
- Tests d'acceptation :
  `gate_tests/ported/tests/governance/validate_m004_conversion_runtime_governance_acceptance.py`
  et `gate_tests/ported/tests/m004/validate_native_docling_conversion_acceptance.py`.
- Tests de contrat :
  `gate_tests/ported/tests/m004/validate_native_docling_conversion_unit.py`
  et `gate_tests/ported/tests/m004/validate_native_document_conversion_worker_unit.py`.
- Commits : RED `d21b71718`, `b789b3360`; GREEN `ef05c09eb`.

## Notes

Cette ADR reste **Proposée** tant que les adaptateurs, actifs et preuves réelles
ne sont pas livrés. Elle complète ADR-001 à ADR-004 et ADR-031 sans en changer
le sens.

La compatibilité Python 3.12 de Docling, son installation par `uv` et la
nécessité de précharger les modèles avant un usage hors ligne ont été vérifiées
dans la documentation officielle Docling. La contrainte OCRmyPDF sous Windows
est satisfaite par le conteneur isolé et non par une installation globale.
