# ADR-037 - Parallélisme documentaire et projection par lots

**Statut :** Acceptée
**Date :** 2026-07-15
**Décideurs :** Équipe OSTrading
**Remplace :** Aucun
**Remplacée par :** ADR-040 pour le plafond de concurrence Granite seulement
**Source :** Demande utilisateur du 2026-07-15 sur l'accélération d'un PDF unique ; ADR-031 ; ADR-036 ; `docs/specs/m004_version_canonique_publiee.md` ; `docs/specs/m005_projection_connaissance_recherchable.md`.

## Contexte

`uv run ui` démarre aujourd'hui un worker documentaire et un worker de
projection. La file PostgreSQL permet de traiter plusieurs jobs concurrents,
mais une conversion de PDF unique reste séquentielle page par page et une
projection reste séquentielle jusqu'à l'upsert complet dans Qdrant.

Le cas fréquent après l'ingestion initiale est l'ajout d'un seul PDF. Ajouter
plusieurs processus workers sans parallélisme interne accélère surtout plusieurs
PDF distincts, pas le document courant. Le besoin utilisateur est d'accélérer ce
document tout en conservant les invariants existants : route M-003 par page,
Granite puis Gemma page par page selon ADR-036, progression publique persistée
selon ADR-031, et publication canonique ou searchable uniquement complète.

## Décision

- `services.workers.concurrency` **DOIT** devenir le plafond explicite de
  parallélisme local pour `uv run ui`. Sa valeur par défaut applicative est 8.
- `uv run ui` **DOIT** démarrer autant de processus workers documentaires et de
  projection que cette valeur, avec des identifiants stables et distincts.
- Le worker documentaire **DOIT** convertir les pages d'un même document en
  parallèle jusqu'à ce plafond, tout en assemblant le `DoclingDocument` final
  dans l'ordre PDF déterministe.
- Granite puis Gemma restent un enchaînement page par page. L'échec Granite
  d'une page ne redirige pas les autres pages vers Gemma.
- La progression de conversion **DOIT** compter les pages réellement terminées.
  Elle **NE DOIT PAS** utiliser le numéro de page terminé comme compteur.
- La publication canonique SP **DOIT** rester atomique : aucun artefact canonique
  n'est publié tant que toutes les pages attendues ne sont pas converties,
  fusionnées et acceptées par la QA.
- Le worker de projection **DOIT** paralléliser l'encodage et la publication
  Qdrant par lots sous le même plafond, tout en vérifiant le nombre exact de
  points avant de marquer la projection `SEARCHABLE`.
- La projection **NE DOIT PAS** devenir `SEARCHABLE` si un lot échoue, si une
  génération partielle existe ou si le count Qdrant final diffère du total
  attendu.
- Les mises à jour de progression **DOIVENT** provenir des unités terminées et
  persistées, pas des logs ni d'un état local UI.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Parallélisme interne pagewise et projection par lots | Retenue | Accélère un PDF unique sans publier d'état partiel. |
| Multiplier seulement les processus workers | Rejetée | Accélère plusieurs documents concurrents mais pas le PDF courant. |
| Publier des versions partielles au fil des pages ou des lots | Rejetée | Viole l'autorité canonique et le caractère régénérable complet de la projection. |
| Déduire la progression depuis l'UI ou les logs | Rejetée | Viole ADR-031 et masque les échecs réels. |

## Conséquences

### Positives

- Un PDF long peut utiliser plusieurs coeurs et plusieurs appels d'outils en
  parallèle.
- La progression publique devient cohérente avec le nombre d'unités terminées.
- Le paramètre de concurrence est unique et visible dans la configuration.

### Négatives ou coûts

- Plusieurs processus et plusieurs sous-processus Docling/Granite/Gemma peuvent
  consommer davantage de mémoire.
- Les erreurs concurrentes exigent une propagation stricte pour éviter toute
  publication partielle.

### Risques et contrôles

- Risque : progression incohérente si une page haute finit avant une page basse.
  Contrôle : compteur monotone d'unités terminées.
- Risque : génération Qdrant partielle visible. Contrôle : count exact final et
  refus d'une génération préexistante incomplète.
- Risque : fallback Gemma global. Contrôle : récupération limitée au résultat
  de la page qui a échoué avec Granite.

## Impact d'implémentation

- Modules concernés : `app/source_processing/application/convert_routed_pages.py`,
  `app/source_processing/application/routed_document_conversion_worker.py`,
  `app/source_processing/adapters/worker_runtime.py`,
  `app/knowledge_access/application/encode_projection.py`,
  `app/knowledge_access/adapters/qdrant_vector_index.py`,
  `app/knowledge_access/adapters/projection_runtime.py`,
  `app/knowledge_access/adapters/worker_runtime.py`,
  `app/platform/ui_local_stack.py`.
- Configuration concernée : `config/application.yaml`,
  `config/application.example.yaml`, `services.workers.concurrency`.
- Tests attendus : conversion pagewise parallèle, progression monotone,
  publication Qdrant par lots parallèles, bootstrap `uv run ui` avec 8 workers.
- Milestones concernées : M-004, M-005, M-013-FastAPI.

## Liens de traçabilité

- Spécification : `docs/specs/m004_version_canonique_publiee.md` et
  `docs/specs/m005_projection_connaissance_recherchable.md`.
- Plan d'implémentation : demande utilisateur directe sur le parcours UI réel.
- Tests d'acceptation :
  `gate_tests/ported/tests/m004/validate_parallel_page_conversion_unit.py`,
  `gate_tests/ported/tests/m013_fastapi/validate_projection_parallel_batches_unit.py`,
  `gate_tests/ported/tests/m013/validate_ui_worker_parallelism_unit.py`.
- Commits : RED et GREEN à renseigner.

## Notes

Cette décision reste proposée jusqu'à la preuve GREEN de `uv run --locked gate`
et du parcours d'ingestion réel jusqu'à la projection.
