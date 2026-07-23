# T-003 - Publier les contrats de distribution locale

## Milestone

- Nom : M14-distribution-core - Socle de distribution locale durable.
- Source : `docs/specs/plan_distribution.md`, T-003 ; ADR-052.
- Objectif métier : rendre les jobs, résultats, artefacts et limites locales
  versionnés et refusables avant d'ajouter leur persistance.

## Contexte DDD

- Domaine : traitement des sources et plateforme d'exécution locale.
- Bounded contexts : Source Processing publie les contrats documentaires ;
  `platform` transporte les jobs sans interpréter leur contenu métier et valide
  la configuration d'exécution.
- Objectif métier : permettre à n'importe lequel des deux workers généralistes
  de comprendre une page sans dépendre d'un chemin libre, d'un état local ou
  d'une valeur implicite.
- Langage ubiquitaire : `CONVERT_PAGE`, résultat de page, assemblage canonique,
  version de contrat, capacité requise, identité d'artefact, empreinte SHA-256,
  clé d'idempotence, erreur stable, configuration locale stricte.
- Invariants critiques : un seul schéma versionné par contrat ; identité
  d'environnement cohérente avec l'enveloppe du job ; route M-003 immuable ;
  artefact appartenant à SP et résolu sous la racine du profil ; exactement
  deux replicas, 2 Gio et 4 CPU par worker, deux slots Granite globaux et un par
  worker, périphérique `cuda:0`.
- Garde-fous : aucune clé absente, vide, placeholder ou inconnue ; aucun chemin
  absolu ou traversée dans un payload ; aucune valeur issue de l'environnement
  système ; aucun statut calculé depuis les logs ou un compteur mémoire.

## Blocages Ou Préconditions

- État GREEN/RED connu : T-001 et T-002 sont GREEN ; ADR-052 est proposée,
  indexée et cohérente avec ADR-051.
- Présence des milestones amont dans master : M-013 et les contrats ADR-025 de
  claims fenced sont présents dans `master`.
- Décisions manquantes : aucune décision structurante supplémentaire ; toute
  divergence par rapport à ADR-052 bloque la tâche et exige une ADR remplaçante.
- Risques : payload générique non validé, duplication incohérente de l'identité
  entre enveloppe et contenu, erreur instable, contrat couplé à PostgreSQL ou
  Docker, ou configuration qui autorise plus de deux processus Granite.

## Tâches

### T-003 - Publier les contrats de distribution locale

- But métier : donner une forme publique, stricte et sérialisable au travail de
  page et à son résultat avant que deux workers puissent le réclamer.
- Portée DDD : DTO neutres de jobs, contrats SP de page et d'artefact, vocabulaire
  fermé des erreurs, value objects de configuration et validation Compose des
  trois profils.
- Scénario BDD :
  - Given un job `CONVERT_PAGE` versionné désigne une page routée, un traitement
    parent et un artefact source appartenant à l'environnement `test`.
  - When un worker du même déploiement valide le contrat et sa configuration de
    capacité.
  - Then tous les identifiants, versions, empreintes, capacités et limites sont
    explicites, le résultat attendu est déterministe, et toute divergence
    d'environnement, d'artefact, de route, de version ou de capacité est refusée
    avant le premier accès au modèle.
- Tests d'acceptation à écrire : round-trip strict des versions initiales de
  `CONVERT_PAGE`, résultat de page et `ASSEMBLE_CANONICAL_DOCUMENT` ; refus des
  champs absents, supplémentaires ou incohérents ; identité environnement et
  déploiement incompatible ; clé d'idempotence divergente ; route ou numéro de
  page invalide ; artefact hors racine ou hash divergent ; erreurs stables de
  capacité Granite, CUDA, OOM et artefact ; rendu des trois profils avec deux
  replicas, 2 Gio, 4 CPU, `cuda:0`, capacité globale 2 et capacité par worker 1.
- Tests unitaires à écrire : value objects de version, identité d'artefact,
  exigence de capacité, état et erreur de résultat ; sérialisation canonique ;
  comparaison de rejeu identique ou divergent ; invariants du schéma de
  configuration ; rejet de `auto`, CPU, valeur nulle, valeur par défaut, troisième
  replica et limite Granite supérieure aux bornes.
- Implémentation attendue : publier des types immuables sous la frontière de
  contrats appropriée, conserver `JobRequest` neutre, introduire les parseurs et
  sérialisations fermés, étendre `config/application.schema.json` et les types de
  configuration, exprimer les limites dans les fichiers versionnés des trois
  profils et renforcer les validateurs Compose sans créer encore de job de page
  ni exécuter de migration.
- Invariants et garde-fous : le job ne cible aucun worker particulier ; la
  capacité requise ne modifie pas la route ; `SKIP_EMPTY` reste un état terminal
  sans convertisseur ; `TARGETED_ENRICHMENT` compte une seule unité après
  adjudication ; les métriques techniques ne deviennent pas la progression
  publique.
- Dépendances : T-002 ; ADR-025, ADR-040, ADR-042, ADR-046, ADR-051 et ADR-052 ;
  `app/contracts/technical_jobs.py` ; domaine de conversion pagewise M-004 ;
  configuration M13-environments.
- Commandes de validation : tests unitaires et d'acceptation des contrats M14 ;
  `uv run --locked gate --scope m004` ;
  `uv run --locked gate --scope m013_config` ;
  `uv run --locked gate --scope m013_environments` ;
  `uv run --locked gate --scope m014_distribution_core` ;
  `uv run --locked gate`.
- Commit RED : `test(m014-core): couvrir contrats stricts de distribution locale`.
- Commit GREEN : `feat(m014-core): publier contrats de jobs et capacité locale`.
