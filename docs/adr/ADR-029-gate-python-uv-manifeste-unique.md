# ADR-029 - Gate Python uv à manifeste unique

**Statut :** Acceptée
**Date :** 2026-07-13
**Décideurs :** Propriétaire du projet
**Remplace :** ADR-010 ; obligations de wrappers PowerShell d’ADR-011 et ADR-012
**Remplacée par :** Aucune
**Source :** `docs/specs/m013_gate_python.md`, `docs/tasks/milestone_013-gate-python/`

## Contexte

La gate PowerShell actuelle orchestre 37 validations et 309 tests déclarés. Les préconditions M-003 à M-013 rappellent la gate et utilisent des variables d’environnement de récursion. L’exécution complète réexécute donc plusieurs nœuds et crée un processus PowerShell par commande. Elle ne fournit ni graphe de dépendances explicite ni preuve que chaque test a été exécuté une seule fois.

L’inventaire du 2026-07-13 montre 61 scripts sous `scripts/`, 374 tests sous `tests/` et 435 fichiers `.ps1` suivis. Ces nombres diffèrent respectivement de +3, +45 et +48 du diagnostic initial. Le nombre de tests déclarés reste 309 ; le nombre de validations déclarées est 37, non 36.

## Décision

À la bascule atomique, le dépôt DOIT exposer une seule commande canonique : `uv run gate`. La même gate en environnement verrouillé DOIT être `uv run --locked gate`.

Le paquet technique `ost_gate`, distinct des bounded contexts métier, DOIT charger le seul manifeste racine `gate.toml`, construire un graphe orienté acyclique et exécuter chaque nœud exactement une fois par run. Le manifeste DOIT refuser un identifiant ou chemin dupliqué, un chemin hors dépôt, un fichier absent, une suite vide et toute dépendance cyclique.

La gate canonique DOIT :

- exécuter les validations, tests et pipeline produit réel M-013 sans mock, stub ni chemin synthétique ;
- retourner RED lorsque le service obligatoire du pipeline réel est absent ;
- interdire les tests ignorés, xfail et les éléments non collectés ;
- propager le code d’échec du test ou validateur fautif ;
- appliquer un timeout explicite par nœud ;
- produire un rapport JSON comprenant l’identifiant, le scope, la phase, le statut, la durée et le nombre d’exécutions ;
- utiliser la parallélisation seulement pour les groupes explicitement isolés et conserver les groupes Git, processus, sauvegarde/restauration, HTTP et pipeline réel en série.

`uv run gate --scope <milestone>` et `uv run gate --offline` sont des exécutions partielles : ils ne DOIVENT jamais afficher `Gate GREEN`. `uv run gate --list` DOIT lister le plan déterministe sans l’exécuter.

Les préconditions deviennent des nœuds Git ciblés (branche, ancêtre, artefacts, spécifications et preuves). Elles NE DOIVENT PAS rappeler la gate complète et les variables `OST_M*_PRECONDITION_ACCEPTANCE_RUNNING` sont supprimées.

Pendant la migration, ADR-010 reste l’autorité officielle et cette ADR reste proposée. La candidate Python NE DOIT PAS appeler PowerShell. La bascule finale est atomique : cette ADR devient acceptée, ADR-010 devient remplacée, les obligations de wrappers PowerShell d’ADR-011 et ADR-012 sont explicitement remplacées, les documents normatifs et skills sont mis à jour, puis tous les `.ps1` sont supprimés. Les anciennes ADR et journaux conservent leurs mentions historiques, couvertes par une allowlist documentaire stricte ; elles ne présentent plus ces commandes comme actives.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Gate Python uv, manifeste unique et DAG | Retenue | Évite la récursion, garantit l’unicité et conserve une preuve structurée. |
| Conserver des wrappers PowerShell autour de Python | Rejetée | Conserverait les processus PowerShell et deux autorités de commande. |
| Ajouter une candidate Python à la gate historique | Rejetée | Doublerait le coût et ne démontrerait pas une exécution unique. |

## Conséquences

### Positives

- Une seule autorité de validation et un rapport exploitable par nœud.
- Les tests isolés peuvent être parallélisés sans faire chevaucher les ressources partagées.
- Les opérations de sauvegarde, restauration et reconstruction sont accessibles via des commandes uv versionnées.

### Négatives ou coûts

- La parité explicite de chaque ancien test et validateur doit être maintenue pendant la migration.
- Le pipeline réel M-013 rend la gate dépendante de services réellement disponibles, volontairement sans fallback.

### Risques et contrôles

- Risque : nœud oublié ou rejoué. Contrôle : validation du manifeste, plan DAG et rapport d’exécution unique.
- Risque : GREEN partiel présenté comme canonique. Contrôle : statuts `SCOPE GREEN` et `PARTIAL GREEN` distincts.
- Risque : documentation historique prise pour une commande active. Contrôle : allowlist versionnée et validateur dédié.

## Impact d’implémentation

- Modules concernés : `ost_gate/`, `gate.toml`, `gate_tests/`, `scripts/*.py`.
- Configuration concernée : dépendances de développement verrouillées par `uv.lock`.
- Tests attendus : planificateur, manifeste, exécuteur, rapport, opérations et pipeline M-013 réel.
- Milestones concernées : M-000 à M-013 et sous-milestones M13-config, M13-FastAPI et M13-gate-python.

## Liens de traçabilité

- Spécification : `docs/specs/m013_gate_python.md`.
- Plan d’implémentation : `docs/tasks/milestone_013-gate-python/`.
- Tests d’acceptation : `gate_tests/ost_gate/` et les nœuds M-013 du manifeste.
- Commits : migration en cours ; bascule atomique à compléter.

## Notes

La présente ADR ne change pas encore le statut des ADR acceptées qu’elle remplace à terme. Cette modification ne devient valide qu’avec la suppression effective de toutes les entrées PowerShell actives.
