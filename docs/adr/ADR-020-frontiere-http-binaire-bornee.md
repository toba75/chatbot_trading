# ADR-020 - Frontière HTTP binaire bornée

**Statut :** Acceptée
**Date :** 2026-07-12
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** Findings de revue M13-FastAPI; T-006; T-008; T-011; ADR-019

## Contexte

ADR-019 établit FastAPI et Uvicorn comme adaptateurs de la frontière publique `orchestrator-api`. Les routes documentaires acceptent des PDF multipart et restituent les originaux immuables. Un contrôle limité à `UploadFile.read()` intervient trop tard : le parseur multipart peut déjà avoir consommé ou spoulé un transfert sans `Content-Length`. Une restitution construite avec `Path.read_bytes()` charge par ailleurs l'original complet en mémoire et transforme le streaming HTTP en chunk unique.

La stack locale conserve un système de fichiers racine en lecture seule. Le spool multipart nécessite donc un espace temporaire explicitement borné. La défense doit couvrir la frontière edge, l'ASGI et les invariants métier sans fallback silencieux.

## Scénario BDD

- Given un client transmet un PDF ou un original doit être restitué.
- When le corps HTTP franchit Caddy puis l'ASGI, ou que l'original vérifié est lu.
- Then les octets consommés, spoulés et émis restent bornés, les métadonnées excessives sont refusées explicitement et le hash de l'original est vérifié avant toute réponse 200.

## Décision

- Caddy **DOIT** refuser tout corps `/api/*` supérieur à 54 Mo avant le proxy vers `orchestrator-api`.
- L'application ASGI **DOIT** appliquer la même limite agrégée, avec ou sans `Content-Length`, avant de déléguer au parseur multipart.
- Le buffer ASGI **DOIT** utiliser un spool mémoire court puis `/tmp`; le service Compose **DOIT** monter `/tmp` en `tmpfs` de 128 Mio avec `read_only: true` conservé afin de couvrir simultanément le spool agrégé et celui du parseur multipart.
- La route documentaire **DOIT** conserver une limite PDF métier de 50 Mio et refuser explicitement les titres de plus de 512 caractères, plus de 16 auteurs, un auteur de plus de 256 caractères, une édition de plus de 64 caractères ou une année hors de l'intervalle 1 à 9999.
- La restitution d'un original **DOIT** vérifier son hash par chunks bornés avant de publier un statut 200, puis émettre le même fichier en chunks d'au plus 64 Kio avec fermeture garantie.
- Les opérations synchrones de fichier, PostgreSQL et inspection PDF appelées depuis des routes asynchrones **DOIVENT** être exécutées dans le threadpool borné du runtime ASGI ou par une route synchrone.
- L'image applicative **DOIT** séparer la résolution des dépendances dans un builder du runtime non privilégié. Le runtime **NE DOIT PAS** installer `uv` ni résoudre des dépendances.
- Une limite absente, invalide ou dépassée **NE DOIT PAS** déclencher de fallback vers un autre parseur, routeur ou stockage.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Contrôle après `request.form()` seulement | Rejetée | Le transfert peut déjà être consommé et spoulé sans borne agrégée. |
| Limite Caddy seulement | Rejetée | L'ASGI resterait vulnérable lors d'un accès interne ou d'une mauvaise configuration edge. |
| Charger le PDF complet avant restitution | Rejetée | La mémoire croît avec la taille du document et le streaming devient nominal. |
| Défense Caddy + ASGI, spool tmpfs borné et restitution par chunks | Retenue | Les limites restent explicites à chaque frontière et la mémoire est bornée. |

## Conséquences

### Positives

- Les transferts chunked et les longueurs annoncées sont bornés avant le parsing métier.
- Le système de fichiers racine reste en lecture seule avec un seul espace temporaire dimensionné.
- Plusieurs restitutions peuvent progresser sans charger chaque PDF complet en mémoire.
- La chaîne de dépendances et le runtime Docker sont séparés.

### Négatives ou coûts

- Un upload autorisé est lu une première fois par le middleware agrégé avant le parsing multipart.
- La vérification avant réponse puis la restitution lisent deux fois l'original afin de conserver le statut d'erreur 409 avant les en-têtes 200.
- Le `tmpfs` réserve une enveloppe maximale explicite de 128 Mio par conteneur pour le double spool borné.

### Risques et contrôles

- Risque : divergence entre limites Caddy et ASGI. Contrôle : mêmes marqueurs vérifiés par la gate de déploiement.
- Risque : substitution entre vérification et émission. Contrôle : le descripteur vérifié reste ouvert, est repositionné puis fermé par le générateur de chunks.
- Risque : blocage event-loop. Contrôle : délégation des opérations synchrones au threadpool FastAPI/Starlette et tests de concurrence bornée.

## Impact d'implémentation

- Modules concernés : `app/platform/orchestrator_asgi.py`, adaptateurs HTTP et stockage SP.
- Configuration concernée : Caddy, Compose et Dockerfile de la stack locale.
- Tests attendus : commandes documentaires, streaming original, déploiement, preuve live supérieure à 1 Mio et audit de dépendances.
- Milestones concernées : M13-FastAPI, correctif de revue T-006/T-008/T-011.

## Liens de traçabilité

- Spécification : `docs/specs/m013_fastapi_api_orchestratrice.md`.
- Plan d'implémentation : `docs/tasks/milestone_013-fastapi/0006_enregistrer_pdf_lancer_diagnostic.md`; `0008_recuperer_pdf_original_controle.md`; `0011_deployer_auditer_api_orchestratrice.md`.
- Tests d'acceptation : `tests/m013_fastapi/validate_document_commands_http_acceptance.ps1`; `validate_original_pdf_retrieval_acceptance.ps1`; `validate_document_http_live_acceptance.ps1`.
- Commits : RED `ae943a04c` et `d4b64cf26`; GREEN `89acbdd70`, `feat(api): borner frontiere http et streaming original ADR-020`.

## Notes

ADR-019 reste acceptée et inchangée : ADR-020 précise ses garde-fous binaires et opérationnels sans déplacer la propriété métier de SP.
