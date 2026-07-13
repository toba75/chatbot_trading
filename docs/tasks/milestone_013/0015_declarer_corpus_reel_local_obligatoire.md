# T-015 - Déclarer le corpus réel local obligatoire

## Milestone

- Nom: M-013 - Durcissement et acceptation V1, tranche `M13-remediation`.
- Source: `docs/specs/plan_remediation_m13.md`, exigences M-012 de corpus pilote et rapport des écarts V1 M-012.
- Objectif métier: rendre impossible une validation réelle sans PDF originaux locaux, déclarés, vérifiables et justifiés.

## Contexte DDD

- Domaine: assistant personnel de trading et d'investissement fondé sur preuves.
- Bounded context: `evaluation` et `source_processing`, avec dépendances vers la gouvernance de preuves.
- Objectif métier: établir l'entrée réelle du pipeline avant toute conversion, recherche ou réponse.
- Langage ubiquitaire: corpus réel, manifeste de corpus, PDF original immuable, hash stable, strate documentaire, justification d'inclusion, absence de fallback.
- Invariants critiques: chaque PDF existe localement; chaque original est immuable; chaque entrée porte un hash stable et une strate; aucun corpus fixture ne remplace le corpus réel.
- Garde-fous: aucun chemin par défaut; aucun PDF généré par test; aucun corpus minimal de secours; aucun original modifié pendant la validation.

## Blocages Ou Préconditions

- État GREEN/RED connu: les gates documentaires M-013 sont GREEN; aucun gate existant ne prouve encore la présence d'un corpus PDF réel local.
- Présence des milestones amont dans master: M-003 à M-013 sont présents dans `master` après rafraîchissement des références; cette tâche étend M-013 sans créer de milestone aval.
- Décisions manquantes: créer une ADR seulement si le format de manifeste local devient un contrat d'exploitation durable non couvert par les ADR existantes.
- Risques: dépendance à des chemins machine; fuite de documents privés; validation GREEN avec corpus fixture; doublons binaires non détectés; sélection documentaire non justifiée.

## Tâches

### T-015 - Déclarer le corpus réel local obligatoire

- But métier: rendre impossible une validation réelle sans PDF réels.
- Portée DDD: EV, SP, manifeste de corpus, références vers originaux locaux, strates documentaires et preuve d'immuabilité.
- Scénario BDD:
  - Given l'utilisateur déclare un corpus local de PDF trading et investissement.
  - When le gate de réalité charge le manifeste.
  - Then chaque PDF existe, possède un hash stable, une strate documentaire et une justification d'inclusion.
- Tests d'acceptation à écrire: `uv run --locked gate`.
- Tests unitaires à écrire: manifeste absent, chemin non résolvable, hash manquant, hash divergent, strate absente, doublon binaire, document hors plage 50-100, exclusion non justifiée, PDF généré par le test.
- Implémentation attendue: créer un format strict de manifeste local, par exemple `docs/evaluation/m013/real_corpus_manifest.schema.json`, et un validateur qui lit un chemin explicite fourni par variable d'environnement obligatoire.
- Invariants et garde-fous: aucun PDF généré; aucun chemin par défaut; aucun corpus minimal de secours; aucun original modifié; aucun contenu PDF privé ajouté au dépôt sans décision explicite.
- Dépendances: exigences M-012 de corpus pilote, `docs/specs/plan_remediation_m13.md`, `docs/governance/m012_v1_gap_report.md`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m013): exiger manifeste corpus reel`
- Commit GREEN: `feat(m013): valider manifeste corpus reel`
