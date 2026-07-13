# ADR-028 - Admission documentaire locale authentifiée et bornée

**Statut :** Acceptée
**Date :** 2026-07-13
**Décideurs :** Équipe OSTrading
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** Revue UI, sécurité et performance M13-FastAPI, passe 3

## Contexte

ADR-018 impose que l'UI consomme exclusivement les contrats publics de `orchestrator-api`, ADR-020 borne la frontière binaire et ADR-021 impose les migrations PostgreSQL avant readiness. Le premier écran UI permet désormais d'enregistrer un PDF, de demander son diagnostic et de relire son original. Ces opérations cumulent trois risques structurants : une mutation directe de l'API sans identité locale, la matérialisation de fichiers pouvant atteindre 50 Mio dans plusieurs processus, et des admissions concurrentes capables de dépasser la capacité durable du corpus.

Le bind loopback ne constitue pas une authentification : un autre processus local ou une page web malveillante peut joindre un port local. Un contrôle d'origine navigateur ne protège pas non plus un appel direct à l'API. Enfin, une limite par requête ne suffit pas à limiter le volume agrégé du corpus, notamment lorsque plusieurs uploads sont admis simultanément.

## Décision

- Toute mutation documentaire persistante exposée par `orchestrator-api` **DOIT** exiger un token Bearer lu depuis un fichier secret hors Git d'au moins 32 octets. `POST /v1/documents` et `POST /v1/documents/{document_id}/diagnose` sont concernés.
- L'UI **DOIT** injecter ce token uniquement dans son appel backend. Le token **NE DOIT PAS** apparaître dans l'OpenAPI, le HTML, les journaux, une redirection ou une erreur publique.
- L'absence d'en-tête d'autorisation **DOIT** produire `401 LOCAL_API_TOKEN_REQUIRED`; une valeur incorrecte **DOIT** produire `403 LOCAL_API_TOKEN_INVALID`. Les lectures documentaires, `/health` et `/ready` restent non authentifiées par ce mécanisme local.
- Toute mutation reçue par le serveur UI **DOIT** présenter un en-tête `Origin` dont l'autorité est identique à `Host`. Un `Sec-Fetch-Site` présent **DOIT** valoir `same-origin`. Un refus **DOIT** précéder la lecture du corps et répondre `403 UI_ORIGIN_FORBIDDEN`.
- Le PDF **DOIT** être transféré par chunks bornés de l'UI vers l'API, mis en attente dans un fichier temporaire borné, puis copié vers le corpus sans matérialisation intégrale en mémoire. La restitution API vers UI puis navigateur **DOIT** conserver le streaming et la backpressure.
- La taille PDF reste limitée à 50 Mio et un dépassement **DOIT** répondre `413`. Les métadonnées bibliographiques **DOIVENT** avoir des cardinalités et longueurs maximales explicites; une valeur invalide **DOIT** répondre `400 HTTP_REQUEST_INVALID` avant appel métier.
- Le serveur UI **DOIT** limiter le nombre de requêtes concurrentes et borner les délais socket et backend. Une saturation **DOIT** répondre `503 UI_TRANSFER_CAPACITY_EXHAUSTED`; elle **NE DOIT PAS** créer une file ou des threads non bornés.
- Le quota agrégé du corpus **DOIT** être configuré explicitement. Chaque nouvel original **DOIT** réserver son volume dans PostgreSQL sous verrou de ligne et transaction avant écriture durable. Deux réservations concurrentes **NE DOIVENT PAS** dépasser le quota; le refus public est `507 CORPUS_QUOTA_EXCEEDED`.
- Une réservation existante du même fingerprint **DOIT** rendre le doublon idempotent. Une écriture de fichier échouée **DOIT** libérer la réservation qu'elle vient de créer.
- La liste du corpus **DOIT** lire une projection SQL légère, page par page, sans hydrater manifestes, diagnostics de pages ou routes et sans fan-out `1+N`.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Considérer le loopback comme identité suffisante | Rejetée | Le loopback est une frontière réseau, pas une identité de processus ni d'utilisateur. |
| Contrôler seulement `Origin` côté UI | Rejetée | Un client direct de l'API ne porte pas nécessairement un contexte navigateur. |
| Token backend hors Git et contrôle same-origin navigateur | Retenue | Les deux canaux d'attaque sont contrôlés séparément sans session ni base d'utilisateurs V1. |
| Charger les PDF complets en mémoire | Rejetée | Deux copies de 50 Mio par transfert rendent la mémoire et la concurrence non bornées. |
| Streaming chunké avec capacité et timeouts bornés | Retenue | La mémoire reste indépendante de la taille du PDF et la saturation devient explicite. |
| Calculer le quota à partir du seul système de fichiers | Rejetée | Le contrôle concurrent ne serait pas atomique entre processus. |
| Réserver le quota sous verrou PostgreSQL | Retenue | La décision d'admission est durable, transactionnelle et sérialisée. |

## Conséquences

### Positives

- Une page web tierce et un client local non autorisé ne peuvent plus muter silencieusement le corpus.
- Les secrets restent hors contrats publics et hors observabilité.
- La mémoire des processus reste bornée pendant l'upload et le téléchargement.
- La saturation UI, la taille excessive et le quota agrégé possèdent des statuts et codes publics distincts.
- La pagination du corpus garde un coût SQL et mémoire borné au nombre d'éléments visibles.

### Négatives ou coûts

- Le déploiement local exige un secret supplémentaire partagé uniquement entre UI et API.
- Le chemin d'upload effectue plusieurs lectures séquentielles du fichier temporaire pour inspection, hash et copie durable.
- La migration 009 ajoute un compteur et un registre de réservations propriétaires de SP.
- Quatre transferts lents peuvent saturer l'UI jusqu'aux timeouts socket ou backend de 30 secondes; le cinquième reçoit volontairement `503`.

### Risques et contrôles

- Risque : fuite du token par log ou redirection. Contrôle : tests avec sentinelle et inspection OpenAPI, HTML et logs Compose.
- Risque : course quota. Contrôle : `SELECT ... FOR UPDATE`, deux connexions concurrentes et assertion d'un seul succès.
- Risque : upload lent bloquant. Contrôle : sémaphore, timeout socket/backend et test 4+1 avec récupération de capacité.
- Risque : fichier temporaire ou réservation orpheline. Contrôle : suppression en `finally` et compensation de la réservation créée lorsque la copie échoue.
- Risque : régression des lectures. Contrôle : santé et GET restent accessibles sans secret, pagination à une requête et preuve Compose réelle.

## Impact d'implémentation

- Modules concernés : `app/platform/local_authorization.py`, `app/platform/orchestrator_asgi.py`, `app/platform/local_runtime.py`, `app/platform/ui_document_api.py`, `app/platform/ui_corpus.py`, `app/source_processing/adapters/http.py`, `app/source_processing/adapters/postgres_document_persistence.py`, `app/source_processing/application/document_queries.py`.
- Configuration concernée : `paths.corpus_quota_bytes`, `security.secrets.local_api_token_path`, secret Compose `local_api_token`.
- Tests attendus : autorisation directe 401/403, CSRF, upload/téléchargement streaming, 413, transferts lents concurrents, pagination supérieure à cent documents, course quota PostgreSQL, migration 009 et Compose exporté depuis HEAD.
- Milestones concernées : M13-FastAPI et tranche UI minimale de M-013.

## Liens de traçabilité

- Spécifications : `docs/specs/m013_fastapi_api_orchestratrice.md`; `docs/specs/ui.md`; ADR-018; ADR-020; ADR-021.
- Plan d'implémentation : `docs/tasks/milestone_013/0024_creer_premier_ecran_corpus_pdf_ui.md`; correctifs de revue M13-FastAPI.
- Tests d'acceptation : `tests/m013_fastapi/validate_review3_ui_security_acceptance.ps1`; `tests/m013_fastapi/validate_review3_ui_security_live.ps1`; `tests/m013_fastapi/validate_ui_orchestrator_document_flow_acceptance.ps1`; `tests/m013_fastapi/validate_review3_deployment_live.ps1`.
- Commits : RED `9a487beb7`; GREEN `6d6d58c89`.

## Notes

ADR-028 complète ADR-018, ADR-020 et ADR-021 sans les remplacer. Elle ne crée ni compte utilisateur, ni cookie de session, ni service d'identité. Une exposition autre que locale exigerait une nouvelle décision d'authentification et de terminaison TLS.
