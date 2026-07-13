# Runbook ingestion PDF V1 M-013

## Statut

- Identifiant : `M013-Runbook-PdfIngestion-1.1`.
- Contextes : UI locale, SP et plateforme.
- Sources : `docs/specs/m003_source_enregistree_diagnostiquee_routee.md`, `docs/specs/m013_fastapi_api_orchestratrice.md` et `docs/specs/ui.md`.
- ADR applicables : ADR-018, ADR-020, ADR-021, ADR-025 et ADR-028.
- Limite : la conversion canonique M-004 et l'indexation KA ne sont pas livrées par M13-FastAPI.

## Scénario BDD

- Given la stack locale est prête et le secret backend local est provisionné hors Git.
- When l'utilisateur ajoute un PDF par `/ui/corpus-pdf`, demande son diagnostic et ouvre l'original.
- Then l'UI enregistre le PDF réel via l'API, conserve l'identifiant après redirection, affiche les statuts et motifs persistés, puis restitue l'original bit à bit sans exposer son chemin interne.

## Préconditions

1. Créer `deploy/local-compose/secrets/postgres_password` selon le runbook d'exploitation.
2. Créer `deploy/local-compose/secrets/local_api_token` avec au moins 32 octets aléatoires. Ne jamais versionner, afficher ou copier cette valeur dans une commande, un rapport ou un navigateur.
3. Définir `OSTRADING_IMAGE_REVISION` sur le commit complet et `OSTRADING_POSTGRES_SCHEMA_VERSION` sur `009`.
4. Démarrer la stack Compose supportée puis attendre `/api/ready`.

L'UI et l'API montent le même secret en lecture seule. Le navigateur ne reçoit jamais le token : le serveur UI l'ajoute uniquement à l'appel backend.

## Ajouter un PDF

1. Ouvrir `/ui/corpus-pdf` depuis l'origine locale publiée par Caddy.
2. Choisir un fichier `application/pdf` de 50 Mio maximum.
3. Saisir explicitement le titre, un ou plusieurs auteurs, l'année de publication et l'édition. Le nom du fichier n'est jamais une métadonnée.
4. Envoyer le formulaire. Une réponse nominale produit une redirection `303` vers le corpus avec `document_id` et le marqueur de doublon.

Le transfert navigateur -> UI -> API et la copie API -> corpus utilisent des chunks bornés. Une taille excessive répond `413`; une origine absente ou divergente répond `403 UI_ORIGIN_FORBIDDEN`; une saturation de quatre transferts lents répond `503 UI_TRANSFER_CAPACITY_EXHAUSTED` au suivant.

## Quota et erreurs d'admission

| Statut | Code public | Action |
|---|---|---|
| `401` | `LOCAL_API_TOKEN_REQUIRED` | Vérifier le montage du secret entre UI et API; ne pas contourner par un appel direct. |
| `403` | `LOCAL_API_TOKEN_INVALID` ou `UI_ORIGIN_FORBIDDEN` | Vérifier que les deux services lisent le même secret ou que la requête provient de l'origine UI exacte. |
| `413` | `HTTP_REQUEST_TOO_LARGE` | Choisir un PDF inférieur ou égal à 50 Mio; ne pas augmenter silencieusement la limite. |
| `422` | `SOURCE_UNREADABLE` | Corriger ou remplacer le PDF; aucun parseur alternatif n'est appelé silencieusement. |
| `507` | `CORPUS_QUOTA_EXCEEDED` | Libérer ou augmenter le quota par une décision d'exploitation explicite; ne pas écrire hors corpus. |

Le quota agrégé est `paths.corpus_quota_bytes`. PostgreSQL sérialise les admissions concurrentes par la migration 009; un doublon de même fingerprint ne réserve pas deux fois son volume.

## Diagnostiquer et inspecter

- Depuis le corpus, demander le diagnostic du document. Le worker réel doit produire un statut persistant, un manifeste et des signaux page par page.
- `MANUAL_REVIEW` affiche `manual_review_reason`; `FAILED` affiche `failure_error_code`.
- Ouvrir le visualiseur en lecture seule ou télécharger l'original. Le contenu est streamé et vérifié par SHA-256 avant exposition; `original_storage_ref` ne devient jamais public.
- Plus de cent documents sont parcourus page par page. L'UI ne charge jamais tout le corpus ni les manifestes de chaque document pour construire la liste.

## Limite M-004 explicite

M13-FastAPI s'arrête au diagnostic documentaire. Aucun adaptateur Docling/OCRmyPDF de conversion canonique, aucune QA canonique et aucune publication durable `CanonicalSourcePublished` ne sont prouvés ici. Tant que M-004 n'est pas réellement raccordé, conversion et projection affichent `fonctionnalité non livrée` sans bouton ni conseil de retry. Un diagnostic `DIAGNOSED` ne constitue pas une preuve de conversion ou d'indexation.

## Compatibilité documentaire M-003/M-004

Les termes historiques `SourceDocumentId`, `SourceLocator`, quarantaine, route explicite et version canonique restent les marqueurs normatifs des spécifications M-003 et M-004. Leur présence dans ce runbook ne déclare pas le runtime M-004 livré par M13-FastAPI.

- Commande vérifiée : `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m003_specification.ps1`.
- Commande vérifiée : `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m004_specification.ps1`.
- Résultat attendu : les contrats de spécification restent cohérents et chaque statut public conserve son sens normatif.
- Erreur explicite : toute absence de route, quarantaine active, autorité textuelle manquante ou `SourceLocator` non résoluble bloque la publication canonique; M13-FastAPI ne contourne pas ce blocage.
- Preuve à conserver : sorties des validateurs, identifiant `SourceDocumentId` et, uniquement lorsqu'un futur runtime M-004 les produit réellement, `SourceLocator` et référence de version canonique.

## Commandes de preuve

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_review3_ui_security_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_review3_ui_security_live.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_ui_orchestrator_document_flow_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_review3_deployment_live.ps1
```

La dernière commande exporte le commit HEAD, construit les images schéma 009, exécute le parcours PDF réel, redémarre PostgreSQL et l'API, relit l'original puis supprime conteneurs, volumes et secrets temporaires.

## Garde-fous

- Aucun fallback silencieux, aucune route documentaire par défaut et aucune correction silencieuse d'un PDF.
- Aucun secret, PDF complet ou chemin interne dans les logs, OpenAPI, HTML ou redirections.
- Aucune suppression ordinaire ni purge depuis cet écran.
- Aucun statut M-004, KA ou conversationnel fabriqué depuis le seul diagnostic SP.
