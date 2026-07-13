# T-001 - Vérifier la précondition GREEN de la conversion réelle

## Milestone

- Nom : M04-conversion - Conversion canonique réellement exécutable.
- Source : `docs/specs/m004_version_canonique_publiee.md`, T-004 de `docs/specs/plan_remediation_m13.md` et UI-019 de `docs/specs/ui.md`.
- Objectif métier : ne rendre l'action de conversion disponible qu'à partir d'un socle M13-FastAPI officiellement intégré et complètement GREEN.

## Contexte DDD

- Domaine : traitement des sources documentaires.
- Bounded context : SP.
- Objectif métier : préserver l'intégrité du `SourceDocument`, du `DocumentProcessingRun` routé et de la future `CanonicalSource` avant toute nouvelle transition de conversion.
- Langage ubiquitaire : précondition GREEN, route explicite, conversion canonique, action UI disponible.
- Invariants critiques : aucune action UI n'est proposée si la chaîne réelle n'est pas livrable ; une dépendance M-003 absente ou une gate RED bloque le milestone.
- Garde-fous : pas de reprise depuis une base locale non intégrée à `master` ; pas de conclusion GREEN partielle.

## Blocages Ou Prérequis

- État GREEN/RED connu : le socle a été GREEN sur `9edeab957`, puis la vérification de cette tranche a révélé un RED de gouvernance sur `gate.historical-references` : l'empreinte historique d'ADR-010 était incohérente avec le contenu versionné. Ce défaut de portabilité de l'allowlist doit être corrigé avant d'ouvrir la conversion.
- Présence des milestones amont dans master : M-000, M-001, M-002 et M-003, ainsi que M13-FastAPI, sont visibles depuis `master`.
- Décisions manquantes : aucune ; ADR-001 à ADR-004, ADR-018, ADR-019, ADR-024, ADR-025 et ADR-031 sont applicables.
- Risques : une régression du socle FastAPI, de l'outbox ou du worker invaliderait toutes les tranches suivantes.

## Tâches

### T-001 - Vérifier la précondition GREEN de la conversion réelle

- But métier : autoriser l'ouverture de la tranche seulement si le socle officiel peut exécuter sa validation canonique.
- Portée DDD : gouvernance de livraison ; aucune transition métier nouvelle.
- Scénario BDD :
  - Given `master` contient les contrats M-003 et le runtime M13-FastAPI, et une ADR historique autorisée est extraite avec des fins de lignes Windows.
  - When la gate canonique verrouillée contrôle l'intégrité de l'allowlist historique.
  - Then elle compare une représentation stable du contenu versionné, accepte l'ADR inchangée et le milestone démarre uniquement si chaque nœud est GREEN et exécuté une seule fois.
- Tests d'acceptation à écrire : la gate canonique verrouillée, le contrôle de l'ancêtre `master` et la reproduction du hachage avec fins de lignes Windows.
- Tests unitaires à écrire : un test du validateur des références historiques prouvant que le hachage est invariant aux fins de lignes de l'arbre de travail, tout en restant RED dès que le contenu sémantique est modifié.
- Implémentation attendue : corriger le calcul de l'intégrité de l'allowlist pour utiliser la représentation stable de l'index Git, sans élargir la liste fermée ; consigner l'identifiant de base, la commande et son résultat dans le journal M04-conversion.
- Invariants et garde-fous : ne pas créer de code, de dépendance ou de bouton dans cette tranche ; tout RED bloque la suite.
- Dépendances : aucune.
- Commandes de validation : `uv run --locked gate --workers 8` ; `git merge-base --is-ancestor master HEAD`.
- Commit RED : `test(gate): reproduire l'intégrité historique sous Windows`.
- Commit GREEN : `fix(gate): stabiliser l'allowlist historique`.
