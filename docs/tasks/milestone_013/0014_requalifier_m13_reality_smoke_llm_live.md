# T-014 - Requalifier M13-reality en smoke test LLM live

## Milestone

- Nom: M-013 - Durcissement et acceptation V1, tranche `M13-remediation`.
- Source: `docs/specs/plan_remediation_m13.md`, `docs/specs/m013_reality_closure.md`, `docs/specs/plan_implementation_milestones_workstreams.md`, `docs/governance/m012_v1_gap_report.md` et `docs/governance/m013_v1_acceptance_report.md`.
- Objectif métier: lever l'ambiguïté entre un appel LLM réel et une validation produit réelle, afin que la V1 ne soit jamais déclarée prouvée par un simple smoke test `orchestrator-api -> llm-gateway -> Spark/vLLM`.

## Contexte DDD

- Domaine: assistant personnel de trading et d'investissement fondé sur preuves.
- Bounded context: gouvernance V1 et évaluation, avec impact documentaire sur `platform`, `conversation`, `research_answering`, `knowledge_access` et `source_processing`.
- Objectif métier: qualifier correctement les preuves M13 existantes avant d'exiger un pipeline bout-en-bout partant de PDF réels.
- Langage ubiquitaire: smoke test LLM live, pipeline produit réel, preuve bout-en-bout, corpus réel, validation V1, écart produit, absence de fallback.
- Invariants critiques: le chemin LLM live reste une preuve technique utile; il ne remplace pas une preuve PDF -> réponse citée ouvrable; aucun statut V1 n'est promu sans preuve produit.
- Garde-fous: ne pas changer le sens d'une ADR acceptée; ne pas masquer l'écart produit; ne pas supprimer les preuves techniques déjà acquises; ne pas présenter un micro-prompt comme donnée documentaire.

## Blocages Ou Préconditions

- État GREEN/RED connu: `uv run --locked gate` et `uv run --locked gate` sont GREEN avant création de la tranche; le chemin LLM live M13 est GREEN, mais le pipeline produit réel bout-en-bout n'est pas prouvé.
- Présence des milestones amont dans master: après `git fetch origin --prune`, `master` et `origin/master` pointent sur `08ecd4f2d56f993899d3bec0f5abe28f57405514`; les dossiers `docs/tasks/milestone_003` à `docs/tasks/milestone_013` sont présents dans `master`.
- Décisions manquantes: aucune décision structurante n'est requise pour requalifier la preuve; une ADR serait requise seulement si la définition de validation V1 changeait de sens.
- Risques: continuer à utiliser `M13-reality` comme validation de PDF réels; diluer le verdict `non acceptée`; rendre la documentation plus floue au lieu de séparer preuve technique et preuve produit.

## Tâches

### T-014 - Requalifier M13-reality en smoke test LLM live

- But métier: supprimer l'ambiguïté entre chemin LLM réel et pipeline produit réel.
- Portée DDD: documentation de M-013, traçabilité, rapport V1, langage de gate et journal du milestone.
- Scénario BDD:
  - Given le validateur actuel M13 appelle Gemma réel avec des micro-prompts.
  - When le rapport d'acceptation décrit la preuve obtenue.
  - Then il la qualifie comme smoke test LLM live et non comme validation réelle du produit.
- Tests d'acceptation à écrire: un validateur documentaire M-013 qui échoue si `M13-reality` est présenté comme preuve de pipeline PDF bout-en-bout.
- Tests unitaires à écrire: contrôles des libellés dans le rapport V1, la matrice de traçabilité, la spécification de remédiation et le journal M-013.
- Implémentation attendue: renommer les preuves existantes dans la documentation et les rapports sans supprimer leur valeur technique, puis expliciter que la validation produit reste à établir par les tâches T-015 à T-023.
- Invariants et garde-fous: aucune modification silencieuse d'ADR acceptée; aucun verdict V1 promu; aucun effacement des commandes GREEN existantes; aucune confusion entre prompt LLM et preuve documentaire.
- Dépendances: `docs/tasks/milestone_013/0013_ancrer_gateway_llm_chemin_reel.md`, `docs/specs/m013_reality_closure.md`, `docs/specs/plan_remediation_m13.md`, `docs/traceability/matrix.md`, rapport V1.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m013): refuser confusion smoke llm et pipeline reel`
- Commit GREEN: `docs(m013): requalifier reality en smoke test llm live`
