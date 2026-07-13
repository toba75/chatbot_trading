# T-010 - Exposer les endpoints de stratégie

## Milestone
- Nom: M-010 - Stratégie candidate attribuée.
- Source: M-010 et API v4.1, endpoints `POST /v1/strategies/compile` et `GET /v1/strategies/{id}`.
- Objectif métier: permettre au produit de compiler une stratégie candidate attribuée et de relire son état sans exposer les détails internes SD.

## Contexte DDD
- Domaine: conception de stratégies candidates attribuées.
- Bounded context: SD, exposé par adaptateur HTTP.
- Objectif métier: publier une surface produit stricte pour demander la compilation et consulter stratégie, diagnostics, origines et snapshot.
- Langage ubiquitaire: endpoint stratégie, compilation, lecture de stratégie, diagnostic bloquant, origine de règle, snapshot, erreur publique stable.
- Invariants critiques: l'API ne déclenche pas de backtest; les erreurs publiques distinguent stratégie absente, règle non attribuée, conflit non résolu, donnée actuelle requise et stratégie non compilable avec les codes `STRATEGY_RULE_ORIGIN_MISSING`, `STRATEGY_CONFLICT_UNRESOLVED` et `CURRENT_DATA_REQUIRED`; l'adaptateur ne contourne pas le domaine.
- Garde-fous: pas de fallback HTTP vers une stratégie vide; pas de création implicite au `GET`; pas d'exposition de payload interne RA ou EG; pas de champ de rentabilité.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-009.
- Présence des milestones amont dans master: M-009 présent dans `master`.
- Décisions manquantes: aucune si l'API reste l'adaptateur de commandes SD.
- Risques: mélanger endpoint de compilation M-010 et endpoint de backtest M-011; masquer un diagnostic bloquant sous un HTTP 200 ambigu; retourner un message libre sans code public stable; accepter un schéma partiel.

## Tâches
### T-010 - Exposer les endpoints de stratégie
- But métier: rendre la compilation et la consultation de stratégie utilisables par CV ou un client local sans fuite de modèle interne.
- Portée DDD: adaptateur HTTP SD, schémas de requête et réponse, mapping d'erreurs publiques, handlers applicatifs de compilation et lecture, dépôt de stratégie et snapshot store.
- Scénario BDD:
  - Given une stratégie candidate contient une règle sans origine.
  - When `POST /v1/strategies/compile` est appelé.
  - Then l'API retourne un refus de compilation avec le diagnostic bloquant, le code public `STRATEGY_RULE_ORIGIN_MISSING` et aucun snapshot n'est créé.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue tant que les endpoints `POST /v1/strategies/compile` et `GET /v1/strategies/{id}` ne publient pas les diagnostics, origines et codes publics stables `STRATEGY_RULE_ORIGIN_MISSING`, `STRATEGY_CONFLICT_UNRESOLVED` et `CURRENT_DATA_REQUIRED`.
- Tests unitaires à écrire: tests d'adaptateur HTTP pour requête invalide, stratégie absente, compilation refusée avec `STRATEGY_RULE_ORIGIN_MISSING`, conflit bloquant exposé avec `STRATEGY_CONFLICT_UNRESOLVED`, donnée actuelle manquante exposée avec `CURRENT_DATA_REQUIRED`, compilation acceptée, lecture de snapshot, absence de backtest, mapping d'erreur et rejet de champ inconnu.
- Implémentation attendue: créer `app/strategy_design/adapters/strategy_http.py`, câbler les handlers applicatifs, définir les DTO publics stricts, mapper explicitement les diagnostics SD vers les codes publics stables et enrôler les routes sans dépendance du domaine au framework web.
- Invariants et garde-fous: aucune création implicite au `GET`; aucun HTTP 200 pour diagnostic bloquant sans statut métier explicite et code public stable; aucun backtest; aucun fallback vers un dépôt global caché.
- Dépendances: T-009; `app/web_app.py` ou registre d'adaptateurs existant; contrats M-001; DDD-ADR-008.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m010): couvrir contrat http strategies`
- Commit GREEN: `feat(m010): exposer endpoints strategies`
