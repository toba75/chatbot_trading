# T-004 - Exposer la conversion et sa progression publique dans l'UI

## Milestone

- Nom : M04-conversion - Conversion canonique réellement exécutable.
- Source : ADR-018, ADR-019, ADR-024, ADR-031 et SP-016 de `docs/specs/m004_version_canonique_publiee.md`.
- Objectif métier : proposer `Convertir` seulement lorsqu'un document routé possède toute sa chaîne réelle d'exécution.

## Contexte DDD

- Domaine : traitement des sources documentaires.
- Bounded context : SP, avec présentation par platform.
- Objectif métier : accepter une demande de conversion idempotente, persister sa progression, la relayer au worker et rendre son issue publique.
- Langage ubiquitaire : `POST /v1/documents/{id}/convert`, `CONVERT_DOCUMENT`, conversion en file, conversion en cours, conversion réussie, conversion échouée.
- Invariants critiques : l'UI n'invente aucun compteur ; l'action demandée demeure inspectable ; le bouton ne réapparaît pas après acceptation.
- Garde-fous : API, outbox, relais, worker et lecture publique sont obligatoires avant le bouton ; les erreurs ne divulguent pas les identifiants internes.

## Blocages Ou Prérequis

- État GREEN/RED connu : T-003 est GREEN.
- Présence des milestones amont dans master : contrats FastAPI et sécurité locale M13-FastAPI sont présents.
- Décisions manquantes : aucune ; ADR-031 gouverne la progression générique.
- Risques : masquer le bouton sans progression publique recréerait l'incident du diagnostic.

## Tâches

### T-004 - Exposer la conversion et sa progression publique dans l'UI

- But métier : rendre la conversion utilisable et observable par l'utilisateur.
- Portée DDD : commande SP, outbox, worker, contrats FastAPI, client UI et rendu HTML.
- Scénario BDD :
  - Given un document routé convertissable et le worker supervisé par `uv run ui`.
  - When l'utilisateur clique sur `Convertir` dans la colonne Conversion.
  - Then l'UI affiche la phase persistée, les pages réalisées sur le total, puis la version canonique ou l'erreur terminale réelle.
- Tests d'acceptation à écrire : parcours UI → API → outbox → relais → worker → lecture publique, avec phase en cours observée et issue terminale.
- Tests unitaires à écrire : bouton disponible seulement pour `ROUTE_PLANNED` sans conversion, validation Pydantic du contrat `CONVERT`, redirection UI et rafraîchissement des phases non terminales.
- Implémentation attendue : étendre les commandes FastAPI et UI, généraliser la progression publique, relayer `CONVERT_DOCUMENT` et superviser son worker via `uv run ui`.
- Invariants et garde-fous : aucun mock, aucune lecture de table ou de log par l'UI, aucun `Gate GREEN` partiel.
- Dépendances : T-003.
- Commandes de validation : tests ciblés M04-conversion ; `uv run --locked gate`; parcours local `uv run ui`.
- Commit RED : `test(ui): couvrir action conversion réelle ADR-031`.
- Commit GREEN : `feat(ui): exécuter conversion et progression publique`.
