# Journal M13-environments

## Planification

- Sous-milestone: `M13-environments`, matérialisé dans `docs/tasks/milestone_013-environments`.
- Source principale: demande utilisateur du 2026-07-21 et section `M13-environments` du plan d'implémentation.
- Règle de gouvernance: ce dossier est un sous-milestone de M-013; il requiert M-000 à M-012 dans `master`, ne requiert pas la clôture de M-013 et ne clôture pas M-013 pour les milestones aval.
- Dépendance fonctionnelle: M13-config, dont le chargeur strict, les points d'entrée `--config` et l'interdiction des variables d'environnement sont présents sur la branche.
- Décision à créer pendant T-002: ADR-045, remplaçant explicitement ADR-016 pour la règle du chemin unique, sans modifier ADR-016 silencieusement.

## Intention

Fournir trois commandes opérateur simples, `uv run development`, `uv run test` et `uv run production`. Chacune sélectionne un fichier complet et immuable, supervise la chaîne réelle et utilise exclusivement ses bases, volumes, fichiers, artefacts, queues, outbox et secrets. Les workers portent la même identité que l'API et refusent tout travail d'un autre environnement avant claim ou effet métier.

## Tâches créées

- T-001: vérifier la précondition GREEN.
- T-002: décider le contrat des environnements explicites.
- T-003: lancer l'environnement choisi par une commande UV.
- T-004: vérifier l'identité des stockages avant usage.
- T-005: isoler toutes les ressources mutables.
- T-006: orchestrer trois piles et secrets distincts.
- T-007: lier workers et jobs à l'environnement courant.
- T-008: borner les opérations administratives à un environnement.
- T-009: prouver le parcours réel en development.
- T-010: prouver le parcours réel en test.
- T-011: prouver le parcours réel en production.
- T-012: relier environnements, runbooks et gates.

## Limite de cette planification

Cette étape crée uniquement le plan et les fichiers de tâches. Elle ne crée pas ADR-045, ne publie pas la spécification détaillée, ne modifie ni code, ni test, ni configuration, ni déploiement, et ne démarre ou n'arrête aucun service.

## T-001 - Précondition documentaire

Date d'exécution: 2026-07-21.

Scénario contrôlé:

- Given le sous-milestone M13-environments est demandé.
- When les prérequis Git et la gate documentaire sont vérifiés.
- Then M-000 à M-012 sont présents dans `master`, la branche descend de `master` et la gouvernance est GREEN avant planification.

Références Git observées avant le commit de planification:

- Branche courante: `codex/m13-environments`.
- `HEAD`: `781469359`.
- `master`: `9edeab957`.
- `origin/master`: `35fb5a4f8`.
- `master` et `origin/master` sont ancêtres de `HEAD`.

Présence dans `master`:

- M-000: 7 fichiers; M-001: 12; M-002: 12; M-003: 10; M-004: 11; M-005: 11.
- M-006: 11 fichiers; M-007: 11; M-008: 12; M-009: 12; M-010: 12; M-011: 13; M-012: 13.

Commandes exécutées:

- `git fetch origin --prune` - GREEN.
- contrôle `git cat-file -e master:docs/tasks/milestone_NNN/journal.md` pour M-000 à M-012 - GREEN.
- `uv run --locked gate --scope governance` - GREEN; 25 nœuds exécutés, aucune exécution manquante, inattendue ou dupliquée.

État connu de l'implémentation avant M13-environments:

- `pyproject.toml` ne publie pas encore `development`, `test` ou `production`.
- `config/application.schema.json` et le chargeur ne portent pas encore `environment` ou `deployment_id`.
- Compose utilise encore un unique jeu de volumes et un unique fichier monté pour tous les services.
- Les workers consomment `configuration_hash`, mais aucun contrat d'environnement ne bloque encore un job cross-environment.

Statut de T-001 pour la planification: GREEN documentaire. La baseline complète et les prérequis live devront être rejoués au début de l'implémentation, sans mock ni fallback.

## Validation de la planification

- `uv run --locked gate --scope governance` - GREEN après création des tâches; 25 nœuds, aucune exécution manquante, inattendue ou dupliquée.
- `uv run --locked gate --scope m013_config` - GREEN; 36 nœuds couvrant les préconditions M-001 à M-012 et les validations du chargeur, de la spécification, de Compose, des runbooks, du gateway et de la traçabilité M13-config.
- `git diff --check` - GREEN; avertissement de normalisation LF vers CRLF uniquement, sans erreur d'espacement.

Périmètre contrôlé: un fichier de plan, douze fichiers de tâches et ce journal. Aucun autre artefact n'est modifié.
