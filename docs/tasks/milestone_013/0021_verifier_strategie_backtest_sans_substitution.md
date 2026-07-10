# T-021 - Vérifier les scénarios stratégie et backtest sans substitution

## Milestone

- Nom: M-013 - Durcissement et acceptation V1, tranche `M13-remediation`.
- Source: `docs/specs/plan_remediation_m13.md`, écarts V1 SD, contrats EX M-011 et exigences de conservation des résultats négatifs.
- Objectif métier: empêcher une réponse générique sur les stratégies de trading lorsque les preuves, la calibration ou les données de marché réelles manquent.

## Contexte DDD

- Domaine: assistant personnel de trading et d'investissement fondé sur preuves.
- Bounded context: `strategy_design`, `experimentation`, `research_answering`, `evidence_governance` et `conversation`.
- Objectif métier: produire uniquement des règles de stratégie sourcées et backtestables, ou refuser explicitement lorsque les preuves ou données réelles manquent.
- Langage ubiquitaire: stratégie candidate, règle sourcée, paramètre calibré, donnée de marché versionnée, backtest reproductible, résultat négatif conservé, refus explicite.
- Invariants critiques: une stratégie ne peut pas inventer une meilleure règle universelle; un backtest ne tourne pas sur données fictives; un résultat négatif n'est pas supprimé.
- Garde-fous: pas de conseil stratégique non sourcé; pas de paramètre sans calibration; pas de backtest non déterministe; pas de substitution par données synthétiques.

## Blocages Ou Préconditions

- État GREEN/RED connu: SD reste bloquant dans le rapport V1; EX est accepté sur les backtests pilotes mais la chaîne produit réelle doit refuser les substitutions.
- Présence des milestones amont dans master: M-003 à M-013 sont présents dans `master`; M-010 et M-011 fournissent les contrats SD et EX à respecter.
- Décisions manquantes: aucune si le comportement refuse explicitement les données manquantes; créer une ADR seulement si une nouvelle politique de marché ou de calibration est introduite.
- Risques: réponse générique "meilleure stratégie"; paramètres non calibrés; données de marché absentes; résultat négatif masqué; backtest lancé sur données fictives.

## Tâches

### T-021 - Vérifier les scénarios stratégie et backtest sans substitution

- But métier: empêcher une réponse générique sur les stratégies de trading lorsque la preuve, la calibration ou les données réelles manquent.
- Portée DDD: SD, EX, RA, EG, CV, preuves documentaires, données de marché versionnées et diagnostics de refus.
- Scénario BDD:
  - Given l'utilisateur demande "Quelle est la meilleure stratégie Short possible ?"
  - When le chatbot route la demande vers stratégie.
  - Then le système recherche les preuves réelles, propose uniquement des règles sourcées, refuse les paramètres non calibrés, et lance un backtest seulement si les données de marché versionnées sont disponibles.
- Tests d'acceptation à écrire: `tests/m013/validate_real_strategy_short_acceptance.ps1`.
- Tests unitaires à écrire: règle sans origine, paramètre sans calibration, donnée de marché absente, backtest non déterministe, résultat négatif supprimé, réponse générique non sourcée, preuve RA ignorée.
- Implémentation attendue: relier CV vers SD/EX via les façades existantes et publier un diagnostic explicite lorsque le pipeline réel ne dispose pas des preuves ou données nécessaires.
- Invariants et garde-fous: pas de conseil stratégique non sourcé; pas de "meilleure stratégie" universelle inventée; pas de backtest sur données fictives; aucun fallback vers résultats préfabriqués.
- Dépendances: T-020, modules SD et EX M-010/M-011, données de marché versionnées.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_real_strategy_short_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_task_system.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m013): couvrir strategie short reelle`
- Commit GREEN: `feat(m013): refuser strategie non prouvee`
