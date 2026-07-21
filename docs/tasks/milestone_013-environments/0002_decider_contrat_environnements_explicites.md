# T-002 - Décider le contrat des environnements explicites

## Milestone

- Nom: M13-environments - Environnements explicites et données étanches.
- Source: demande utilisateur du 2026-07-21; ADR-016; M13-config.
- Objectif métier: donner un sens unique et testable à `development`, `test` et `production` avant toute modification de runtime.

## Contexte DDD

- Domaine: plateforme d'exécution et exploitation.
- Bounded context: `platform.configuration`.
- Objectif métier: publier l'identité, les responsabilités et les interdictions de chaque environnement.
- Langage ubiquitaire: `ApplicationEnvironment`, `deployment_id`, configuration complète, ressource mutable, identité de stockage, absence de fallback.
- Invariants critiques: ensemble fermé à trois valeurs; sélection explicite; trois fichiers complets; aucune fusion ou valeur héritée implicitement.
- Garde-fous: ADR-016 n'est pas réécrite; ADR-045 la remplace explicitement pour la règle du chemin unique; l'interdiction des variables d'environnement reste applicable.

## Blocages Ou Préconditions

- État GREEN/RED connu: T-001 GREEN.
- Présence des milestones amont dans master: M-000 à M-012 visibles.
- Décisions manquantes: décision structurante ADR-045 et spécification M13-environments à créer pendant cette tâche.
- Risques: confondre une variable d'environnement avec un environnement applicatif explicite, ou introduire un socle partiel fusionné silencieusement.

## Tâches

### T-002 - Décider le contrat des environnements explicites

- But métier: rendre les trois profils auditables et refuser toute ambiguïté avant le premier accès externe.
- Portée DDD: value object `ApplicationEnvironment`, identité `deployment_id`, erreurs publiques et règles d'isolation de toutes les ressources mutables.
- Scénario BDD:
  - Given un opérateur choisit un profil parmi `development`, `test` et `production`.
  - When le contrat de configuration du profil est validé.
  - Then l'identité est complète, appartient à l'ensemble fermé, décrit toutes ses ressources et ne dépend d'aucune valeur implicite ou variable système.
- Tests d'acceptation à écrire: contrat des trois profils, refus d'un profil absent/inconnu, refus d'une configuration partielle, refus d'une fusion implicite, exigence de ressources distinctes.
- Tests unitaires à écrire: validation de `environment`, `deployment_id`, chemins de secrets, matrice d'unicité des ressources et codes `CONFIG_ENVIRONMENT_UNKNOWN`, `CONFIG_ENVIRONMENT_MISMATCH`, `DATASTORE_ENVIRONMENT_MISMATCH`, `WORKER_ENVIRONMENT_MISMATCH`.
- Implémentation attendue: créer ADR-045 depuis le template, marquer ADR-016 remplacée sans changer son sens, mettre à jour l'index ADR, publier la spécification détaillée M13-environments et préparer les évolutions de schéma attendues par les tâches suivantes.
- Invariants et garde-fous: aucun `.env`, `os.environ`, `getenv`, `env_file` ou `environment:` applicatif; aucun secret en clair; aucune valeur par défaut; aucun profil générique `local`.
- Dépendances: T-001; ADR-016; `docs/adr/TEMPLATE.md`; spécification M13-config.
- Commandes de validation: `uv run --locked gate --scope governance`; tests M13-environments du contrat; `uv run --locked gate`.
- Commit RED: `test(m13-environments): couvrir contrat des profils explicites`.
- Commit GREEN: `docs(m13-environments): decider isolation des environnements`.
