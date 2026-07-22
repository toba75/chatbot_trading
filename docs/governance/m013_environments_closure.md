# État de livraison M13-environments

## Décision

L'implémentation statique des environnements explicites est GREEN au regard
d'ADR-046 et ADR-048. Son statut machine reste
`SUBMILESTONE_GREEN_M013_OPEN` : ce sous-milestone ne clôt pas M-013.

Les rapports versionnés produits avant la réduction du runtime sont
explicitement `STALE`. Ils prouvaient une ancienne pile à six workers et
dix-sept conteneurs ; ils ne constituent plus une preuve GREEN du runtime
courant et ne sont jamais consommés par la gate offline.

## Contrat live courant à requalifier

| Profil | Parcours exigé | Cardinalité exigée | Isolation exigée |
|---|---:|---|---|
| development | 1 parcours réel, redémarrage inclus | 3 progressions `SUCCEEDED`, 4 workers, 14 conteneurs, 3 jobs | document étranger absent, volumes conservés, HTTPS validé par CA |
| test | 2 parcours réels depuis des piles vides | par cycle : 3 progressions `SUCCEEDED`, 4 workers, 14 conteneurs, 3 jobs | credentials étrangers inaccessibles, seuls les volumes test propriétaires supprimés, HTTPS validé par CA |
| production | 1 parcours réel, redémarrage inclus | 3 progressions `SUCCEEDED`, 4 workers, 14 conteneurs, 3 jobs | document étranger absent, volumes conservés, HTTPS validé par CA |

Seule `uv run --locked gate --scope m013_environments --live` peut qualifier ce
tableau. Elle exige les nouveaux rapports à une révision commune égale à HEAD,
le hash de la CA Caddy exportée et `https_ca_verified=true`. L'option offline
valide le contrat, la matrice, la documentation et la traçabilité, avec zéro
exécution live déclarée.

## Preuves et couverture

- Archive historique marquée `STALE` :
  `docs/governance/m013_environments_execution_evidence.json`.
- Matrice d'étanchéité courante :
  `docs/governance/m013_environments_isolation_matrix.json` et sa lecture
  humaine Markdown.
- Traçabilité ADR/spec/code/tests/runbooks :
  `docs/governance/m013_environments_traceability.json`.
- Exploitation : `docs/runbooks/environnements_explicites.md`.
- Gate statique : `uv run --locked gate --scope m013_environments --offline`.
- Gate live réelle :
  `uv run --locked gate --scope m013_environments --live`.

## Politique RED

La preuve live est RED si un profil manque, si une exécution ne porte pas
exactement quatre identités workers et quatorze conteneurs, si les appels HTTPS
ne valident pas la CA exportée, si deux exécutions réutilisent un identifiant
borné, si la révision diffère de HEAD, si une ressource mutable n'est pas
inventoriée ou si une donnée sensible apparaît. Aucun écart n'est accepté
implicitement.
