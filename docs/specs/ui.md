# UI minimale - ingestion PDF et conversation documentée

## Statut

- Objet: spécification produit transverse pour l'interface locale minimale du chatbot.
- Portée: ingestion d'un PDF local, préparation documentaire, indexation, conversation et ouverture des preuves.
- Sources normatives: `docs/specs/m003_source_enregistree_diagnostiquee_routee.md`, `docs/specs/m004_version_canonique_publiee.md`, `docs/specs/m005_projection_connaissance_recherchable.md`, `docs/specs/m007_reponse_documentaire_verifiee.md`, `docs/specs/m008_conversation_produit.md`, `docs/specs/m013_durcissement_acceptation_v1.md`, `docs/user/v1_guide_utilisateur.md`, `docs/runbooks/ingestion_pdf.md` et `docs/runbooks/conversation_v1.md`.
- ADR consultées: ADR-001, ADR-002, ADR-003, ADR-004, ADR-005, ADR-006, ADR-008, ADR-009, ADR-010, DDD-ADR-003, DDD-ADR-004, DDD-ADR-005, DDD-ADR-007 et DDD-ADR-008.
- ADR: non requise, car cette spécification applique les contrats existants sans créer de nouvelle topologie, sans stockage métier UI et sans accès direct au Spark, à Qdrant, à SP, KA, EG ou RA internes.
- Nature du changement: conception documentaire. Ce fichier ne livre aucune implémentation `app/...`.

## Scénario BDD principal

- Given un utilisateur exploite la V1 localement avec un PDF original identifié.
- When il ajoute le PDF, le rend interrogeable, ouvre une conversation et pose une question.
- Then l'UI affiche les étapes documentaires, la projection recherchable, la réponse, les citations, les lacunes, les contradictions et les pannes explicites sans fallback silencieux.

## Mission

L'UI minimale doit permettre à un utilisateur non technique d'utiliser le chatbot local sans passer par les commandes PowerShell pour le parcours courant: ajouter un PDF, attendre qu'il devienne interrogeable, poser une question et vérifier les preuves.

L'UI n'est pas un nouveau bounded context métier. Elle est un client local des contrats publics et des read-models nécessaires. Elle ne décide aucune vérité documentaire, ne choisit aucune route documentaire implicite, ne publie aucun brouillon LLM comme réponse, ne remplace aucune projection indisponible et ne masque aucune panne.

La cible ergonomique est un outil de travail sobre, pas une landing page. Le premier écran est l'espace opérationnel: état local, corpus, conversation et preuves.

## Principe de surface minimale

Une zone de chargement PDF et une zone de chat ne suffisent pas. Pour que le pipeline soit réellement utilisable, l'interface minimale comprend six surfaces:

| Surface | Rôle | Obligatoire pour |
|---|---|---|
| État local | Afficher santé API, files de jobs, `llm-gateway`, Spark, stockage local et erreurs publiques. | Éviter de soumettre une action quand une dépendance bloquante est déjà connue. |
| Corpus PDF | Ajouter un PDF, renseigner ses métadonnées, suivre diagnostic, routage, conversion et indexation. | Transformer un fichier local en source interrogeable. |
| Détails documentaires | Montrer pages en revue, quarantaine, version canonique, projection et erreurs. | Ne jamais confondre source chargée et source prête pour RA. |
| Conversation | Créer une conversation, envoyer un message, afficher question résolue, mode, justification, statut et réponse. | Utiliser CV et RA sans exposer l'historique comme preuve. |
| Preuves et citations | Ouvrir les citations, SourceLocator, page, fragment, statut de support, lacunes et contradictions. | Vérifier la réponse au lieu de faire confiance au texte généré. |
| Journal d'événements public | Afficher les dernières commandes, statuts publics et identifiants utiles. | Diagnostiquer explicitement une limite sans logs sensibles. |

## Disposition minimale

L'écran principal est une application locale en trois colonnes, avec une barre d'état supérieure:

| Zone | Contenu minimal | Comportement |
|---|---|---|
| Barre supérieure | Statut local global, statut `llm-gateway`, statut Spark, nombre de jobs bloqués, dernier code d'erreur public. | Un statut bloquant affiche le code public et la prochaine action autorisée. |
| Colonne gauche | Bibliothèque PDF, bouton d'ajout, filtres par statut, fiche du document sélectionné. | Un document non `SEARCHABLE` reste visible mais non sélectionnable pour une question RA. |
| Colonne centrale | Conversation active, historique append-only, champ de message, mandat, documents sélectionnés, mode demandé facultatif. | L'envoi crée un tour; la réponse n'est affichée comme factuelle qu'après statut public final. |
| Colonne droite | Citations, SourceLocator, page, fragment, lacunes, contradictions, trace publique et détails de réponse. | Chaque citation ouvrable pointe vers la source et la version canonique utilisées. |

Sur mobile ou fenêtre étroite, ces zones deviennent quatre onglets: `État`, `PDF`, `Conversation`, `Preuves`. Les mêmes informations restent accessibles sans masquer les erreurs.

## Flux utilisateur minimal

### 1. Vérifier l'état local

L'UI affiche un état local avant toute action documentaire ou conversationnelle.

États bloquants attendus:

- `LLM_UNAVAILABLE`, `LLM_FIRST_TOKEN_TIMEOUT`, `LLM_TLS_CERTIFICATE_INVALID`, `LLM_AUTHENTICATION_FAILED`, `LLM_PARTIAL_OUTPUT` ou `LLM_CIRCUIT_OPEN` pour le chemin LLM.
- `SEARCH_INDEX_UNAVAILABLE`, `PROJECTION_STALE` ou `PROJECTION_NOT_FOUND` pour la recherche.
- `SOURCE_QUARANTINED`, `SOURCE_NOT_ROUTED`, `SOURCE_NOT_CANONICAL` ou `PAGE_AUTHORITY_MISSING` pour le pipeline documentaire.

Une action bloquée reste visible avec sa raison. L'UI ne remplace pas l'action par une autre action et ne bascule jamais vers un fournisseur, une projection, un mode ou une source alternative.

### 2. Ajouter un PDF

Le formulaire d'ajout demande explicitement:

| Champ | Règle UI |
|---|---|
| Fichier PDF original | Obligatoire. Le fichier est envoyé comme `original_content`. |
| Titre documentaire | Obligatoire dans `bibliographic_metadata`; le nom de fichier ne devient pas titre par défaut. |
| Émetteur ou origine | Obligatoire dans `bibliographic_metadata`; aucune origine implicite. |
| Date documentaire | Obligatoire ou marquée explicitement `DATE_NON_RENSEIGNEE` par l'utilisateur. |
| Type documentaire | Obligatoire parmi les types supportés par la configuration locale. |
| Langue principale | Obligatoire ou marquée explicitement `LANGUE_NON_RENSEIGNEE` par l'utilisateur. |

Commande appelée:

```http
POST /v1/documents
```

Résultat affiché:

- `document_id`;
- `document_status`;
- indicateur `duplicate` si `DUPLICATE_SOURCE`;
- code public en cas de refus, notamment `HTTP_REQUEST_INVALID` ou `SOURCE_UNREADABLE`.

### 3. Préparer le PDF

Après enregistrement, l'UI propose les étapes dans l'ordre du pipeline:

| Étape | Commande | Condition d'accès | Résultat visible |
|---|---|---|---|
| Diagnostic | `POST /v1/documents/{document_id}/diagnose` | Source enregistrée ou doublon accepté. | `diagnostic_status`, progression publique et erreurs. |
| Revue explicite | Read-model documentaire. | Route incertaine, page bloquée ou quarantaine. | Pages concernées, motif et action autorisée. |
| Conversion canonique | `POST /v1/documents/{document_id}/convert` | Route explicite et source non quarantainée. | `conversion_status`, `canonical_version_id` si accepté. |
| Indexation | `POST /v1/documents/{document_id}/index` | Version canonique acceptée. | `projection_id`, `projection_status`, `canonical_version_id`. |

L'UI ne déclenche pas automatiquement la conversion ou l'indexation après une étape ambiguë. En cas de `MANUAL_REVIEW`, `QUARANTINE`, `REJECTED`, `FAILED`, `SOURCE_NOT_ROUTED`, `PAGE_AUTHORITY_MISSING` ou `PROJECTION_PROFILE_INVALID`, elle arrête le flux et affiche l'action explicite requise.

Le profil de projection ne peut pas être implicite. Si plusieurs profils existent, l'utilisateur choisit un profil exposé par la configuration locale. Si aucun profil n'est disponible, l'indexation est bloquée avec une erreur publique.

### 4. Sélectionner les documents interrogeables

Un document devient sélectionnable pour la conversation seulement si:

- une version canonique est publiée ou acceptée;
- une projection KA existe;
- la projection est `SEARCHABLE`;
- aucun statut bloquant actif ne concerne la source, la version canonique ou la projection.

Un document chargé mais non indexé reste visible dans le corpus avec son état réel. L'UI ne le présente jamais comme utilisable par le chatbot.

### 5. Ouvrir une conversation

Le formulaire de conversation demande explicitement:

| Champ | Règle UI |
|---|---|
| Titre | Obligatoire. |
| Mandat par défaut | Obligatoire; il décrit univers autorisé, horizon, langue, niveau de détail et exclusions. |
| Préférences de présentation | Obligatoires; aucune préférence implicite. |
| Documents sélectionnés | Facultatifs, mais seuls les documents `SEARCHABLE` peuvent être transmis. |

Commande appelée:

```http
POST /v1/conversations
```

L'UI lit ensuite la conversation et ses tours via:

```http
GET /v1/conversations/{conversation_id}
GET /v1/conversations/{conversation_id}/turns
```

### 6. Poser une question

Le champ de message envoie:

- `message`;
- `idempotency_key` générée une seule fois par tentative d'envoi;
- `occurred_at`;
- `research_mandate` si le message remplace le mandat par défaut;
- `selected_documents` si l'utilisateur borne explicitement la réponse;
- `requested_mode` seulement si l'utilisateur force un mode supporté.

Commande appelée par l'UI native:

```http
POST /v1/conversations/{conversation_id}/messages
```

`POST /v1/chat/completions` reste réservé à la compatibilité client externe. L'UI produit doit utiliser le contrat CV pour conserver les champs produit: `resolved_question`, `mode`, `mode_justification`, `support_status`, `citations`, `knowledge_gaps` et `unresolved_conflicts`.

Une réponse conversationnelle affiche:

- la question autonome résolue;
- le mode choisi et sa justification;
- le statut documentaire;
- le texte de réponse si publiable;
- les citations ouvrables;
- les lacunes documentaires;
- les contradictions non résolues;
- l'identifiant de conversation, de tour et de réponse quand il existe.

L'historique de conversation n'est jamais affiché comme preuve. Une réutilisation d'assertion historique doit être présentée comme réutilisation vérifiée ou revalidation RA, jamais comme souvenir suffisant.

### 7. Vérifier les preuves

Le panneau de preuves affiche chaque citation avec:

- `SourceLocator`;
- titre documentaire;
- `document_id`;
- `canonical_version_id`;
- page;
- fragment ou item cité;
- hash de contenu ou hash de span si exposé;
- statut de résolution;
- lien d'ouverture locale.

Une citation non ouvrable bloque le statut supporté et affiche `ANSWER_CITATION_UNRESOLVABLE`. L'UI ne remplace pas une citation invalide par un chemin de fichier, un extrait voisin ou une recherche libre.

## Contrats UI à prévoir côté backend

Les commandes publiques existantes ne suffisent pas à rendre une UI exploitable: l'utilisateur doit lire l'état courant entre deux commandes. Les read-models suivants sont donc requis avant une implémentation complète de l'UI. Ils peuvent être exposés par les contextes propriétaires ou par un adaptateur UI sans stockage métier.

| Besoin UI | Propriétaire métier | Données minimales | Interdits |
|---|---|---|---|
| Lire l'état local global. | `platform` | santé API, file de jobs, statut `llm-gateway`, statut Spark, dernier code public, horodatage. | prompt complet, secret, preuve complète, réponse complète. |
| Lister les documents. | SP avec projection de lecture KA. | `document_id`, titre, statut source, statut diagnostic, statut conversion, `canonical_version_id`, statut projection. | `original_storage_ref`, tables SP, collection Qdrant. |
| Lire un document. | SP. | métadonnées publiques, pages en revue, quarantaine, version canonique, SourceLocator ouvrables. | artefacts internes de conversion non publiés. |
| Lire une projection. | KA. | `projection_id`, `canonical_version_id`, `projection_status`, profil public, fraîcheur. | `qdrant_collection`, identifiants de points, paramètres internes non publiés. |
| Résoudre une citation. | SP via langage SourceLocator. | page, item, coordonnées si disponibles, hash et aperçu local borné. | substitution de source ou lecture directe d'un stockage interne. |
| Lire une réponse présentée. | CV/RA. | statut, texte publié, citations, lacunes, contradictions, identifiants publics. | brouillon, prompt, override de support, stockage RA. |

Si ces lectures n'existent pas encore, l'UI doit être considérée non implémentable proprement. Elle ne doit pas reconstruire ces états depuis les logs, les chemins locaux, les collections techniques ou les tables internes.

## États publics affichables

### Documents et projections

| État | Sens UI |
|---|---|
| `SOURCE_REGISTERED` | PDF enregistré, pas encore forcément diagnostiqué. |
| `DUPLICATE_SOURCE` | Source binaire déjà connue; l'UI affiche l'identité existante. |
| `DIAGNOSTIC_REQUESTED` | Diagnostic accepté et en attente ou en cours. |
| `ROUTE_EXPLICIT` | Route documentaire décidée explicitement. |
| `MANUAL_REVIEW` | Décision humaine requise avant poursuite. |
| `SOURCE_QUARANTINED` | Source bloquée et non publiable. |
| `CONVERSION_REQUESTED` | Conversion canonique demandée. |
| `CANONICAL_ACCEPTED` | Version canonique acceptée et référençable. |
| `INDEXATION_REQUESTED` | Projection demandée. |
| `REQUESTED`, `BUILDING`, `BUILT`, `INDEXING` | Projection non encore interrogeable. |
| `SEARCHABLE` | Projection utilisable par RA via KA. |
| `STALE`, `FAILED`, `RETIRED` | Projection non utilisable sans action explicite. |

### Conversation et réponse

| État | Sens UI |
|---|---|
| `SUPPORTED` | Réponse supportée par citations directes. |
| `PARTIALLY_SUPPORTED` | Réponse utilisable avec limites visibles. |
| `INSUFFICIENT_EVIDENCE` | Preuves insuffisantes; abstention ou réponse limitée. |
| `CONFLICTING_EVIDENCE` | Contradiction non résolue; pas de conclusion simplifiée. |
| `REQUIRES_CURRENT_DATA` ou `CURRENT_DATA_REQUIRED` | Données actuelles requises mais non autorisées. |
| `FOLLOW_UP_AMBIGUOUS` | Question de suivi ambiguë; clarification requise. |
| `CONVERSATION_MODE_UNSUPPORTED` | Mode demandé ou sélectionné refusé. |
| `HISTORICAL_ASSERTION_REVALIDATION_REQUIRED` | Assertion historique non réutilisable sans RA. |
| `LLM_UNAVAILABLE` et statuts LLM M-013 | Panne Spark ou gateway explicitement visible. |

## Comportements vérifiables UI

| Comportement | Invariant | Scénario BDD |
|---|---|---|
| UI-001 - État local visible | Une dépendance bloquante interdit l'action concernée sans proposer de chemin alternatif. | Given Spark est indisponible; When l'utilisateur ouvre l'UI; Then l'état `LLM_UNAVAILABLE` est visible et aucun fournisseur de secours n'est proposé. |
| UI-002 - PDF enregistré avec métadonnées explicites | Le PDF original et ses métadonnées sont requis. | Given un PDF sans titre documentaire; When l'utilisateur tente l'ajout; Then l'UI refuse l'envoi avant `POST /v1/documents`. |
| UI-003 - Préparation documentaire ordonnée | Diagnostic, revue, conversion et indexation restent des étapes distinctes. | Given une source route incertaine; When le diagnostic produit `MANUAL_REVIEW`; Then l'UI bloque conversion et indexation. |
| UI-004 - Chat limité aux projections recherchables | Une source chargée mais non `SEARCHABLE` ne peut pas être sélectionnée comme corpus RA. | Given un PDF `SOURCE_REGISTERED`; When l'utilisateur prépare une question; Then le document reste non sélectionnable pour `selected_documents`. |
| UI-005 - Conversation append-only et statutée | Chaque message affiche question résolue, mode, justification et statut. | Given une conversation active; When l'utilisateur pose une question; Then le tour présenté contient `resolved_question`, `mode`, `mode_justification` et `support_status`. |
| UI-006 - Citations ouvrables | Une réponse supportée exige des citations résolubles. | Given RA retourne une citation; When l'utilisateur l'ouvre; Then l'UI affiche SourceLocator, page et version canonique. |
| UI-007 - Abstention visible | Une lacune ou donnée actuelle manquante n'est pas reformulée en réponse affirmative. | Given RA retourne `CURRENT_DATA_REQUIRED`; When la réponse est présentée; Then l'UI affiche l'abstention et la raison publique. |
| UI-008 - Payloads sensibles absents | L'UI ne rend pas publics prompt complet, brouillon, preuve complète, secret ou stockage interne. | Given une erreur publique survient; When le journal UI l'affiche; Then seuls code public, identifiants publics et horodatage sont visibles. |

## Exclusions

- Pas de chat générique directement branché au LLM.
- Pas d'appel navigateur direct vers Spark, vLLM, Qdrant, PostgreSQL ou stockage documentaire interne.
- Pas de recherche libre KA exposée à l'utilisateur final hors flux RA/CV.
- Pas de correction OCR ou édition documentaire silencieuse dans l'UI minimale.
- Pas de promesse financière, conseil d'investissement ou donnée de marché inventée.
- Pas de suppression ou purge administrative depuis l'UI minimale.
- Pas de publication publique externe; l'interface reste locale.

