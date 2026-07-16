# M-003 - Source enregistrée, diagnostiquée et routée

## Statut

- Milestone: M-003 - Source enregistrée, diagnostiquée et routée.
- Source canonique: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M-003 - Source enregistrée, diagnostiquée et routée`.
- Spécification normative: `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 5, 12, 17, 19, 20 et 21.
- ADR consultées: ADR-002, ADR-003, ADR-010, ADR-033, DDD-ADR-003.
- Contrats amont: `docs/specs/m001_frontieres_ddd_contrats_publies.md` et `docs/specs/m002_plateforme_locale_sure.md`.
- ADR: non requise, car M-003 applique le routage hybride, l'usage OCRmyPDF conditionnel et le langage publié documentaire sans changer leur sens.

## Scénario BDD

- Given la spécification v4.1 définit SP comme propriétaire du diagnostic et du routage documentaire.
- When la spécification M-003 est publiée.
- Then chaque comportement M-003 nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.

## Mission

M-003 publie le contrat exécutable du bounded context SP pour transformer un PDF original en `SourceDocument` enregistré, diagnostiqué page par page et muni d'une route explicite. Le PDF original reste immuable, chaque page est représentée dans un manifeste de pages et une route incertaine produit une revue manuelle ou une quarantaine explicite.

M-003 ne publie aucune version canonique et ne décide pas l'autorité textuelle finale. Ces comportements restent exclus et relèvent de M-004.

## Contexte DDD

- Domaine: traitement des sources documentaires.
- Bounded context: SP.
- Objectif métier: définir comment un PDF original devient une source enregistrée, diagnostiquée page par page et munie d'une route explicite sans conversion canonique encore publiée.
- Agrégats concernés: `SourceDocument` et `DocumentProcessingRun`.
- Intégrations: M-003 consomme les capacités techniques M-002 et prépare les contrats SP qui seront publiés après M-004 via `SourceLocator`.
- Garde-fous: aucun choix implicite de route n'est accepté, aucune bascule silencieuse n'est acceptée, une source en quarantaine n'est pas publiable.

## Langage ubiquitaire M-003

| Terme | Sens M-003 |
|---|---|
| SourceDocument | Agrégat qui possède l'enregistrement du PDF original, son empreinte stable, son état de source et son statut de publication interdit tant que le diagnostic n'est pas routé. |
| DocumentProcessingRun | Agrégat qui possède une tentative de diagnostic et de routage pour un SourceDocument donné. |
| PDF original | Fichier source conservé comme artefact immuable; le système ne le modifie pas. |
| empreinte stable | Hash calculé sur l'original pour identifier la source et refuser les substitutions silencieuses. |
| manifeste de pages | Inventaire complet des pages attendues pour le PDF original. |
| diagnostic de page | Ensemble de signaux observés sur une page: texte natif, image, structure, OCR existant, rotation et lisibilité. |
| route de page | Décision explicite de traitement page par page ou document par document. |
| revue manuelle | État explicite demandé quand la route ne peut pas être décidée sans risque. |
| quarantaine | État bloquant qui interdit toute publication de la source. |

## Agrégats et objets-valeur

| Agrégat | Responsabilité M-003 | Invariants | Événements |
|---|---|---|---|
| SourceDocument | Enregistrer le PDF original immuable, son empreinte stable et son état de source. | L'original reste immuable; une source en quarantaine n'est pas publiable. | SourceDocumentRegistered; SourceDocumentQuarantined |
| DocumentProcessingRun | Construire le manifeste de pages, enregistrer les diagnostics page par page et produire une route explicite. | Chaque page du PDF est représentée; une route incertaine produit une revue manuelle explicite. | PageManifestCreated; PageDiagnosticRecorded; PageRoutePlanned; ManualReviewRequested |

| Objet-valeur | Sens M-003 | Invariants |
|---|---|---|
| OriginalFingerprint | Empreinte stable du PDF original. | Calculée sur le fichier original et jamais remplacée sans nouvelle source. |
| PageManifest | Liste complète des pages attendues. | Le nombre de pages diagnostiquées doit être égal au nombre de pages du manifeste. |
| PageDiagnostic | Signaux observés pour une page. | Les signaux insuffisants ne produisent pas de route implicite. |
| PageRoute | Décision explicite de traitement. | La route doit être nommée et justifiée. |

## Politiques de domaine M-003

| Politique | Décision | Invariants | ADR |
|---|---|---|---|
| SourceRegistrationPolicy | Accepte l'enregistrement seulement avec PDF original, empreinte stable et identité de source explicites. | L'original reste immuable. | DDD-ADR-003 |
| PageManifestCompletenessPolicy | Refuse un diagnostic qui laisse une page hors manifeste. | Chaque page est représentée dans le manifeste. | DDD-ADR-003 |
| PageDiagnosticPolicy | Mesure les signaux de texte natif, image, structure et OCR existant sans publier de conversion. | Le diagnostic précède tout routage; une dégradation physique précède un mélange technique lorsque les deux sont observés. | ADR-002; ADR-003; ADR-033 |
| PageRoutingPolicy | Choisit une route explicite ou demande une revue manuelle. | Une route incertaine produit une revue explicite; aucune bascule silencieuse n'est acceptée; `PREPROCESS_GRANITE` est réservé à `SCAN_DEGRADED` et `BAD_OCR_TO_GRANITE` à un OCR mauvais sans dégradation physique. | ADR-002; ADR-003; ADR-033 |
| QuarantinePublicationPolicy | Bloque toute publication d'une source en quarantaine. | Une source en quarantaine n'est pas publiable. | DDD-ADR-003 |

## Machine d'états M-003

| État | Portée | Sens M-003 | Transition autorisée |
|---|---|---|---|
| REGISTERED | SourceDocument | Le PDF original et son empreinte stable sont enregistrés. | Vers MANIFEST_CREATED. |
| MANIFEST_CREATED | DocumentProcessingRun | Le manifeste de pages couvre toutes les pages attendues. | Vers DIAGNOSED ou QUARANTINED. |
| DIAGNOSED | DocumentProcessingRun | Chaque page possède un diagnostic. | Vers ROUTE_PLANNED, MANUAL_REVIEW ou QUARANTINED. |
| ROUTE_PLANNED | DocumentProcessingRun | Chaque page possède une route explicite et justifiée. | Fin M-003; M-004 pourra consommer la route. |
| MANUAL_REVIEW | DocumentProcessingRun | Une incertitude exige une décision humaine explicite. | Vers ROUTE_PLANNED ou QUARANTINED après décision. |
| QUARANTINED | SourceDocument | La source est bloquée et non publiable. | Fin bloquante tant qu'aucune décision explicite ne la remplace. |

## Comportements vérifiables M-003

| Comportement | Invariant | Scénario BDD | Test RED | ADR | Commande |
|---|---|---|---|---|---|
| SP-001 - Enregistrement immuable | L'original reste immuable et l'empreinte stable identifie la source. | Given un PDF original ajouté; When SP enregistre la source; Then l'original et son empreinte stable sont conservés sans modification. | T-003 | DDD-ADR-003 | uv run --locked gate
| SP-002 - Manifeste complet | Chaque page est représentée dans le manifeste de pages. | Given un SourceDocument enregistré; When le manifeste est créé; Then aucune page du PDF original ne reste hors manifeste. | T-004 | DDD-ADR-003 | uv run --locked gate
| SP-003 - Diagnostic page par page | Chaque page possède un diagnostic avant routage. | Given un manifeste complet; When le diagnostic est demandé; Then chaque page reçoit ses signaux documentaires et leur priorité explicite. | T-005 | ADR-002; ADR-003; ADR-033 | uv run --locked gate
| SP-004 - Routage explicite | La route de page est nommée et justifiée. | Given des diagnostics complets; When la politique de routage s'exécute; Then une dégradation physique est routée `PREPROCESS_GRANITE`, un OCR mauvais non dégradé `BAD_OCR_TO_GRANITE` et une page mixte saine `MIXED_PAGEWISE`. | T-006 | ADR-002; ADR-003; ADR-033 | uv run --locked gate
| SP-005 - Revue manuelle d'incertitude | Une route incertaine produit une revue manuelle explicite. | Given des signaux contradictoires; When aucune route sûre ne peut être décidée; Then SP demande une revue manuelle au lieu de changer de route implicitement. | T-006 | ADR-002; ADR-003 | uv run --locked gate
| SP-006 - Quarantaine non publiable | Une source en quarantaine n'est pas publiable. | Given une source en quarantaine; When une publication est demandée; Then la publication est refusée explicitement. | T-007 | DDD-ADR-003 | uv run --locked gate
| SP-007 - Commandes de validation | Aucun GREEN n'est implicite. | Given la spécification M-003; When les gates sont exécutés; Then le validateur M-003, test et lint sont tous nommés. | T-002 | ADR-002; ADR-003; DDD-ADR-003 | uv run --locked gate
| SP-008 - Contrat HTTP documentaire | Les commandes publiques exposent les statuts et erreurs client sans identifiant interne. | Given un client appelle les commandes documentaires SP; When l'enregistrement ou le diagnostic est demandé; Then les réponses HTTP nomment création, doublon, acceptation, erreurs client et erreurs métier sans fallback. | T-008 | DDD-ADR-003; ADR-010 | uv run --locked gate

## Contrat HTTP M-003

| Endpoint | Succès | Erreurs publiques | Corps public |
|---|---|---|---|
| POST /v1/documents | 201 pour une source créée; 200 avec `DUPLICATE_SOURCE` pour un doublon binaire existant. | 400 `HTTP_REQUEST_INVALID` pour `original_content` absent ou pour tout champ bibliographique désormais interdit; 422 `SOURCE_UNREADABLE` pour PDF corrompu ou chiffré. | Requête multipart limitée à `original_content`; réponse avec `document_id`, `document_status`, et `duplicate` seulement quand le statut est `DUPLICATE_SOURCE`. |
| POST /v1/documents/{id}/diagnose | 202 `DIAGNOSTIC_REQUESTED` quand le job `DIAGNOSE` est accepté. | 400 `HTTP_REQUEST_INVALID` pour `document_id` invalide; 404 `SOURCE_NOT_FOUND`; 409 `DIAGNOSTIC_ALREADY_REQUESTED`. | `document_id` et `diagnostic_status`, sans `processing_run_id`, sans `original_storage_ref` et sans route. |

## Commandes de validation

La commande sans `-Path` cible exclusivement `docs/specs/m003_source_enregistree_diagnostiquee_routee.md`.

```console
uv run --locked gate
uv run --locked gate
uv run --locked gate
uv run --locked gate
```

## Exclusions M-004

- M-003 ne publie aucune version canonique.
- M-003 ne produit pas le Docling JSON final.
- M-003 ne décide pas l'autorité textuelle unique par page.
- M-003 ne publie aucun `CanonicalSourcePublished` vers KA ou EG.
- M-003 n'introduit pas Docling comme modèle de domaine; Docling reste un outil de conversion gouverné par les politiques SP ultérieures.
