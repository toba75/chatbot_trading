# Gate Python uv à exécution unique

## Objectif

Remplacer l’orchestration PowerShell récursive par une gate Python unique, reproductible avec `uv`, qui couvre les validations de gouvernance, d’architecture, de plateforme, de configuration, de sécurité et le pipeline produit réel M-013.

## Scénarios BDD

### Gate canonique

- Given un dépôt complet, un environnement uv verrouillé et les services obligatoires du pipeline réel M-013 disponibles.
- When `uv run --locked gate` est exécuté.
- Then chaque nœud du manifeste est collecté et exécuté une seule fois, le rapport JSON contient une occurrence par identifiant et le résultat est `Gate GREEN` uniquement si tous les nœuds sont GREEN.

### Exécution ciblée

- Given un manifeste valide et le scope `m008`.
- When `uv run gate --scope m008` est exécuté.
- Then le plan contient le scope et ses dépendances, ne relance aucun nœud et le résultat est `SCOPE GREEN`, jamais `Gate GREEN`.

### Service réel absent

- Given le nœud live M-013 requis et un service obligatoire indisponible.
- When `uv run gate` est exécuté.
- Then le nœud live est RED avec son identifiant et son erreur explicite ; aucun mock, stub ou résultat synthétique ne le remplace.

### Manifeste invalide

- Given un manifeste vide, cyclique, dupliqué, hors dépôt ou référençant un fichier absent.
- When la gate construit le plan.
- Then elle retourne RED avant toute exécution et nomme précisément le défaut.

## Invariants

- Un nœud possède un identifiant et un chemin uniques.
- Un nœud exécuté GREEN reste disponible en mémoire pour ses dépendants sans être relancé.
- Les tests `unit` ne lancent ni Git, ni processus, ni service, ni vrai timeout.
- Les groupes séries ne se chevauchent jamais.
- Une sortie `skipped`, `xfail` ou un écart de collecte interdit le GREEN canonique.
- Les commandes et sources actives ne contiennent pas `powershell`, `pwsh` ni une référence `.ps1`.

## Mesure de départ

| Mesure | Diagnostic initial | État observé | Écart |
|---|---:|---:|---:|
| Scripts PowerShell sous `scripts/` | 58 | 61 | +3 |
| Tests PowerShell sous `tests/` | 329 | 374 | +45 |
| Fichiers `.ps1` suivis | 387 | 435 | +48 |
| Validations déclarées par `scripts/test.ps1` | 36 | 37 | +1 |
| Tests déclarés par `scripts/test.ps1` | 309 | 309 | 0 |
| Tests `m013_config` | 15 | 15 | 0 |

L’amplification, le nombre de sous-commandes et les multiplicités de test sont recalculés par le rapport comparatif avant la bascule ; ils ne sont pas déduits d’un ancien état de branche.
