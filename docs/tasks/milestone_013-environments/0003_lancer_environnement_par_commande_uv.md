# T-003 - Lancer l'environnement choisi par une commande UV

## Milestone

- Nom: M13-environments - Environnements explicites et données étanches.
- Source: contrat T-002; demande de commandes `uv run development`, `uv run test`, `uv run production`.
- Objectif métier: masquer le chemin de configuration à l'opérateur sans rendre la sélection implicite.

## Contexte DDD

- Domaine: plateforme d'exécution.
- Bounded context: `platform.configuration` et composition de processus.
- Objectif métier: fournir trois intentions de lancement simples, stables et non configurables.
- Langage ubiquitaire: commande d'environnement, mapping fermé, supervision, readiness, arrêt terminal.
- Invariants critiques: une commande correspond à un seul profil et un seul fichier; l'opérateur ne fournit plus `--config`; tous les processus enfants reçoivent la même identité.
- Garde-fous: pas de commande générique avec profil par défaut; pas de recherche automatique de fichier; pas de fallback sur `config/application.yaml`.

## Blocages Ou Préconditions

- État GREEN/RED connu: T-001 et T-002 GREEN.
- Présence des milestones amont dans master: M-000 à M-012 visibles.
- Décisions manquantes: aucune après ADR-045.
- Risques: wrapper ergonomique qui masque une divergence entre API, UI, gateway et workers.

## Tâches

### T-003 - Lancer l'environnement choisi par une commande UV

- But métier: permettre un lancement mémorisable tout en conservant une sélection déterministe et auditée.
- Portée DDD: entrées `[project.scripts]`, lanceur commun, mapping vers `config/environments/{profile}.yaml`, cycle de vie de la pile.
- Scénario BDD:
  - Given les trois fichiers complets existent.
  - When l'opérateur exécute l'une des commandes UV dédiées.
  - Then la pile complète démarre avec le fichier codé pour cette commande, publie son identité et échoue si un composant attendu n'atteint pas la readiness du même profil.
- Tests d'acceptation à écrire: invocation réelle des trois entrypoints; chemin exact attendu; absence d'argument `--config` public; erreur sur fichier absent; supervision API/UI/gateway/workers; propagation du code terminal.
- Tests unitaires à écrire: mapping fermé commande-fichier, construction de commandes enfants, refus de surcharge, refus de profil non répertorié, arrêt ordonné après échec.
- Implémentation attendue: ajouter les trois scripts UV et un lanceur commun strict; conserver `--config` uniquement comme détail interne des processus; fournir des états `starting`, `ready`, `failed`, `stopped` fondés sur les contrats réels.
- Invariants et garde-fous: aucune variable d'environnement applicative; aucun profil par défaut; aucun composant marqué prêt sur simple existence d'un processus; aucun service alternatif lancé en cas d'échec.
- Dépendances: T-002; `pyproject.toml`; points d'entrée API, UI, gateway et workers existants.
- Commandes de validation: tests d'acceptation et unitaires du lanceur; `uv run --locked gate --scope m013_config`; `uv run --locked gate`.
- Commit RED: `test(platform): couvrir commandes uv des environnements`.
- Commit GREEN: `feat(platform): lancer les environnements par commandes uv`.
