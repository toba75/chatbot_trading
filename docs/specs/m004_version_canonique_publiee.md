# M-004 - Version canonique publiée

## Statut

- Milestone: M-004 - Version canonique publiée.
- Source canonique: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M-004 - Version canonique publiée`.
- Spécification normative: `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 5, 12, 14, 17, 19, 20 et 21.
- ADR consultées: ADR-001, ADR-002, ADR-003, ADR-004, ADR-010, DDD-ADR-003, DDD-ADR-006, DDD-ADR-008, DDD-ADR-010.
- Contrats amont: `docs/specs/m003_source_enregistree_diagnostiquee_routee.md`, `docs/specs/m001_frontieres_ddd_contrats_publies.md`.
- ADR: non requise, car M-004 applique les décisions existantes sur les artefacts canoniques, le routage hybride, OCRmyPDF conditionnel, l'autorité textuelle unique, SourceLocator, l'outbox, la cohérence éventuelle, les gates uv run --locked gate

## Scénario BDD

- Given une source M-003 enregistrée, diagnostiquée et routée.
- When la spécification M-004 est publiée.
- Then chaque comportement de version canonique nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.

## Mission

M-004 publie le contrat exécutable du bounded context SP pour produire une `CanonicalSource` structurée, contrôlée, immutable et publiable depuis une source M-003 routée. M-004 transforme les sorties page par page en un `DoclingDocument unique`, sérialise un `Docling JSON canonique`, vérifie les contrôles qualité pré et post-conversion, puis publie une version canonique immuable vers les contextes aval.

Le PDF original reste la référence éditoriale et visuelle. Les exports Markdown, HTML, texte, tables, figures et aperçus restent des artefacts dérivés et régénérables, jamais la source de vérité.

## Contexte DDD

- Domaine: traitement des sources documentaires.
- Bounded context: SP.
- Objectif métier: convertir les pages routées en `DoclingDocument unique`, choisir une autorité textuelle unique par page et publier une version canonique immuable.
- Agrégat propriétaire: `CanonicalSource`.
- Intégrations: M-004 consomme les routes explicites M-003 et publie `CanonicalSourcePublished` vers KA et EG par outbox.
- Garde-fous: aucune source en quarantaine n'est publiable; aucun fallback Docling vers Granite n'est silencieux; aucune transcription concurrente n'est fusionnée silencieusement; aucune page ne peut être omise.
- Chaque page possède exactement une autorité textuelle unique.

## Langage ubiquitaire M-004

| Terme | Sens M-004 |
|---|---|
| CanonicalSource | Agrégat qui possède une version canonique acceptée, publiable et immutable. |
| CanonicalVersionId | Identifiant de version immuable; une correction en crée un nouveau. |
| DoclingDocument unique | Représentation structurée obtenue par fusion pagewise dans l'ordre du PDF original. |
| Docling JSON canonique | Artefact canonique sérialisé depuis le DoclingDocument contrôlé. |
| TextAuthorityManifest | Manifeste qui associe chaque page à son autorité textuelle retenue. |
| SourceLocator | Langage publié qui résout document, version canonique, page, item et hash de contenu. |

## Agrégats et objets-valeur

| Agrégat | Responsabilité M-004 | Invariants | Événements |
|---|---|---|---|
| CanonicalSource | Publier ou superséder une version canonique acceptée. | La version publiée est immuable; une correction crée une nouvelle version canonique et ne modifie jamais la version publiée en place; une source en quarantaine n'est pas publiable. | CanonicalSourcePublished; CanonicalSourceSuperseded |

| Objet-valeur | Sens M-004 | Invariants |
|---|---|---|
| CanonicalVersionId | Identité stable d'une version canonique. | Jamais réutilisée pour une correction. |
| CanonicalArtifactRef | Référence vers le Docling JSON canonique. | Pointe vers un artefact contrôlé. |
| TextAuthorityManifest | Autorité textuelle retenue page par page. | Chaque page possède une seule autorité. |
| QualityDecision | Verdict de QA pré et post-conversion. | Toute alerte bloquante refuse la publication. |
| CanonicalArtifactHash | Hash de contenu canonique. | Identique tant que la version est immuable. |

## Politiques normatives M-004

| Politique | Décision | Invariants | ADR |
|---|---|---|---|
| TextAuthoritySelectionPolicy | Sélectionne l'autorité textuelle unique d'une page. | Les transcriptions concurrentes ne sont pas fusionnées silencieusement. | ADR-004 |
| CanonicalAcceptancePolicy | Décide si la conversion peut devenir `CanonicalSource`. | Aucune page ne peut être omise; une source en quarantaine est refusée. | ADR-001; ADR-002; ADR-003; ADR-004; DDD-ADR-003 |
| CriticalPageSamplingPolicy | Choisit les pages critiques pour contrôle renforcé. | Les tableaux, formules, pages faibles et routes minoritaires sont échantillonnés. | ADR-002; ADR-003; ADR-004 |

## Machine d'états M-004

| État | Portée | Sens M-004 | Transition autorisée |
|---|---|---|---|
| ROUTED | DocumentProcessingRun | M-003 a produit une route explicite. | Vers PRE_QA_PASSED ou QUARANTINED. |
| PRE_QA_PASSED | DocumentProcessingRun | Les pages critiques et routes sont admissibles avant conversion. | Vers CONVERTED. |
| CONVERTED | DocumentProcessingRun | Les sorties de pages sont produites. | Vers POST_QA_PASSED ou REJECTED. |
| POST_QA_PASSED | DocumentProcessingRun | Le DoclingDocument unique satisfait les contrôles. | Vers ACCEPTED. |
| ACCEPTED | CanonicalSource | La version canonique est acceptée. | Vers PUBLISHED. |
| PUBLISHED | CanonicalSource | `CanonicalSourcePublished` peut être émis. | Vers SUPERSEDED. |
| SUPERSEDED | CanonicalSource | Une version plus récente remplace la version courante. | Terminale. |
| QUARANTINED | DocumentProcessingRun | Publication interdite. | Terminale tant qu'une décision explicite ne relance pas une nouvelle tentative. |
| REJECTED | DocumentProcessingRun | QA ou invariants refusent la conversion. | Terminale. |

## Fusion pagewise vers DoclingDocument unique

La fusion pagewise crée un `DoclingDocument unique` à partir des sorties de chaque page routée. Elle ajoute chaque page dans l'ordre du PDF original, conserve le numéro de page PDF, normalise les coordonnées, maintient des identifiants d'items uniques et relie chaque item au PDF original par `SourceLocator`. Aucune page ne peut être omise.

Les routes mixtes ne produisent pas plusieurs documents canoniques concurrents. Les sorties natives, Granite-Docling ou OCR amont explicitement retenues restent auditables, mais seule l'autorité textuelle choisie par `TextAuthoritySelectionPolicy` alimente le contenu canonique de la page.

## QA pré-conversion

La QA pré-conversion contrôle les pages critiques choisies par `CriticalPageSamplingPolicy`, les routes minoritaires, les tableaux, les formules, les pages à faible confiance et les pages complexes avant conversion.

Les statuts admis sont `PASS`, `PASS_WITH_WARNINGS`, `RETRY_WITH_ALTERNATIVE_ROUTE`, `MANUAL_REVIEW` et `QUARANTINE`. Une route incertaine ne déclenche pas de traitement alternatif silencieux; elle produit une revue, une relance explicite ou une quarantaine.

## QA post-conversion

La QA post-conversion contrôle le nombre de pages, le JSON valide, les identifiants uniques, l'ordre des pages, la provenance de chaque item, les coordonnées, les nombres, signes négatifs, pourcentages, séparateurs décimaux, tableaux, figures et l'autorité textuelle enregistrée.

`CanonicalAcceptancePolicy` refuse toute version candidate qui laisse une page sans autorité, qui référence une page inexistante, qui produit un item sans `SourceLocator`, qui perd une page du manifeste ou qui transforme une alerte bloquante en avertissement non bloquant.

## Événements M-004

| Événement | Déclencheur | Payload publié |
|---|---|---|
| CanonicalSourcePublished | La version est publiée vers KA et EG. | `CanonicalSourceRef` contractuel; `canonical_artifact_sha256` inclus; `SourceLocator` résolu via le registre T-007 |
| CanonicalSourceSuperseded | Une correction publie une nouvelle version. | previous_canonical_version_id; new_canonical_version_id |
| CanonicalAuditEvent | Une publication, un refus QA ou une quarantaine post-canonique doit être observé. | trace_id; document_id; canonical_version_id; phase; status; page_count; pages_rejected_by_qa; ambiguous_text_authorities; artifact_hash; error_code |
| PreCanonicalAuditEvent | Une demande de conversion est acceptée ou refusée avant existence d'une version canonique. | trace_id; document_id; phase; status; page_count; error_code; canonical_version_id nul; artifact_hash nul |

## Comportements vérifiables M-004

| Comportement | Invariant | Scénario BDD | Test RED | ADR | Commande |
|---|---|---|---|---|---|
| SP-009 - Spécification exécutable M-004 | La spécification nomme mission, agrégat, politiques, QA, HTTP, ADR et exclusions. | Given une source M-003 routée; When la spécification M-004 est publiée; Then elle est validée par commande uv run --locked gate
| SP-010 - Fusion pagewise vers DoclingDocument unique | Aucune page ne peut être omise. | Given des pages routées; When la conversion fusionne les sorties; Then le DoclingDocument unique conserve toutes les pages dans l'ordre. | T-003 | ADR-001; ADR-002; ADR-003; ADR-004 | uv run --locked gate
| SP-011 - Autorité textuelle unique par page | Chaque page possède une seule autorité. | Given une sortie native et Granite; When TextAuthoritySelectionPolicy arbitre; Then une seule autorité est retenue. | T-004 | ADR-004 | uv run --locked gate
| SP-012 - QA pré et post-conversion | Les pages critiques et le Docling JSON sont contrôlés. | Given une conversion candidate; When CanonicalAcceptancePolicy évalue la version; Then les chiffres, signes, tableaux et provenance sont vérifiés. | T-005 | ADR-001; ADR-002; ADR-003; ADR-004 | uv run --locked gate
| SP-013 - Publication immuable | Une correction crée une nouvelle version. | Given une version publiée; When une correction est acceptée; Then l'ancienne version reste résolvable et une nouvelle version est publiée. | T-006 | ADR-001; DDD-ADR-003; DDD-ADR-010 | uv run --locked gate
| SP-014 - SourceLocator résolvable | Tout item canonique pointe vers document, version, page, item et hash. | Given un item canonique; When un contexte aval ouvre sa preuve; Then SourceLocator résout l'item sans lire les tables SP. | T-007 | DDD-ADR-003 | uv run --locked gate
| SP-015 - Événement CanonicalSourcePublished | SP est l'unique producteur de CanonicalSourcePublished. | Given une CanonicalSource publiée; When l'outbox publie l'événement; Then KA et EG reçoivent une référence idempotente. | T-008 | ADR-001; DDD-ADR-003; DDD-ADR-006; DDD-ADR-008 | uv run --locked gate
| SP-016 - Contrat HTTP de conversion | Le client ne voit que les statuts publics et erreurs stables. | Given un client appelle POST /v1/documents/{id}/convert; When la commande est acceptée ou refusée; Then la réponse ne divulgue pas d'identifiant interne. | T-009 | ADR-010; DDD-ADR-003; DDD-ADR-006; DDD-ADR-008 | uv run --locked gate
| SP-017 - Traçabilité et gates M-004 | Aucun GREEN n'est implicite. | Given les preuves M-004; When les gates s'exécutent; Then test, lint et uv run --locked gate sont enrôlés. | T-010 | ADR-001; ADR-004; ADR-010; DDD-ADR-003; DDD-ADR-006; DDD-ADR-008 | uv run --locked gate

## Contrat HTTP M-004

| Endpoint | Succès | Erreurs publiques | Corps public |
|---|---|---|---|
| POST /v1/documents/{id}/convert | 202 `CONVERSION_REQUESTED` quand la source routée est acceptée pour conversion; 202 `CANONICAL_ACCEPTED` quand la version canonique est déjà acceptée. | 400 `HTTP_REQUEST_INVALID`; 404 `SOURCE_NOT_FOUND`; 409 `SOURCE_NOT_ROUTED`; 409 `SOURCE_QUARANTINED`; 409 `CONVERSION_ALREADY_REQUESTED`; 422 `PAGE_AUTHORITY_MISSING`; 422 `SOURCE_NOT_CANONICAL`. | `document_id`; `conversion_status`; `canonical_version_id` seulement avec `CANONICAL_ACCEPTED`. |

## Commandes de validation

La commande sans `-Path` cible exclusivement `docs/specs/m004_version_canonique_publiee.md`.

```console
uv run --locked gate
uv run --locked gate
uv run --locked gate
uv run --locked gate
```

## Exclusions M-005

- M-004 ne crée aucune `KnowledgeProjection`.
- M-004 n'indexe rien dans Qdrant.
- M-004 ne découpe pas les chunks de recherche.
- M-004 ne déclenche pas `POST /v1/search`.
- M-004 ne calcule ni embeddings ni métriques Recall@k, MRR ou nDCG.
- M-004 ne transforme pas `DoclingDocument` en modèle universel aval; les contextes aval consomment des références publiées.
