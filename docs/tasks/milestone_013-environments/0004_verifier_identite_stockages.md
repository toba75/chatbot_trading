# T-004 - Vérifier l'identité des stockages avant usage

## Milestone

- Nom: M13-environments - Environnements explicites et données étanches.
- Source: contrat T-002; exigence d'étanchéité des données.
- Objectif métier: empêcher qu'une configuration correcte en apparence accède au stockage d'un autre environnement.

## Contexte DDD

- Domaine: plateforme de données.
- Bounded context: `platform.configuration`, persistance et projections.
- Objectif métier: faire de l'identité du stockage un invariant vérifié, pas une convention de nommage.
- Langage ubiquitaire: identité attendue, identité observée, `deployment_id`, préflight de stockage, incompatibilité terminale.
- Invariants critiques: PostgreSQL, Qdrant et chaque racine de fichiers portent l'identité du profil; la vérification précède lecture, écriture, migration et claim.
- Garde-fous: une URL distincte ou un hash de configuration ne suffit pas à prouver l'identité; aucune identité absente n'est créée silencieusement sur un stockage non vierge.

## Blocages Ou Préconditions

- État GREEN/RED connu: T-001 à T-003 GREEN.
- Présence des milestones amont dans master: M-000 à M-012 visibles.
- Décisions manquantes: le contrat T-002 fixe le format des marqueurs.
- Risques: vérifier après migration, ou considérer un stockage sans marqueur comme compatible.

## Tâches

### T-004 - Vérifier l'identité des stockages avant usage

- But métier: interrompre un mauvais raccordement avant que la première donnée métier soit touchée.
- Portée DDD: table d'identité PostgreSQL, marqueur Qdrant, marqueur signé ou strict de racine fichier, préflight commun à tous les composition roots.
- Scénario BDD:
  - Given un processus `test` reçoit par erreur les coordonnées d'un stockage `production`.
  - When le processus exécute son préflight avant toute opération métier.
  - Then il termine avec `DATASTORE_ENVIRONMENT_MISMATCH`, ne migre rien, ne réclame aucun job et ne lit ni n'écrit de donnée métier.
- Tests d'acceptation à écrire: identité concordante pour chaque type de stockage; mismatch croisé 3 x 3; marqueur absent sur stockage vierge/non vierge; ordre de vérification avant migration et accès.
- Tests unitaires à écrire: parsing d'identité, comparaison `environment`/`deployment_id`, atomicité de création initiale, erreurs stables et absence d'appel aval après mismatch.
- Implémentation attendue: introduire le contrat d'identité des ressources et le brancher dans API, migrations, workers, Qdrant et stores de fichiers avant leur usage.
- Invariants et garde-fous: fail-closed; aucune réécriture automatique d'identité; aucune option `force`; aucune récupération par nom de volume ou hostname seulement.
- Dépendances: T-002 et T-003; migrations PostgreSQL; adaptateurs Qdrant; stores de fichiers.
- Commandes de validation: tests M13-environments d'identité; tests de migrations et de persistance ciblés; `uv run --locked gate`.
- Commit RED: `test(platform): couvrir identite des stockages`.
- Commit GREEN: `feat(platform): refuser les stockages hors environnement`.
