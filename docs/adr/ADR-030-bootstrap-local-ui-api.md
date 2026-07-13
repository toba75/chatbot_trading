# ADR-030 - Bootstrap local de l’UI via l’API réelle

**Statut :** Acceptée
**Date :** 2026-07-13
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** Demande utilisateur du 2026-07-13 ; `docs/specs/ui.md` ; ADR-018 ; ADR-026 ; ADR-028

## Contexte

La commande `uv run ui` servait uniquement le serveur de présentation. L’API orchestratrice, PostgreSQL et le secret local de mutation restaient absents, ce qui rendait l’interface explicitement non opérationnelle dès l’ouverture ou à l’enregistrement d’un PDF.

ADR-018 interdit à l’UI de contourner l’API et ADR-028 impose un secret local partagé entre l’UI et l’API. ADR-026 concerne le déploiement d’exploitation Compose depuis un commit complet ; elle ne décrit pas un bootstrap de développement sur l’hôte.

## Décision

- `uv run ui` **DOIT** démarrer un runtime local de développement comprenant PostgreSQL et `orchestrator-api` réels avant de servir l’UI sur le port publié.
- Le runtime **DOIT** construire une configuration hôte temporaire qui pointe l’API vers PostgreSQL local ; l’UI continue d’appeler exclusivement `orchestrator-api` conformément à ADR-018.
- Le runtime **DOIT** limiter l’UI, l’API et le `llm-gateway` démarrés sur l’hôte à `127.0.0.1` ; aucun service interne ne devient accessible sur le réseau local.
- Le bootstrap **DOIT** provisionner explicitement les secrets locaux absents avec une entropie suffisante et annoncer leur création sans afficher leur valeur.
- Le runtime **DOIT** refuser explicitement un port occupé, un conteneur PostgreSQL non géré, un secret illisible ou une dépendance Docker indisponible ; il **NE DOIT PAS** réutiliser silencieusement une dépendance inconnue.
- Le runtime **DOIT** conserver les données documentaires locales et nettoyer les processus ainsi que la configuration temporaire à l’arrêt. Il **NE DOIT PAS** se présenter comme le déploiement Compose d’exploitation d’ADR-026.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Conserver `uv run ui` comme serveur de présentation seul | Rejetée | L’interface n’est pas utilisable sans connaissance préalable de plusieurs services et secrets. |
| Faire lire directement `data/corpus` par l’UI | Rejetée | Contourne ADR-018 et fabrique un état différent du read-model public. |
| Bootstrap hôte explicite des dépendances réelles | Retenue | Rend le parcours UI utilisable en une commande tout en conservant l’API comme frontière métier unique. |
| Remplacer le déploiement Compose d’exploitation par ce bootstrap | Rejetée | Le bootstrap local ne fournit ni l’archive Git ni les contrôles de déploiement d’ADR-026. |

## Conséquences

### Positives

- L’ajout et la consultation de PDF disponibles dans M-013 deviennent utilisables après `uv run ui`.
- Les secrets et dépendances locales sont préparés de manière traçable, sans les exposer.
- L’UI conserve le trajet HTTP public réel vers `orchestrator-api`.

### Négatives ou coûts

- Docker est une précondition locale explicite.
- Le premier démarrage crée les secrets locaux et le stockage PostgreSQL de développement.

### Risques et contrôles

- Risque : connecter l’UI à une API ou une base inconnue. Contrôle : ports, nom et marqueur de propriété vérifiés explicitement.
- Risque : contourner la frontière UI/API. Contrôle : la configuration temporaire ne crée aucun adaptateur métier UI et les tests vérifient le passage par `orchestrator-api`.
- Risque : confondre développement et exploitation. Contrôle : la documentation distingue explicitement ce bootstrap d’ADR-026.

## Impact d’implémentation

- Modules concernés : `app/platform/ui_command.py` et bootstrap local de plateforme.
- Configuration concernée : secrets locaux ignorés par Git et configuration runtime temporaire.
- Tests attendus : configuration runtime locale, orchestration de `uv run ui` et parcours PDF réel.
- Milestones concernées : M-013 UI et M13-FastAPI.

## Liens de traçabilité

- Spécification : `docs/specs/ui.md`.
- Plan d’implémentation : demande utilisateur du 2026-07-13.
- Tests d’acceptation : `gate_tests/ported/tests/m013/validate_uv_run_ui_local_stack_acceptance.py`.
- Commits : RED `8c37fd451` et `43f29a633` ; GREEN lié à l’acceptation de cette ADR.

## Notes

Cette décision ne remplace pas ADR-018, ADR-026 ni ADR-028.
