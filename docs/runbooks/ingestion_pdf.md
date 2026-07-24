# Runbook d'ingestion PDF locale M-014

## Statut

- Identifiant : `M014-Runbook-PdfIngestion-2.0`.
- Contextes : UI locale, Source Processing (SP), plateforme et Knowledge Access
  (KA).
- Sources : spécifications M-003, M-004, M-005, M13-FastAPI et
  `docs/specs/m014_local_pipeline_documentaire_distribue.md`.
- ADR applicables : ADR-018, ADR-020, ADR-021, ADR-024, ADR-025, ADR-046,
  ADR-052 et ADR-053.
- Portée livrée : enregistrement du PDF réel, diagnostic, conversion distribuée
  locale, publication `CanonicalSourcePublished` et projection automatique dans
  le Qdrant du même environnement.

## Scénario BDD

- **Given** la stack locale et ses secrets sont prêts, les migrations 023 à 029
  sont appliquées et les workers déclarent la même identité d'environnement ;
- **When** l'utilisateur ajoute un PDF, le diagnostique puis demande sa
  conversion sous `m014-page-fanout-v1` ;
- **Then** SP distribue les pages, publie une version canonique complète et KA
  crée automatiquement une projection `REQUESTED`, l'exécute puis la rend
  `SEARCHABLE` sans appel manuel à `/index`.

## Préconditions et démarrage

1. Fournir hors Git les secrets `config/secrets/development/*`.
2. Exécuter `uv run development` depuis la racine du dépôt. La composition
   vérifie Docker et démarre PostgreSQL, Qdrant authentifié, le gateway LLM,
   l'API, deux replicas `worker-documents` et le worker KA réel.
3. Le worker documentaire relaie ses outbox de pages et de complétions avant de
   réclamer `CONVERT_PAGE` ou `ASSEMBLE_CANONICAL_DOCUMENT`. Le worker KA relaie
   `CanonicalSourcePublished`, puis son outbox `PROJECT_DOCUMENT`, avant de
   réclamer la projection.
4. Attendre l'ouverture de l'UI sur
   `https://localhost:18443/ui/corpus-pdf`.

Si un service, un secret, CUDA, Qdrant, PostgreSQL ou un worker est indisponible,
corriger l'erreur explicite. Aucun service, parseur, périphérique ou secret de
substitution n'est sélectionné silencieusement.

## Ajouter et diagnostiquer un PDF

1. Ouvrir le corpus PDF et choisir un fichier `application/pdf` de 50 Mio au
   maximum.
2. Saisir le titre, les auteurs, l'année et l'édition. Le nom du fichier n'est
   jamais utilisé comme métadonnée.
3. Envoyer le formulaire. La redirection `303` conserve le `document_id` et le
   marqueur de doublon éventuel.
4. Demander le diagnostic. L'UI lit uniquement la progression publique
   persistée : phase, unités réalisées, total et erreur terminale.
5. Un statut `DIAGNOSED` prouve le diagnostic, pas encore la conversion.
   `MANUAL_REVIEW` doit être résolu explicitement avant la suite.

Le PDF original est streamé et contrôlé par SHA-256. Son chemin interne et les
secrets ne sont jamais exposés dans l'UI, les redirections ou les logs.

## Convertir et projeter automatiquement

1. Demander la conversion du document diagnostiqué. La configuration active
   doit porter explicitement `m014-page-fanout-v1` ; une valeur absente ou
   inconnue est refusée.
2. SP fige le manifeste, persiste les pages `SKIP_EMPTY` et produit les jobs
   `CONVERT_PAGE` pour les autres pages. Les deux workers documentaires
   partagent exactement deux slots Granite, un par replica, sur `cuda:0`.
3. La dernière complétion valide produit
   `ASSEMBLE_CANONICAL_DOCUMENT`. La publication réussie rend visibles dans une
   même transaction SP la version canonique, la progression terminale et
   l'outbox `CanonicalSourcePublished`.
4. Le worker KA consomme cette publication dans sa transaction propre, crée la
   projection `REQUESTED` et l'outbox `PROJECT_DOCUMENT`, puis publie une
   génération Qdrant complète avant `SEARCHABLE`.
5. L'écran affiche la progression publique persistée de `CONVERT_DOCUMENT` et
   `PROJECT_DOCUMENT`. Il ne déduit jamais l'avancement depuis les logs ou un
   compteur local.

La projection automatique est le parcours nominal M-014. L'ancien endpoint
`/index` reste un contrat de compatibilité M-005 ; il n'est ni requis ni appelé
par ce runbook après `CanonicalSourcePublished`.

## États et erreurs opérateur

| État ou code | Sens et action |
|---|---|
| `QUEUED`, `RUNNING` | Attendre la progression persistée ; ne pas relancer la commande pour fabriquer un avancement. |
| `CANONICAL_ACCEPTED` | La version canonique et son événement sont committés atomiquement. |
| `REQUESTED`, `BUILDING`, `BUILT`, `INDEXING` | La projection automatique KA est en cours. |
| `SEARCHABLE` | La génération Qdrant exacte a été vérifiée et peut être recherchée. |
| `ARTIFACT_HASH_MISMATCH` | Restaurer l'artefact attendu ; aucun contenu alternatif n'est accepté. |
| `CANONICAL_ARTIFACT_HASH_MISMATCH` | Restaurer l'artefact canonique publié ; KA ne projette pas un fichier divergent. |
| `PROJECTION_REPLAY_INCOMPLETE` | La génération `SEARCHABLE` n'est plus exacte ; traiter la reprise explicite, sans index de secours. |
| `JOB_LEASE_LOST` ou `PROJECTION_EVENT_LEASE_LOST` | L'ancien détenteur ne doit plus muter l'état ; laisser le détenteur courant reprendre. |

Les erreurs HTTP d'admission restent explicites : `401`
`LOCAL_API_TOKEN_REQUIRED`, `403` `LOCAL_API_TOKEN_INVALID` ou
`UI_ORIGIN_FORBIDDEN`, `413` `HTTP_REQUEST_TOO_LARGE`, `422`
`SOURCE_UNREADABLE`, et `507` `CORPUS_QUOTA_EXCEEDED`.

## Reprise et migrations

Les migrations 027 et 028 durcissent les contraintes, les claims et la
coexistence bornée. La migration 029 exécute la phase **expand** décidée par
ADR-053 : elle enrichit les anciens contrats depuis leurs preuves durables,
révoque les claims réécrits, reconstruit les outbox SP historiques et remet les
projections qualifiées dans un chemin de rejeu explicite. Le relais public fait
ensuite converger KA sans DML intercontexte.

La phase **contract** destructive est différée jusqu'au drainage démontré des
anciens writers. Un rollback applicatif arrête les nouvelles admissions, draine
les jobs et laisse les publications déjà committées converger ; il ne supprime
pas les migrations et ne réécrit pas les résultats.

## Preuves ciblées

Les sous-agents utilisent les tests et scopes ciblés documentés par leur tâche.
La gate globale de clôture n'est pas une commande opératoire de ce runbook :
elle appartient exclusivement à l'orchestrateur selon la politique du milestone.

## Garde-fous

- Aucun fallback silencieux, aucune route documentaire par défaut et aucune
  correction silencieuse d'un PDF.
- Aucune publication canonique partielle et aucune projection avant
  `CanonicalSourcePublished`.
- Aucun secret, PDF complet ou chemin interne dans les logs, OpenAPI, HTML ou
  redirections.
- Aucune progression synthétique et aucune lecture UI directe de l'état des
  workers, de PostgreSQL ou de Qdrant.
