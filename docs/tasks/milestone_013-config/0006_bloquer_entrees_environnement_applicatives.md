# T-006 - Bloquer les entrées d'environnement applicatives

## Milestone

- Nom: M13-config - Configuration applicative sans environnement.
- Source: ADR-016; `docs/tasks/README.md`; inventaire des usages `os.environ`, `GEMMA_*`, `DATABASE_URL`, `QDRANT_URL`, `LLM_GATEWAY_URL`.
- Objectif métier: empêcher la réintroduction d'une configuration applicative par environnement après la migration.

## Contexte DDD

- Domaine: gouvernance d'exécution et sécurité de plateforme.
- Bounded context: transverse, `platform.configuration`, `platform.security`.
- Objectif métier: transformer l'interdiction d'environnement en gate automatisée.
- Langage ubiquitaire: environnement pollué, clé homonyme, allowlist technique, scan statique, erreur explicite, absence de fallback.
- Invariants critiques: les anciens noms applicatifs ne sont jamais acceptés; les gardes de récursion des validateurs ne sont pas confondus avec la configuration applicative; toute exception est documentée.
- Garde-fous: pas de scan cosmétique; pas d'allowlist large; pas de suppression silencieuse d'une variable dangereuse.

## Blocages Ou Préconditions

- État GREEN/RED connu: T-003 à T-005 doivent avoir migré les chemins principaux.
- Présence des milestones amont dans master: M-000 à M-012 visibles dans `master`.
- Décisions manquantes: aucune.
- Risques: bloquer des variables de contrôle de tests non applicatives ou, inversement, laisser passer une lecture applicative réelle.

## Tâches

### T-006 - Bloquer les entrées d'environnement applicatives

- But métier: rendre impossible une régression où un processus recommence à lire `GEMMA_*`, `DATABASE_URL`, `QDRANT_URL`, `LLM_GATEWAY_URL`, `.env`, `env_file` ou `environment:` comme source applicative.
- Portée DDD: scan statique, validateurs de gouvernance, frontières réseau, exceptions documentées.
- Scénario BDD:
  - Given une modification introduit une lecture de variable d'environnement applicative.
  - When la gate M13-config inspecte le code, Compose, scripts et documentation d'exploitation.
  - Then la validation échoue avec `CONFIG_ENV_INPUT_REJECTED` ou un diagnostic ciblé avant tout démarrage.
- Tests d'acceptation à écrire: `uv run --locked gate`, couvrant `os.environ`, `getenv`, `process.env`, `.env`, `env_file`, `environment:` applicatif, variable homonyme dans le shell et exceptions techniques documentées.
- Tests unitaires à écrire: `uv run --locked gate`, couvrant scanner de fichiers, allowlist limitée, faux positifs sur texte historique, diagnostic de ligne, et refus de clé historique.
- Implémentation attendue: créer `uv run --locked gate` et un module de contrôle si nécessaire; enrôler la validation dans `uv run --locked gate` et `uv run --locked gate`; maintenir une allowlist explicite pour les variables de contrôle des tests uv run --locked gate
- Invariants et garde-fous: aucun fallback vers environnement; aucune variable dangereuse ignorée; les exceptions sont nommées, justifiées et testées.
- Dépendances: T-003 à T-005; `uv run --locked gate`; `uv run --locked gate`; `app/platform/configuration`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(governance): couvrir rejet environnement applicatif`.
- Commit GREEN: `feat(governance): bloquer entrees environnement applicatives`.
