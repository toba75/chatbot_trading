# T-011 - Exposer les endpoints de backtest et d'expériences

## Milestone
- Nom: M-011 - Expérience reproductible.
- Source: M-011, API publique `POST /v1/strategies/{id}/backtest` et `GET /v1/experiments/{id}`.
- Objectif métier: permettre le lancement et la consultation d'expériences sans exposer les stockages internes EX, SD ou plateforme.

## Contexte DDD
- Domaine: expérimentation quantitative reproductible.
- Bounded context: EX exposé par adaptateur HTTP, avec SD comme validation amont.
- Objectif métier: offrir un contrat public strict pour planifier un backtest et consulter son résultat.
- Langage ubiquitaire: endpoint de backtest, expérience, `ExperimentId`, statut public, diagnostic public, artefact, erreur publique, champ interdit.
- Invariants critiques: `POST /v1/strategies/{id}/backtest` valide le snapshot avant planification EX; `GET /v1/experiments/{id}` expose le résultat public sans stockage interne; les erreurs sont stables et explicites.
- Garde-fous: pas de champ `experiment_registry_table`; pas de payload moteur brut; pas de prompt ou texte source complet; pas de backtest synchrone implicite si le statut est planifié; pas de statut HTTP ambigu.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-010.
- Présence des milestones amont dans master: M-010 présent dans `master`.
- Décisions manquantes: aucune si l'adaptateur reste framework-free comme les endpoints SD existants.
- Risques: mélanger contrôleur HTTP et règles de domaine; exposer un store interne; retourner un résultat sans distinguer `PLANNED`, `RUNNING`, `COMPLETED`, `FAILED` et `CANCELLED`.

## Tâches
### T-011 - Exposer les endpoints de backtest et d'expériences
- But métier: rendre l'expérimentation accessible par contrat produit sans fuite d'implémentation.
- Portée DDD: adaptateur HTTP EX, DTO stricts de backtest, lecture publique d'expérience, mapping des erreurs publiques, rejet des champs interdits et intégration avec les handlers EX.
- Scénario BDD:
  - Given un `StrategySnapshot` consultable et des entrées de backtest explicites.
  - When `POST /v1/strategies/{id}/backtest` est appelé.
  - Then EX planifie l'expérience ou renvoie une erreur publique stable, et `GET /v1/experiments/{id}` expose le statut et le résultat public sans stockage interne.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue tant qu'un champ interne est accepté, qu'un statut public est ambigu, qu'un résultat moteur brut fuit, qu'un snapshot absent retourne un succès ou qu'un `GET` crée une expérience.
- Tests unitaires à écrire: tests de l'adaptateur HTTP EX pour corps invalide, champ interdit, snapshot absent, données absentes, coût absent, statut `PLANNED`, statut `RUNNING`, statut `COMPLETED`, statut `FAILED`, résultat archivé et mapping des erreurs.
- Implémentation attendue: créer un adaptateur HTTP framework-free pour EX, connecter les cas d'usage M-011, définir les DTO publics, mapper les diagnostics vers codes publics et enrôler les tests HTTP.
- Invariants et garde-fous: aucun stockage interne exposé; aucune création par `GET`; aucune réponse 200 pour diagnostic bloquant; aucun payload d'artefact non public; aucun fallback vers une stratégie courante.
- Dépendances: T-010; adaptateur HTTP SD M-010; `app/contracts/strategy_experiments.py`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m011): couvrir contrat http experiences`
- Commit GREEN: `feat(m011): exposer endpoints backtest experiences`
