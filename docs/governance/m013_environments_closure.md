# Rapport de livraison M13-environments

## Décision

Le sous-milestone « environnements explicites et données étanches » est GREEN
au regard d'ADR-045 et des preuves listées ci-dessous. Son statut machine est
`SUBMILESTONE_GREEN_M013_OPEN` : cette livraison ne déclare pas le milestone
M-013 global clôturé.

## Preuves d'exécution

| Profil | Parcours | Issue | Isolation démontrée |
|---|---:|---|---|
| development | 1 parcours réel, redémarrage inclus | 3 progressions `SUCCEEDED`, 6 workers, 3 jobs | document absent de test et production, volumes conservés |
| test | 2 parcours réels depuis des piles vides | 6 progressions `SUCCEEDED`, 6 workers et 3 jobs par cycle | credentials étrangers inaccessibles, seules les ressources test supprimées |
| production | 1 parcours réel, redémarrage inclus | 3 progressions `SUCCEEDED`, 6 workers, 3 jobs | document absent de development et test, volumes conservés |

Les quatre exécutions utilisent le PDF réel de 38 pages, les contrats HTTP
publics, PostgreSQL, Qdrant, l'outbox, les relais, les workers et le Spark réel.
Les identifiants de documents, versions, projections, réponses, appels Spark,
PDF réémis, déploiements et hashes de configuration sont distincts quand ils
doivent l'être.

La preuve machine versionnée est
`docs/governance/m013_environments_execution_evidence.json`. Elle conserve les
données d'exécution et les SHA-256 des trois rapports sources. Seuls les
chemins absolus propres au poste ont été normalisés en chemins relatifs. Aucun
secret, token, mot de passe ou contenu complet du PDF n'est copié.

## Couverture

- Matrice d'étanchéité :
  `docs/governance/m013_environments_isolation_matrix.json` et sa lecture
  humaine Markdown.
- Traçabilité ADR/spec/code/tests/rapports/runbooks :
  `docs/governance/m013_environments_traceability.json`.
- Exploitation : `docs/runbooks/environnements_explicites.md`.
- Gate statique : `uv run --locked gate --scope m013_environments`.
- Gate live réelle :
  `uv run --locked gate --scope m013_environments --live`.

## Politique RED

La preuve est RED si un profil manque, si deux exécutions réutilisent un
identifiant borné, si une ressource mutable ou un worker n'est pas inventorié,
si une donnée sensible apparaît ou si une trace ne relie plus ADR-045, la
spécification, le code, les tests, les rapports et le runbook. Aucun écart
n'est accepté implicitement.
