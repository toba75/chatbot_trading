# UI minimale - ingestion PDF et conversation documentée

## Statut

- Objet: spécification produit transverse pour l'interface locale minimale du chatbot.
- Portée: ingestion d'un PDF local, préparation documentaire, indexation, conversation et ouverture des preuves.
- Sources normatives: `docs/specs/m003_source_enregistree_diagnostiquee_routee.md`, `docs/specs/m004_version_canonique_publiee.md`, `docs/specs/m005_projection_connaissance_recherchable.md`, `docs/specs/m007_reponse_documentaire_verifiee.md`, `docs/specs/m008_conversation_produit.md`, `docs/specs/m013_durcissement_acceptation_v1.md`, `docs/user/v1_guide_utilisateur.md`, `docs/runbooks/ingestion_pdf.md` et `docs/runbooks/conversation_v1.md`.
- ADR consultées: ADR-001, ADR-002, ADR-003, ADR-004, ADR-005, ADR-006, ADR-008, ADR-009, ADR-010, ADR-018, DDD-ADR-003, DDD-ADR-004, DDD-ADR-005, DDD-ADR-007 et DDD-ADR-008.
- ADR applicable: ADR-018 impose que l'UI utilise exclusivement les contrats publics de `orchestrator-api`, sans accès métier direct, simulation de capacité absente ni fallback.
- Nature du changement: conception documentaire. Ce fichier ne livre aucune implémentation `app/...`.

## Scénario BDD principal

- Given un utilisateur exploite la V1 localement avec un PDF original identifié.
- When il ajoute le PDF, le rend interrogeable, ouvre une conversation et pose une question.
- Then l'UI affiche les sorties observables de chaque étape documentaire, la projection recherchable, la réponse, les citations, les lacunes, les contradictions et les pannes explicites sans fallback silencieux.

## Mission

L'UI minimale doit permettre à un utilisateur non technique d'utiliser le chatbot local sans passer par les commandes PowerShell pour le parcours courant: ajouter un PDF, attendre qu'il devienne interrogeable, poser une question et vérifier les preuves.

L'UI n'est pas un nouveau bounded context métier. Elle est un client local des contrats publics et des read-models nécessaires. Elle ne décide aucune vérité documentaire, ne choisit aucune route documentaire implicite, ne publie aucun brouillon LLM comme réponse, ne remplace aucune projection indisponible et ne masque aucune panne.

L'UI doit permettre à l'utilisateur de juger visuellement les sorties du pipeline avant d'utiliser le document dans une conversation. Cette visualisation n'ajoute pas un statut métier `APPROUVE_PAR_UTILISATEUR`, ne demande pas une validation explicite à chaque étape et ne bloque pas une étape non ambiguë dans l'attente d'un accord humain.

La cible ergonomique est un outil de travail sobre, pas une landing page. Le premier écran est l'espace opérationnel: état local, corpus, conversation et preuves.

## Frontière UI/API orchestratrice obligatoire

Toute commande, lecture ou récupération de contenu métier initiée par l'UI passe exclusivement par un contrat public de `orchestrator-api`. L'UI reste un adaptateur de présentation et ne devient ni une façade métier concurrente, ni un client direct des composants internes.

Si le contrat API requis est absent ou n'est pas câblé au cas d'usage réel, la fonction UI correspondante reste explicitement non opérationnelle. Il en va de même si le contrat est indisponible. L'UI ne doit ni mocker, ni stuber, ni faker, ni simuler cette capacité; elle ne doit pas produire une réponse synthétique, conserver un état métier substitutif ou déclencher un fallback vers un fichier, un repository, une file de jobs, un worker ou un service interne.

Les doubles de test restent autorisés uniquement dans des tests automatisés isolés. Ils ne constituent jamais une preuve que le chemin UI réel est raccordé à l'application.

Scénario BDD de frontière:

- Given une action de l'UI dépend d'une capacité applicative.
- When l'utilisateur déclenche cette action.
- Then l'UI appelle le contrat public correspondant de `orchestrator-api` câblé au cas d'usage réel et présente sa réponse réelle; si le contrat est absent, non câblé ou indisponible, elle affiche un blocage explicite sans comportement de substitution.

## Principe de surface minimale

Une zone de chargement PDF et une zone de chat ne suffisent pas. Pour que le pipeline soit réellement utilisable, l'interface minimale comprend six surfaces:

| Surface | Rôle | Obligatoire pour |
|---|---|---|
| État local | Afficher santé API, files de jobs, `llm-gateway`, Spark, stockage local et erreurs publiques. | Éviter de soumettre une action quand une dépendance bloquante est déjà connue. |
| Corpus PDF | Ajouter un PDF, renseigner ses métadonnées, suivre diagnostic, routage, conversion et indexation. | Transformer un fichier local en source interrogeable. |
| Détails documentaires | Montrer métadonnées retenues, empreinte, manifeste, diagnostics, routes, QA, version canonique, projection et erreurs. | Ne jamais confondre source chargée et source prête pour RA. |
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

| Étape | Commande | Condition d'accès | Résultat visible immédiat |
|---|---|---|---|
| Diagnostic | `POST /v1/documents/{document_id}/diagnose` | Source enregistrée ou doublon accepté. | `diagnostic_status`, progression publique, manifeste, diagnostics page par page et erreurs. |
| Revue explicite | Read-model documentaire. | Route incertaine, page bloquée ou quarantaine. | Pages concernées, motif, route proposée ou absence de route, et action autorisée uniquement si le pipeline l'exige. |
| Conversion canonique | `POST /v1/documents/{document_id}/convert` | Route explicite et source non quarantainée. | `conversion_status`, QA pré/post-conversion, `TextAuthorityManifest`, `canonical_version_id` et hash canonique si accepté. |
| Indexation | `POST /v1/documents/{document_id}/index` | Version canonique acceptée. | `projection_id`, profil, nombre de chunks, fraîcheur, `projection_status`, `canonical_version_id`. |

L'UI ne déclenche pas automatiquement la conversion ou l'indexation après une étape ambiguë. En cas de `MANUAL_REVIEW`, `QUARANTINE`, `REJECTED`, `FAILED`, `SOURCE_NOT_ROUTED`, `PAGE_AUTHORITY_MISSING` ou `PROJECTION_PROFILE_INVALID`, elle arrête le flux et affiche l'action explicite requise.

Le profil de projection ne peut pas être implicite. Si plusieurs profils existent, l'utilisateur choisit un profil exposé par la configuration locale. Si aucun profil n'est disponible, l'indexation est bloquée avec une erreur publique.

### 4. Visualiser les sorties du pipeline documentaire

L'UI affiche une fiche de sortie pour chaque étape terminée ou bloquée. Cette fiche sert à l'inspection utilisateur: elle ne transforme pas l'utilisateur en validateur métier, ne demande pas d'acceptation ou de refus et ne crée pas d'état supplémentaire dans SP, KA, EG, RA ou CV.

| Étape | Sorties visibles pour jugement utilisateur | Affichage minimal | Interdits |
|---|---|---|---|
| Enregistrement PDF | Empreinte stable, métadonnées retenues, statut source, indication d'immuabilité du PDF original. | Fiche `document_id`, titre, origine, date, type, langue, hash, horodatage, `document_status`, doublon éventuel. | Remplacer le titre ou l'origine par défaut depuis le nom de fichier; masquer un PDF illisible. |
| Diagnostic | Manifeste complet, nombre de pages attendu, nombre de pages diagnostiquées, diagnostic page par page. | Tableau par page: page, type observé, texte natif présent, image présente, OCR existant, rotation, lisibilité, signaux de tableaux ou formules, statut. | Résumer un diagnostic incomplet comme prêt; fusionner des pages absentes; masquer une page non diagnostiquée. |
| Routage documentaire | Route décidée ou absence de route pour chaque page, justification synthétique, motif de revue ou quarantaine. | Tableau par page: route, justification, politique de routage, statut `ROUTE_EXPLICIT`, `MANUAL_REVIEW` ou `SOURCE_QUARANTINED`. | Demander une approbation systématique de l'utilisateur; choisir une route par défaut; poursuivre silencieusement sur une route incertaine. |
| Conversion canonique | `TextAuthorityManifest`, QA pré-conversion, QA post-conversion, pages rejetées, version et hash canoniques. | Comparaison bornée original/canonique: page, autorité textuelle retenue, signaux QA, erreurs, `SourceLocator` échantillons, `canonical_version_id`, hash. | Exposer l'artefact complet si non public; fusionner plusieurs autorités textuelles; présenter une page rejetée comme publiée. |
| Indexation KA | Profil de projection, paramètres publics, nombre de chunks, exemples de chunks, SourceLocator associés, fraîcheur et statut `SEARCHABLE`. | Fiche `projection_id`, `projection_profile_id`, chunking, modèles publics, `chunk_count`, génération, fraîcheur, statut, aperçu borné de quelques chunks avec hashes. | Exposer collection Qdrant, points internes ou scores comme vérité; rendre sélectionnable une projection `STALE`, `FAILED` ou non `SEARCHABLE`. |
| Contrôle de recherche | Vérifier que la projection répond techniquement à une requête bornée produite par un contexte autorisé ou par un read-model d'inspection. | Requête ou contrôle affiché avec `search_trace_id`, filtres appliqués, résultats candidats, SourceLocator et avertissements. | Appeler KA librement depuis le navigateur; présenter une preuve candidate KA comme claim vérifié ou réponse RA; exposer une recherche libre comme vérité utilisateur finale. |
| Réponse conversationnelle | Question résolue, mode, justification, statut, réponse publiable, lacunes, contradictions, citations. | Carte de tour avec `conversation_id`, `turn_id`, `resolved_question`, `mode`, `support_status`, `answer_id` si présent. | Afficher l'historique comme preuve; publier un brouillon ou une sortie partielle LLM. |
| Citations | Ouverture de SourceLocator, page, fragment, version canonique et hash. | Panneau preuve: document, page, item, fragment borné, statut de résolution, lien local. | Remplacer une citation non ouvrable par un extrait voisin; masquer `ANSWER_CITATION_UNRESOLVABLE`. |

Le contrôle de recherche est une visualisation d'inspection KA bornée. Il ne remplace pas RA, ne vérifie pas les claims et ne produit pas de réponse conversationnelle. L'UI ne doit pas appeler directement `POST /v1/search` si le contrat KA le réserve aux contextes RA et EG; dans ce cas, elle lit un read-model de projection affichant des chunks échantillonnés, leurs SourceLocator et les traces de contrôle publiées.

### 5. Sélectionner les documents interrogeables

Un document devient sélectionnable pour la conversation seulement si:

- une version canonique est publiée ou acceptée;
- une projection KA existe;
- la projection est `SEARCHABLE`;
- aucun statut bloquant actif ne concerne la source, la version canonique ou la projection.

Un document chargé mais non indexé reste visible dans le corpus avec son état réel et ses sorties inspectables. L'UI ne le présente jamais comme utilisable par le chatbot.

### 6. Ouvrir une conversation

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

### 7. Poser une question

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

### 8. Vérifier les preuves

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
| Lire la sortie d'enregistrement. | SP. | métadonnées retenues, empreinte stable, statut source, doublon éventuel, horodatage. | métadonnées inventées par l'UI, chemin de stockage interne, hash recalculé côté navigateur. |
| Lire le diagnostic documentaire. | SP. | manifeste complet, nombre de pages, diagnostics page par page, signaux de lisibilité, tableaux, formules, rotation, erreurs. | diagnostic agrégé qui masque une page absente, route implicite, artefacts OCR internes non publiés. |
| Lire le routage documentaire. | SP. | route par page, justification, version de politique, pages en revue, quarantaine, motif public. | approbation utilisateur obligatoire pour route non ambiguë, route par défaut, détail de stockage interne. |
| Lire la sortie canonique. | SP. | `TextAuthorityManifest`, QA pré/post-conversion, pages rejetées, `canonical_version_id`, hash canonique, SourceLocator échantillons, aperçu borné original/canonique. | artefact complet non public, fusion silencieuse d'autorités textuelles, correction OCR silencieuse. |
| Lire une projection. | KA. | `projection_id`, `canonical_version_id`, `projection_status`, profil public, `chunk_count`, fraîcheur, exemples de chunks et SourceLocator. | `qdrant_collection`, identifiants de points, paramètres internes non publiés. |
| Lire un contrôle de recherche borné. | KA via read-model d'inspection ou contexte autorisé. | requête de contrôle, `search_trace_id`, résultats candidats, filtres appliqués, avertissements, SourceLocator. | appeler KA librement depuis le navigateur, présenter un résultat KA comme claim vérifié, exposer une recherche libre comme réponse finale. |
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
| UI-004 - Chat limité aux projections recherchables | Une source chargée mais non `SEARCHABLE` ne peut pas être sélectionnée comme corpus RA. | Given un PDF `REGISTERED`; When l'utilisateur prépare une question; Then le document reste non sélectionnable pour `selected_documents`. |
| UI-005 - Conversation append-only et statutée | Chaque message affiche question résolue, mode, justification et statut. | Given une conversation active; When l'utilisateur pose une question; Then le tour présenté contient `resolved_question`, `mode`, `mode_justification` et `support_status`. |
| UI-006 - Citations ouvrables | Une réponse supportée exige des citations résolubles. | Given RA retourne une citation; When l'utilisateur l'ouvre; Then l'UI affiche SourceLocator, page et version canonique. |
| UI-007 - Abstention visible | Une lacune ou donnée actuelle manquante n'est pas reformulée en réponse affirmative. | Given RA retourne `CURRENT_DATA_REQUIRED`; When la réponse est présentée; Then l'UI affiche l'abstention et la raison publique. |
| UI-008 - Payloads sensibles absents | L'UI ne rend pas publics prompt complet, brouillon, preuve complète, secret ou stockage interne. | Given une erreur publique survient; When le journal UI l'affiche; Then seuls code public, identifiants publics et horodatage sont visibles. |
| UI-009 - Sortie d'enregistrement inspectable | L'utilisateur voit l'identité documentaire retenue sans validation manuelle requise. | Given un PDF est enregistré; When la fiche document est ouverte; Then l'empreinte, les métadonnées retenues, le statut source et l'immuabilité sont affichés. |
| UI-010 - Diagnostic page par page inspectable | Le diagnostic ne se réduit pas à un statut global. | Given un diagnostic est terminé; When l'utilisateur ouvre les détails; Then le manifeste, le nombre de pages et les signaux page par page sont affichés. |
| UI-011 - Routage inspectable sans approbation systématique | Les routes et justifications sont visibles sans créer un workflow d'acceptation utilisateur. | Given le routage est explicite; When l'utilisateur inspecte le document; Then la route par page, la justification et la politique sont affichées sans bouton d'approbation obligatoire. |
| UI-012 - Conversion canonique inspectable | Les sorties canoniques critiques sont visibles avant usage RA. | Given une conversion est acceptée; When l'utilisateur ouvre la version canonique; Then QA pré/post, `TextAuthorityManifest`, pages rejetées, hash et aperçu borné original/canonique sont affichés. |
| UI-013 - Projection inspectable | Une projection `SEARCHABLE` expose assez d'éléments pour juger sa construction. | Given l'indexation est terminée; When l'utilisateur ouvre la projection; Then profil, `chunk_count`, fraîcheur, échantillons de chunks et SourceLocator sont affichés. |
| UI-014 - Contrôle de recherche non factuel | Le contrôle de recherche ne remplace pas RA et ne contourne pas les contextes autorisés. | Given une trace de contrôle KA est disponible; When les résultats s'affichent; Then l'UI les marque comme preuves candidates non vérifiées et conserve `search_trace_id`. |
| UI-015 - Frontière API orchestratrice obligatoire | Toute capacité UI passe par un contrat `orchestrator-api` câblé au cas d'usage réel; un contrat absent, non câblé ou indisponible laisse la fonction UI explicitement non opérationnelle sans mock, stub, fake ni fallback. | Given une action UI dépend d'un contrat applicatif; When ce contrat est absent, non câblé ou indisponible; Then l'UI affiche le blocage et n'exécute aucun comportement de substitution. |
| UI-016 - Contrats documentaires stricts | Les statuts SP publics sont partagés avec le client; un diagnostic exige le même `document_id`, un manifeste et des pages complètes, uniques et ordonnées, ainsi que des compteurs et nullabilités cohérents. | Given l'API retourne un diagnostic ou une conversion; When le client UI parse le DTO; Then toute divergence d'identité, page, compteur, statut ou nullabilité est refusée explicitement. |
| UI-017 - Navigation HTML accessible | Un POST UI réussi suit `POST-Redirect-GET`; une erreur reste une page française actionnable avec `role=alert`, lien de réessai et aucun JSON brut. | Given l'utilisateur ajoute ou diagnostique un PDF; When l'orchestrateur répond; Then le navigateur rejoint le corpus en succès ou affiche une erreur sémantique accessible. |
| UI-018 - Origine orchestratrice explicite | `uv run ui` vise l'adresse loopback configurée depuis l'hôte; le service Compose vise le DNS `orchestrator-api`; un contexte inconnu est refusé sans fallback. | Given l'UI démarre sur l'hôte ou dans Compose; When son client HTTP est construit; Then une seule origine validée est sélectionnée explicitement pour ce contexte. |

## Exclusions

- Pas de chat générique directement branché au LLM.
- Pas d'appel navigateur direct vers Spark, vLLM, Qdrant, PostgreSQL ou stockage documentaire interne.
- Pas de recherche libre KA présentée comme réponse finale hors flux RA/CV; seule une inspection de projection bornée peut afficher des preuves candidates explicitement non vérifiées.
- Pas de correction OCR ou édition documentaire silencieuse dans l'UI minimale.
- Pas de promesse financière, conseil d'investissement ou donnée de marché inventée.
- Pas de suppression ou purge administrative depuis l'UI minimale.
- Pas de publication publique externe; l'interface reste locale.
